from datetime import date, datetime, timedelta
from typing import List, Dict, Any
from pathlib import Path
from jinja2 import Template
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import and_, or_

from app.database import get_db
from app.models.worker import Worker
from app.models.occupational_exam import OccupationalExam
from app.models.tipo_examen import TipoExamen
from app.models.cargo import Cargo
from app.models.user import User
from app.models.notification_acknowledgment import NotificationAcknowledgment
from app.services.email_service import EmailService
from app.config import settings
import logging

logger = logging.getLogger(__name__)


def is_notification_trigger_enabled(db: Session) -> bool:
    """Verifica si el disparador de notificaciones está habilitado"""
    from app.models.admin_config import SystemSettings

    setting = db.query(SystemSettings).filter(
        SystemSettings.key == SystemSettings.EXAM_NOTIFICATIONS_ENABLED
    ).first()

    # Si no existe la configuración, asumimos que está habilitado por defecto
    if not setting:
        return True

    return setting.is_enabled


class OccupationalExamNotificationService:
    """Servicio para notificaciones automáticas de exámenes ocupacionales"""
    
    def __init__(self, db: Session):
        self.db = db
        self.email_service = EmailService()
    
    def calculate_next_exam_date(self, exam_date: date, periodicidad: str) -> date:
        """Calcula la fecha del próximo examen basado en la periodicidad del cargo"""
        if periodicidad == "semestral":
            return exam_date + timedelta(days=180)  # 6 meses
        elif periodicidad == "anual":
            return exam_date + timedelta(days=365)  # 1 año
        elif periodicidad == "bianual":
            return exam_date + timedelta(days=730)  # 2 años
        else:
            # Por defecto anual si no se especifica
            return exam_date + timedelta(days=365)
    
    def get_workers_with_pending_exams(self, days_ahead: int = 15) -> List[Dict[str, Any]]:
        """Obtiene trabajadores que necesitan exámenes ocupacionales

        Args:
            days_ahead: Días de anticipación para enviar notificaciones (por defecto 15 días)
        """
        today = date.today()
        notification_date = today + timedelta(days=days_ahead)
        
        # Subconsulta para obtener el último examen de cada trabajador
        latest_exams = (
            self.db.query(
                OccupationalExam.worker_id,
                OccupationalExam.exam_date.label('last_exam_date'),
                TipoExamen.nombre.label('exam_type_name')
            )
            .join(TipoExamen, OccupationalExam.tipo_examen_id == TipoExamen.id)
            .distinct(OccupationalExam.worker_id)
            .order_by(OccupationalExam.worker_id, OccupationalExam.exam_date.desc())
            .subquery()
        )
        
        # Consulta principal para obtener trabajadores con exámenes pendientes
        workers_query = (
            self.db.query(
                Worker,
                Cargo,
                latest_exams.c.last_exam_date,
                latest_exams.c.exam_type_name
            )
            .join(
                Cargo,
                or_(
                    Worker.cargo_id == Cargo.id,
                    and_(Worker.cargo_id.is_(None), Worker.position == Cargo.nombre_cargo),
                ),
            )
            .outerjoin(latest_exams, Worker.id == latest_exams.c.worker_id)
            .filter(Worker.is_active == True)
        )
        
        workers_with_pending_exams = []
        
        for worker, cargo, last_exam_date, exam_type_name in workers_query.all():
            # Si no tiene exámenes previos, necesita uno inmediatamente
            if not last_exam_date:
                next_exam_date = today
                days_until_exam = 0
                status = "sin_examenes"
            else:
                # Calcular próxima fecha basada en periodicidad del cargo y la fecha del último examen
                next_exam_date = self.calculate_next_exam_date(
                    last_exam_date, 
                    cargo.periodicidad_emo or "anual"
                )
                days_until_exam = (next_exam_date - today).days
                
                if days_until_exam <= 0:
                    status = "vencido"
                elif days_until_exam <= days_ahead:
                    status = "proximo_a_vencer"
                else:
                    continue  # No necesita notificación aún
            
            # Obtener usuario asociado al trabajador
            user = self.db.query(User).filter(User.document_number == worker.document_number).first()
            
            workers_with_pending_exams.append({
                "worker": worker,
                "cargo": cargo,
                "user": user,
                "last_exam_date": last_exam_date,
                "next_exam_date": next_exam_date,
                "days_until_exam": days_until_exam,
                "status": status,
                "exam_type_name": exam_type_name
            })
        
        return workers_with_pending_exams
    
    def _load_email_template(self, use_html: bool = True) -> tuple[str, bool]:
        """
        Carga la plantilla para los correos de recordatorio
        Returns: (template_content, is_html)
        """
        try:
            if use_html:
                template_path = Path(__file__).parent.parent / "templates" / "emails" / "occupational_exam_reminder.html"
                with open(template_path, 'r', encoding='utf-8') as file:
                    return file.read(), True
            else:
                template_path = Path(__file__).parent.parent / "templates" / "emails" / "occupational_exam_reminder.txt"
                with open(template_path, 'r', encoding='utf-8') as file:
                    return file.read(), False
        except Exception as e:
            logger.error(f"Error cargando plantilla de email: {str(e)}")
            # Si falla HTML, intentar con texto plano
            if use_html:
                return self._load_email_template(use_html=False)
            
            # Plantilla de respaldo básica
            fallback_template = """
Recordatorio de Examen Médico Ocupacional

Estimado/a {{ worker_name }},

Le recordamos que tiene un examen médico ocupacional programado.

Fecha: {{ next_exam_date }}
Estado: {{ status }}

Por favor, contacte al área de SST para más información.

Atentamente,
Sistema de Gestión SST
            """
            return fallback_template, False
    
    def send_exam_reminder_email(self, worker_data: Dict[str, Any]) -> bool:
        """Envía correo de recordatorio de examen ocupacional usando plantilla HTML"""
        try:
            worker = worker_data["worker"]
            cargo = worker_data["cargo"]
            user = worker_data["user"]
            next_exam_date = worker_data["next_exam_date"]
            days_until_exam = worker_data["days_until_exam"]
            status = worker_data["status"]
            
            if not user or not user.email:
                logger.warning(f"No se encontró email para el trabajador {worker.full_name}")
                return False
            
            # Verificar si el trabajador ya confirmó la recepción de notificaciones para este examen
            # Buscar el examen más reciente del trabajador
            latest_exam = self.db.query(OccupationalExam).options(
                joinedload(OccupationalExam.tipo_examen)
            ).filter(
                OccupationalExam.worker_id == worker.id
            ).order_by(OccupationalExam.exam_date.desc()).first()
            
            if latest_exam:
                # Determinar el tipo de notificación según el estado
                if status == "vencido":
                    notification_type = "overdue"
                elif days_until_exam <= 7:
                    notification_type = "reminder"
                else:
                    notification_type = "first_notification"
                
                # Verificar si ya existe una confirmación para este tipo de notificación
                existing_acknowledgment = self.db.query(NotificationAcknowledgment).filter(
                    and_(
                        NotificationAcknowledgment.worker_id == worker.id,
                        NotificationAcknowledgment.occupational_exam_id == latest_exam.id,
                        NotificationAcknowledgment.notification_type == notification_type,
                        NotificationAcknowledgment.stops_notifications == True
                    )
                ).first()
                
                if existing_acknowledgment:
                    logger.info(f"Notificación omitida para {worker.full_name} - Ya confirmó recepción de {notification_type}")
                    return True  # Retornamos True porque no es un error, simplemente no se envía
            
            # Determinar el asunto según el estado
            if status == "sin_examenes":
                subject = "🚨 Examen Médico Ocupacional Requerido"
                urgency = "INMEDIATO"
            elif status == "vencido":
                subject = "🚨 URGENTE: Examen Médico Ocupacional Vencido"
                urgency = "URGENTE"
            else:  # proximo_a_vencer
                subject = "⚠️ RECORDATORIO: Examen Médico Ocupacional Próximo"
                urgency = "RECORDATORIO"
            
            # Cargar y renderizar la plantilla
            template_content, is_html = self._load_email_template()
            template = Template(template_content)
            
            # Determinar el tipo de examen (por defecto periódico)
            exam_type_label = "Examen Periódico"
            if latest_exam and latest_exam.tipo_examen:
                exam_type_label = latest_exam.tipo_examen.nombre
            
            # Preparar los datos para la plantilla
            last_exam_date = worker_data.get("last_exam_date")
            template_data = {
                "worker_name": worker.first_name,
                "worker_full_name": worker.full_name,
                "worker_document": worker.document_number,
                "worker_position": cargo.nombre_cargo,
                "cargo": cargo.nombre_cargo,
                "periodicidad": cargo.periodicidad_emo or 'Anual',
                "exam_date": next_exam_date.strftime('%d/%m/%Y'),
                "next_exam_date": next_exam_date.strftime('%d/%m/%Y'),
                "last_exam_date": last_exam_date.strftime('%d/%m/%Y') if last_exam_date else 'Sin exámenes previos',
                "days_until_exam": days_until_exam,
                "status": status,
                "urgency": urgency,
                "exam_type_label": exam_type_label,
                "current_date": datetime.now().strftime('%d/%m/%Y'),
                "current_time": datetime.now().strftime('%H:%M:%S'),
                "system_url": getattr(settings, 'FRONTEND_URL', None),
                "contact_email": getattr(settings, 'SUPPORT_EMAIL', None),
                # Variables para el botón de confirmación
                "api_base_url": getattr(settings, 'API_BASE_URL', None),
                "exam_id": latest_exam.id if latest_exam else None,
                "worker_id": worker.id
            }
            
            # Renderizar la plantilla
            rendered_content = template.render(**template_data)
            
            # Enviar correo según el tipo de plantilla con copia a bernardino.deaguas@gmail.com
            if is_html:
                success = self.email_service.send_email(
                    to_email=user.email,
                    subject=subject,
                    message_html=rendered_content,
                    cc=['bernardino.deaguas@gmail.com']
                )
            else:
                # Para texto plano, convertir a HTML básico
                html_content = f"<pre>{rendered_content}</pre>"
                success = self.email_service.send_email(
                    to_email=user.email,
                    subject=subject,
                    message_html=html_content,
                    cc=['bernardino.deaguas@gmail.com']
                )
            
            if success:
                logger.info(f"Correo de recordatorio enviado a {user.email} para {worker.full_name}")
            else:
                logger.error(f"Error enviando correo a {user.email} para {worker.full_name}")
            
            return success
            
        except Exception as e:
            logger.error(f"Error enviando correo de recordatorio: {str(e)}")
            return False
    
    def send_daily_notifications(self) -> Dict[str, int]:
        """Envía notificaciones diarias de exámenes ocupacionales"""
        logger.info("Iniciando envío de notificaciones diarias de exámenes ocupacionales")

        # Verificar si el disparador de notificaciones está habilitado
        if not is_notification_trigger_enabled(self.db):
            logger.info("Disparador de notificaciones deshabilitado por administrador. No se enviarán notificaciones.")
            return {
                "total_workers": 0,
                "emails_sent": 0,
                "emails_failed": 0,
                "sin_examenes": 0,
                "vencidos": 0,
                "proximos_a_vencer": 0,
                "status": "disabled",
                "message": "Disparador de notificaciones deshabilitado por administrador"
            }

        # Obtener trabajadores con exámenes pendientes (15 días de anticipación)
        workers_with_pending_exams = self.get_workers_with_pending_exams(days_ahead=15)
        
        stats = {
            "total_workers": len(workers_with_pending_exams),
            "emails_sent": 0,
            "emails_failed": 0,
            "sin_examenes": 0,
            "vencidos": 0,
            "proximos_a_vencer": 0
        }
        
        for worker_data in workers_with_pending_exams:
            status = worker_data["status"]
            stats[status] += 1
            
            # Enviar correo de recordatorio
            if self.send_exam_reminder_email(worker_data):
                stats["emails_sent"] += 1
            else:
                stats["emails_failed"] += 1
        
        logger.info(f"Notificaciones enviadas: {stats}")
        return stats
    
    def get_exam_statistics(self) -> Dict[str, Any]:
        """Obtiene estadísticas de exámenes ocupacionales"""
        today = date.today()
        
        # Trabajadores activos
        total_workers = self.db.query(Worker).filter(Worker.is_active == True).count()
        
        # Trabajadores sin exámenes
        workers_without_exams = (
            self.db.query(Worker)
            .outerjoin(OccupationalExam)
            .filter(
                and_(
                    Worker.is_active == True,
                    OccupationalExam.id.is_(None)
                )
            )
            .count()
        )
        
        # Obtener trabajadores con exámenes vencidos basados en la periodicidad del cargo
        workers_with_pending_exams = self.get_workers_with_pending_exams(days_ahead=0)
        exams_overdue = sum(1 for worker_data in workers_with_pending_exams if worker_data["status"] == "vencido")
        
        # Exámenes próximos a vencer (15 días)
        workers_with_upcoming_exams = self.get_workers_with_pending_exams(days_ahead=15)
        exams_upcoming = sum(1 for worker_data in workers_with_upcoming_exams if worker_data["status"] == "proximo_a_vencer")
        
        return {
            "total_workers": total_workers,
            "workers_without_exams": workers_without_exams,
            "exams_overdue": exams_overdue,
            "exams_upcoming": exams_upcoming,
            "last_check": datetime.now().isoformat()
        }


def run_daily_exam_notifications():
    """Función para ejecutar las notificaciones diarias"""
    db = next(get_db())
    try:
        service = OccupationalExamNotificationService(db)
        return service.send_daily_notifications()
    finally:
        db.close()


if __name__ == "__main__":
    # Para pruebas
    stats = run_daily_exam_notifications()
    print(f"Estadísticas de notificaciones: {stats}")
