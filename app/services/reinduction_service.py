from datetime import datetime, date, timedelta
from typing import List, Optional, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_, func

from app.models.worker import Worker
from app.models.course import Course, CourseType
from app.models.enrollment import Enrollment, EnrollmentStatus
from app.models.reinduction import ReinductionRecord, ReinductionConfig, ReinductionStatus
from app.models.notification import Notification
from app.schemas.reinduction import (
    ReinductionRecordCreate,
    ReinductionRecordUpdate,
    ReinductionConfigCreate,
    ReinductionConfigUpdate,
    WorkerReinductionSummary,
    ReinductionDashboard,
    BulkReinductionCreate,
    ReinductionNotification
)
from app.models.notification import Notification, NotificationType, NotificationPriority
from app.utils.email import send_email



class ReinductionService:
    """Servicio para gestionar la lógica de reinducción de trabajadores"""
    
    def __init__(self, db: Session):
        self.db = db
    
    def calculate_reinduction_due_date(self, fecha_ingreso: date, year: int, grace_period_days: int = 30) -> date:
        """Calcula la fecha límite para completar la reinducción de un año específico"""
        # La reinducción debe completarse en el aniversario + período de gracia
        anniversary_date = fecha_ingreso.replace(year=year)
        return anniversary_date + timedelta(days=grace_period_days)
    
    def get_years_requiring_reinduction(self, fecha_ingreso: date) -> List[int]:
        """Obtiene los años en los que el trabajador requiere reinducción"""
        current_year = date.today().year
        start_year = fecha_ingreso.year + 1  # La primera reinducción es al año de ingreso
        
        return list(range(start_year, current_year + 1))
    
    def create_reinduction_record(self, record_data: ReinductionRecordCreate, created_by: int) -> ReinductionRecord:
        """Crea un nuevo registro de reinducción"""
        # Verificar si ya existe un registro para este trabajador y año
        existing = self.db.query(ReinductionRecord).filter(
            and_(
                ReinductionRecord.worker_id == record_data.worker_id,
                ReinductionRecord.year == record_data.year
            )
        ).first()
        
        if existing:
            raise ValueError(f"Ya existe un registro de reinducción para el trabajador {record_data.worker_id} en el año {record_data.year}")
        
        record = ReinductionRecord(
            **record_data.model_dump(),
            created_by=created_by
        )
        
        self.db.add(record)
        self.db.commit()
        self.db.refresh(record)
        
        print(f"Registro de reinducción creado: {record.id} para trabajador {record.worker_id}")
        return record
    
    def update_reinduction_record(self, record_id: int, update_data: ReinductionRecordUpdate) -> ReinductionRecord:
        """Actualiza un registro de reinducción"""
        record = self.db.query(ReinductionRecord).filter(ReinductionRecord.id == record_id).first()
        if not record:
            raise ValueError(f"Registro de reinducción {record_id} no encontrado")
        
        update_dict = update_data.model_dump(exclude_unset=True)
        for field, value in update_dict.items():
            setattr(record, field, value)
        
        self.db.commit()
        self.db.refresh(record)
        
        print(f"Registro de reinducción actualizado: {record.id}")
        return record
    
    def generate_missing_reinduction_records(self, worker_id: Optional[int] = None) -> Dict[str, int]:
        """Genera registros de reinducción faltantes para trabajadores"""
        config = self.get_reinduction_config()
        
        # Filtrar trabajadores
        query = self.db.query(Worker).filter(Worker.is_active == True)
        if worker_id:
            query = query.filter(Worker.id == worker_id)
        
        workers = query.all()
        created_count = 0
        updated_count = 0
        
        for worker in workers:
            if not worker.fecha_de_ingreso:
                print(f"Trabajador {worker.id} no tiene fecha de ingreso")
                continue
            
            required_years = self.get_years_requiring_reinduction(worker.fecha_de_ingreso)
            
            for year in required_years:
                # Verificar si ya existe el registro
                existing = self.db.query(ReinductionRecord).filter(
                    and_(
                        ReinductionRecord.worker_id == worker.id,
                        ReinductionRecord.year == year
                    )
                ).first()
                
                if not existing:
                    # Crear nuevo registro
                    due_date = self.calculate_reinduction_due_date(
                        worker.fecha_de_ingreso, 
                        year, 
                        config.grace_period_days
                    )
                    
                    record = ReinductionRecord(
                        worker_id=worker.id,
                        year=year,
                        due_date=due_date,
                        status=ReinductionStatus.PENDING,
                        assigned_course_id=config.default_reinduction_course_id
                    )
                    
                    self.db.add(record)
                    created_count += 1
                else:
                    # Actualizar estado si está vencido
                    if existing.is_overdue and existing.status not in [ReinductionStatus.COMPLETED, ReinductionStatus.EXEMPTED]:
                        existing.status = ReinductionStatus.OVERDUE
                        updated_count += 1
        
        self.db.commit()
        
        print(f"Registros de reinducción generados: {created_count} creados, {updated_count} actualizados")
        return {"created": created_count, "updated": updated_count}
    
    def enroll_worker_in_reinduction(self, record_id: int, course_id: Optional[int] = None) -> Enrollment:
        """Inscribe a un trabajador en un curso de reinducción"""
        record = self.db.query(ReinductionRecord).filter(ReinductionRecord.id == record_id).first()
        if not record:
            raise ValueError(f"Registro de reinducción {record_id} no encontrado")
        
        worker = record.worker
        if not worker.user_id:
            raise ValueError(f"El trabajador {worker.id} no tiene usuario asociado")
        
        # Usar el curso asignado o el curso por defecto
        target_course_id = course_id or record.assigned_course_id
        if not target_course_id:
            config = self.get_reinduction_config()
            target_course_id = config.default_reinduction_course_id
        
        if not target_course_id:
            raise ValueError("No hay curso de reinducción configurado")
        
        # Verificar que el curso existe y es de tipo REINDUCTION
        course = self.db.query(Course).filter(Course.id == target_course_id).first()
        if not course:
            raise ValueError(f"Curso {target_course_id} no encontrado")
        
        if course.course_type != CourseType.REINDUCTION:
            raise ValueError(f"El curso {course.title} no es de tipo reinducción")
        
        # Verificar si ya está inscrito
        existing_enrollment = self.db.query(Enrollment).filter(
            and_(
                Enrollment.user_id == worker.user_id,
                Enrollment.course_id == target_course_id,
                Enrollment.status.in_([EnrollmentStatus.PENDING, EnrollmentStatus.ACTIVE])
            )
        ).first()
        
        if existing_enrollment:
            # Actualizar el registro con la inscripción existente
            record.enrollment_id = existing_enrollment.id
            record.status = ReinductionStatus.IN_PROGRESS
            self.db.commit()
            return existing_enrollment
        
        # Crear nueva inscripción
        enrollment = Enrollment(
            user_id=worker.user_id,
            course_id=target_course_id,
            status=EnrollmentStatus.ACTIVE.value
        )
        
        self.db.add(enrollment)
        self.db.flush()  # Para obtener el ID
        
        # Actualizar el registro de reinducción
        record.enrollment_id = enrollment.id
        record.assigned_course_id = target_course_id
        record.status = ReinductionStatus.IN_PROGRESS
        
        self.db.commit()
        self.db.refresh(enrollment)
        
        print(f"Trabajador {worker.id} inscrito en curso de reinducción {target_course_id}")
        return enrollment
    
    def check_completed_reinducciones(self) -> int:
        """Verifica y actualiza el estado de reinducciones completadas"""
        # Buscar inscripciones completadas que correspondan a reinducciones
        completed_enrollments = self.db.query(Enrollment).join(Course).filter(
            and_(
                Enrollment.status == EnrollmentStatus.COMPLETED,
                Course.course_type == CourseType.REINDUCTION
            )
        ).all()
        
        updated_count = 0
        
        for enrollment in completed_enrollments:
            # Buscar el registro de reinducción correspondiente
            record = self.db.query(ReinductionRecord).filter(
                ReinductionRecord.enrollment_id == enrollment.id
            ).first()
            
            if record and record.status != ReinductionStatus.COMPLETED:
                record.status = ReinductionStatus.COMPLETED
                record.completed_date = enrollment.completed_at.date() if enrollment.completed_at else date.today()
                updated_count += 1
        
        if updated_count > 0:
            self.db.commit()
            print(f"Actualizados {updated_count} registros de reinducción como completados")
        
        return updated_count
    
    def send_reinduction_notifications(self) -> Dict[str, int]:
        """Envía notificaciones de reinducción según las fechas configuradas"""
        config = self.get_reinduction_config()
        
        if not config.auto_notification_enabled:
            return {"sent": 0, "errors": 0}
        
        # Buscar registros que necesitan notificación
        records = self.db.query(ReinductionRecord).join(Worker).filter(
            and_(
                Worker.is_active == True,
                ReinductionRecord.status.in_([ReinductionStatus.PENDING, ReinductionStatus.SCHEDULED])
            )
        ).all()
        
        sent_count = 0
        error_count = 0
        
        for record in records:
            try:
                if record.needs_notification:
                    self._send_notification_for_record(record, config)
                    sent_count += 1
            except Exception as e:
                print(f"Error enviando notificación para registro {record.id}: {str(e)}")
                error_count += 1
        
        if sent_count > 0:
            self.db.commit()
            print(f"Enviadas {sent_count} notificaciones de reinducción")
        
        return {"sent": sent_count, "errors": error_count}
    
    def _send_notification_for_record(self, record: ReinductionRecord, config: ReinductionConfig):
        """Envía notificación para un registro específico"""
        worker = record.worker
        days_left = record.days_until_due
        
        # Determinar tipo de notificación
        if days_left <= config.first_notification_days and not record.first_notification_sent:
            notification_type = "first"
            record.first_notification_sent = datetime.utcnow()
        elif days_left <= config.reminder_notification_days and not record.reminder_notification_sent:
            notification_type = "reminder"
            record.reminder_notification_sent = datetime.utcnow()
        elif days_left < 0 and not record.overdue_notification_sent:
            notification_type = "overdue"
            record.overdue_notification_sent = datetime.utcnow()
        else:
            return
        
        # Crear mensaje de notificación
        if notification_type == "first":
            message = f"Estimado {worker.full_name}, su reinducción anual está programada para completarse antes del {record.due_date.strftime('%d/%m/%Y')}. Quedan {abs(days_left)} días."
        elif notification_type == "reminder":
            message = f"Recordatorio: {worker.full_name}, su reinducción anual debe completarse antes del {record.due_date.strftime('%d/%m/%Y')}. Quedan {abs(days_left)} días."
        else:  # overdue
            message = f"URGENTE: {worker.full_name}, su reinducción anual está vencida desde el {record.due_date.strftime('%d/%m/%Y')}. Han pasado {abs(days_left)} días."
        
        # Enviar notificación en la aplicación si el trabajador tiene usuario
        if worker.user_id:
            priority = NotificationPriority.HIGH if notification_type == "overdue" else NotificationPriority.NORMAL
            notification = Notification(
                user_id=worker.user_id,
                title=f"Reinducción Anual {record.year}",
                message=message,
                notification_type=NotificationType.IN_APP,
                priority=priority
            )
            self.db.add(notification)
        
        # Enviar notificación por email si el trabajador tiene email
        if worker.email:
            self._send_email_notification(worker, record, notification_type, days_left)
        
        self.db.commit()
    
    def _send_email_notification(self, worker: Worker, record: ReinductionRecord, notification_type: str, days_left: int):
        """Envía notificación por email para un registro de reinducción"""
        try:
            # Obtener información del curso si está asignado
            course_name = None
            if record.assigned_course_id:
                course = self.db.query(Course).filter(Course.id == record.assigned_course_id).first()
                if course:
                    course_name = course.name
            
            # Preparar contexto para la plantilla
            context = {
                'worker_name': worker.full_name,
                'year': record.year,
                'due_date': record.due_date.strftime('%d/%m/%Y'),
                'days_left': days_left,
                'is_overdue': days_left < 0,
                'notification_type': notification_type,
                'course_name': course_name,
                'system_url': 'http://localhost:8000'  # TODO: Obtener de configuración
            }
            
            # Determinar asunto del email
            if notification_type == "overdue":
                subject = f"URGENTE: Reinducción Anual {record.year} Vencida"
            elif notification_type == "reminder":
                subject = f"Recordatorio: Reinducción Anual {record.year}"
            else:
                subject = f"Reinducción Anual {record.year} Requerida"
            
            # Enviar email
            success = send_email(
                recipient=worker.email,
                subject=subject,
                template='reinduction_notification',
                context=context
            )
            
            if success:
                print(f"Email de reinducción enviado a {worker.email} para registro {record.id}")
            else:
                print(f"Error al enviar email de reinducción a {worker.email} para registro {record.id}")
                
        except Exception as e:
            print(f"Error al enviar email de reinducción: {str(e)}")
    
    def send_anniversary_notification(self, worker_id: int) -> bool:
        """Envía notificación de aniversario y crea registro de reinducción para un trabajador específico"""
        try:
            worker = self.db.query(Worker).filter(Worker.id == worker_id).first()
            if not worker:
                print(f"Trabajador {worker_id} no encontrado")
                return False
            
            if not worker.fecha_de_ingreso:
                print(f"Trabajador {worker_id} no tiene fecha de ingreso")
                return False
            
            if not worker.email:
                print(f"Trabajador {worker_id} no tiene email configurado")
                return False
            
            # Calcular años en la empresa
            today = date.today()
            years_in_company = today.year - worker.fecha_de_ingreso.year
            
            # Verificar si es el aniversario (mismo día y mes)
            anniversary_date = worker.fecha_de_ingreso.replace(year=today.year)
            if today != anniversary_date:
                print(f"Hoy no es el aniversario del trabajador {worker_id}. Aniversario: {anniversary_date}")
            
            # Crear registro de reinducción si no existe
            current_year = today.year
            existing_record = self.db.query(ReinductionRecord).filter(
                and_(
                    ReinductionRecord.worker_id == worker_id,
                    ReinductionRecord.year == current_year
                )
            ).first()
            
            if not existing_record:
                config = self.get_reinduction_config()
                due_date = self.calculate_reinduction_due_date(
                    worker.fecha_de_ingreso,
                    current_year,
                    config.grace_period_days
                )
                
                record = ReinductionRecord(
                    worker_id=worker_id,
                    year=current_year,
                    due_date=due_date,
                    status=ReinductionStatus.PENDING,
                    assigned_course_id=config.default_reinduction_course_id,
                    first_notification_sent=datetime.utcnow()
                )
                
                self.db.add(record)
                self.db.commit()
                self.db.refresh(record)
                print(f"Registro de reinducción creado para trabajador {worker_id}, año {current_year}")
            else:
                record = existing_record
                print(f"Registro de reinducción ya existe para trabajador {worker_id}, año {current_year}")
            
            # Obtener información del curso si está asignado
            course_name = None
            if record.assigned_course_id:
                course = self.db.query(Course).filter(Course.id == record.assigned_course_id).first()
                if course:
                    course_name = course.name
            
            # Preparar contexto para email de aniversario
            context = {
                'worker_name': worker.full_name,
                'years_in_company': years_in_company,
                'anniversary_date': anniversary_date.strftime('%d/%m/%Y'),
                'year': current_year,
                'due_date': record.due_date.strftime('%d/%m/%Y'),
                'notification_type': 'anniversary',
                'course_name': course_name,
                'system_url': 'http://localhost:8000'  # TODO: Obtener de configuración
            }
            
            # Enviar email de aniversario
            subject = f"🎉 ¡Felicidades por tu {years_in_company}° aniversario! - Reinducción Requerida"
            success = send_email(
                recipient=worker.email,
                subject=subject,
                template='reinduction_notification',
                context=context
            )
            
            if success:
                print(f"Email de aniversario enviado a {worker.email} para trabajador {worker_id}")
                return True
            else:
                print(f"Error al enviar email de aniversario a {worker.email} para trabajador {worker_id}")
                return False
                
        except Exception as e:
            print(f"Error al enviar notificación de aniversario: {str(e)}")
            return False
    
    def get_worker_reinduction_summary(self, worker_id: int) -> WorkerReinductionSummary:
        """Obtiene el resumen de reinducción para un trabajador"""
        worker = self.db.query(Worker).filter(Worker.id == worker_id).first()
        if not worker:
            raise ValueError(f"Trabajador {worker_id} no encontrado")
        
        if not worker.fecha_de_ingreso:
            raise ValueError(f"Trabajador {worker_id} no tiene fecha de ingreso")
        
        # Calcular años en la empresa
        years_in_company = date.today().year - worker.fecha_de_ingreso.year
        
        # Obtener registros de reinducción
        records = self.db.query(ReinductionRecord).filter(
            ReinductionRecord.worker_id == worker_id
        ).all()
        
        # Estadísticas
        total_reinducciones = len(records)
        completed_reinducciones = len([r for r in records if r.status == ReinductionStatus.COMPLETED])
        pending_reinducciones = len([r for r in records if r.status == ReinductionStatus.PENDING])
        overdue_reinducciones = len([r for r in records if r.status == ReinductionStatus.OVERDUE])
        
        # Registro del año actual
        current_year = date.today().year
        current_year_record = next((r for r in records if r.year == current_year), None)
        
        # Próxima fecha límite
        pending_records = [r for r in records if r.status in [ReinductionStatus.PENDING, ReinductionStatus.SCHEDULED]]
        next_due_date = min([r.due_date for r in pending_records]) if pending_records else None
        
        return WorkerReinductionSummary(
            worker_id=worker.id,
            worker_name=worker.full_name,
            fecha_de_ingreso=worker.fecha_de_ingreso,
            years_in_company=years_in_company,
            current_year_record=current_year_record,
            total_reinducciones=total_reinducciones,
            completed_reinducciones=completed_reinducciones,
            pending_reinducciones=pending_reinducciones,
            overdue_reinducciones=overdue_reinducciones,
            next_due_date=next_due_date
        )
    
    def get_reinduction_dashboard(self) -> ReinductionDashboard:
        """Obtiene el dashboard con estadísticas de reinducción"""
        # Estadísticas generales
        total_workers = self.db.query(Worker).filter(Worker.is_active == True).count()
        
        # Trabajadores que requieren reinducción (tienen fecha de ingreso y más de 1 año)
        workers_requiring = self.db.query(Worker).filter(
            and_(
                Worker.is_active == True,
                Worker.fecha_de_ingreso.isnot(None),
                Worker.fecha_de_ingreso < date.today() - timedelta(days=365)
            )
        ).count()
        
        # Estadísticas de registros
        pending = self.db.query(ReinductionRecord).filter(
            ReinductionRecord.status == ReinductionStatus.PENDING
        ).count()
        
        in_progress = self.db.query(ReinductionRecord).filter(
            ReinductionRecord.status == ReinductionStatus.IN_PROGRESS
        ).count()
        
        completed_this_year = self.db.query(ReinductionRecord).filter(
            and_(
                ReinductionRecord.status == ReinductionStatus.COMPLETED,
                ReinductionRecord.year == date.today().year
            )
        ).count()
        
        overdue = self.db.query(ReinductionRecord).filter(
            ReinductionRecord.status == ReinductionStatus.OVERDUE
        ).count()
        
        # Próximos vencimientos
        today = date.today()
        upcoming_30 = self.db.query(ReinductionRecord).filter(
            and_(
                ReinductionRecord.due_date.between(today, today + timedelta(days=30)),
                ReinductionRecord.status.in_([ReinductionStatus.PENDING, ReinductionStatus.SCHEDULED])
            )
        ).count()
        
        upcoming_60 = self.db.query(ReinductionRecord).filter(
            and_(
                ReinductionRecord.due_date.between(today, today + timedelta(days=60)),
                ReinductionRecord.status.in_([ReinductionStatus.PENDING, ReinductionStatus.SCHEDULED])
            )
        ).count()
        
        # Listas de trabajadores
        workers_overdue = self._get_workers_by_status(ReinductionStatus.OVERDUE)
        workers_due_soon = self._get_workers_due_soon(30)
        
        return ReinductionDashboard(
            total_workers=total_workers,
            workers_requiring_reinduction=workers_requiring,
            pending_reinducciones=pending,
            in_progress_reinducciones=in_progress,
            completed_this_year=completed_this_year,
            overdue_reinducciones=overdue,
            upcoming_due_30_days=upcoming_30,
            upcoming_due_60_days=upcoming_60,
            workers_overdue=workers_overdue,
            workers_due_soon=workers_due_soon
        )
    
    def _get_workers_by_status(self, status: ReinductionStatus) -> List[WorkerReinductionSummary]:
        """Obtiene trabajadores por estado de reinducción"""
        records = self.db.query(ReinductionRecord).join(Worker).filter(
            and_(
                ReinductionRecord.status == status,
                Worker.is_active == True
            )
        ).all()
        
        summaries = []
        for record in records:
            try:
                summary = self.get_worker_reinduction_summary(record.worker_id)
                summaries.append(summary)
            except Exception as e:
                print(f"Error obteniendo resumen para trabajador {record.worker_id}: {str(e)}")
        
        return summaries
    
    def _get_workers_due_soon(self, days: int) -> List[WorkerReinductionSummary]:
        """Obtiene trabajadores con reinducción próxima a vencer"""
        today = date.today()
        records = self.db.query(ReinductionRecord).join(Worker).filter(
            and_(
                ReinductionRecord.due_date.between(today, today + timedelta(days=days)),
                ReinductionRecord.status.in_([ReinductionStatus.PENDING, ReinductionStatus.SCHEDULED]),
                Worker.is_active == True
            )
        ).all()
        
        summaries = []
        for record in records:
            try:
                summary = self.get_worker_reinduction_summary(record.worker_id)
                summaries.append(summary)
            except Exception as e:
                print(f"Error obteniendo resumen para trabajador {record.worker_id}: {str(e)}")
        
        return summaries
    
    def get_reinduction_config(self) -> ReinductionConfig:
        """Obtiene la configuración de reinducción (crea una por defecto si no existe)"""
        config = self.db.query(ReinductionConfig).first()
        
        if not config:
            # Crear configuración por defecto
            config = ReinductionConfig()
            self.db.add(config)
            self.db.commit()
            self.db.refresh(config)
            print("Configuración de reinducción creada con valores por defecto")
        
        return config
    
    def update_reinduction_config(self, update_data: ReinductionConfigUpdate, updated_by: int) -> ReinductionConfig:
        """Actualiza la configuración de reinducción"""
        config = self.get_reinduction_config()
        
        update_dict = update_data.model_dump(exclude_unset=True)
        for field, value in update_dict.items():
            setattr(config, field, value)
        
        config.updated_by = updated_by
        
        self.db.commit()
        self.db.refresh(config)
        
        print(f"Configuración de reinducción actualizada por usuario {updated_by}")
        return config
    
    def bulk_create_reinducciones(self, bulk_data: BulkReinductionCreate, created_by: int) -> Dict[str, Any]:
        """Crea reinducciones en lote para múltiples trabajadores"""
        created_records = []
        errors = []
        created_count = 0
        skipped_count = 0
        
        config = self.get_reinduction_config()
        
        for worker_id in bulk_data.worker_ids:
            try:
                # Verificar que el trabajador existe
                worker = self.db.query(Worker).filter(Worker.id == worker_id).first()
                if not worker:
                    errors.append(f"Trabajador {worker_id} no encontrado")
                    continue
                
                if not worker.fecha_de_ingreso:
                    errors.append(f"Trabajador {worker_id} no tiene fecha de ingreso")
                    continue
                
                # Verificar si ya existe el registro
                existing = self.db.query(ReinductionRecord).filter(
                    and_(
                        ReinductionRecord.worker_id == worker_id,
                        ReinductionRecord.year == bulk_data.year
                    )
                ).first()
                
                if existing:
                    skipped_count += 1
                    continue
                
                # Calcular fecha límite
                due_date = self.calculate_reinduction_due_date(
                    worker.fecha_de_ingreso,
                    bulk_data.year,
                    config.grace_period_days
                )
                
                # Crear registro
                record = ReinductionRecord(
                    worker_id=worker_id,
                    year=bulk_data.year,
                    due_date=due_date,
                    assigned_course_id=bulk_data.assigned_course_id or config.default_reinduction_course_id,
                    scheduled_date=bulk_data.scheduled_date,
                    notes=bulk_data.notes,
                    created_by=created_by
                )
                
                self.db.add(record)
                created_records.append(record)
                created_count += 1
                
            except Exception as e:
                errors.append(f"Error con trabajador {worker_id}: {str(e)}")
        
        if created_count > 0:
            self.db.commit()
            # Refresh records to get IDs
            for record in created_records:
                self.db.refresh(record)
        
        print(f"Creación en lote completada: {created_count} creados, {skipped_count} omitidos, {len(errors)} errores")
        
        return {
            "created_count": created_count,
            "updated_count": 0,
            "skipped_count": skipped_count,
            "errors": errors,
            "created_records": created_records
        }
    
    def run_daily_check(self) -> Dict[str, Any]:
        """Ejecuta la verificación diaria automática"""
        config = self.get_reinduction_config()
        
        if not config.auto_check_enabled:
            return {"message": "Verificación automática deshabilitada"}
        
        results = {}
        
        try:
            # 1. Generar registros faltantes
            generation_result = self.generate_missing_reinduction_records()
            results["generation"] = generation_result
            
            # 2. Verificar reinducciones completadas
            completed_count = self.check_completed_reinducciones()
            results["completed_check"] = {"updated": completed_count}
            
            # 3. Enviar notificaciones
            notification_result = self.send_reinduction_notifications()
            results["notifications"] = notification_result
            
            print(f"Verificación diaria completada: {results}")
            
        except Exception as e:
            print(f"Error en verificación diaria: {str(e)}")
            results["error"] = str(e)
        
        return results