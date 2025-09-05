from datetime import datetime, timedelta
from typing import List, Dict, Any
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func, and_, or_

from app.database import get_db
from app.models.user import User
from app.models.worker import Worker
from app.models.course import Course
from app.models.enrollment import Enrollment, EnrollmentStatus
from app.models.evaluation import Evaluation, UserEvaluation, UserEvaluationStatus
from app.models.attendance import Attendance
from app.models.certificate import Certificate
from app.models.reinduction import ReinductionRecord
from app.schemas.supervisor_dashboard import SupervisorDashboardResponse
from app.dependencies import get_current_user, PermissionChecker

router = APIRouter()


@router.get("/dashboard", response_model=SupervisorDashboardResponse)
def get_supervisor_dashboard(
    db: Session = Depends(get_db),
    current_user: User = Depends(PermissionChecker("dashboard", "view"))
):
    """
    Obtener estadísticas del dashboard para supervisores
    """
    
    # Obtener estadísticas principales
    stats = _get_supervisor_stats(db)
    
    # Obtener miembros del equipo
    team_members = _get_team_members(db)
    
    # Obtener alertas de capacitación
    training_alerts = _get_training_alerts(db)
    
    # Obtener datos de cumplimiento
    compliance_data = _get_compliance_data(db)
    
    return SupervisorDashboardResponse(
        stats=stats,
        team_members=team_members,
        training_alerts=training_alerts,
        compliance_data=compliance_data
    )


def _get_supervisor_stats(db: Session) -> Dict[str, Any]:
    """
    Obtener estadísticas principales del supervisor
    """
    # Métricas de trabajadores
    total_employees = db.query(Worker).count()
    active_employees = db.query(Worker).filter(Worker.is_active == True).count()
    inactive_employees = db.query(Worker).filter(Worker.is_active == False).count()
    
    # Empleados en capacitación (con enrollments activos)
    employees_in_training = db.query(Worker).join(
        User, Worker.user_id == User.id
    ).join(
        Enrollment, User.id == Enrollment.user_id
    ).filter(
        Worker.is_active == True,
        Enrollment.status == EnrollmentStatus.ACTIVE
    ).distinct().count()
    
    # Capacitaciones completadas en los últimos 30 días
    thirty_days_ago = datetime.utcnow() - timedelta(days=30)
    completed_trainings = db.query(Enrollment).filter(
        Enrollment.status == EnrollmentStatus.COMPLETED,
        Enrollment.completed_at >= thirty_days_ago
    ).count()
    
    # Evaluaciones pendientes
    pending_evaluations = db.query(UserEvaluation).join(
        Enrollment, UserEvaluation.enrollment_id == Enrollment.id
    ).filter(
        UserEvaluation.status == UserEvaluationStatus.NOT_STARTED,
        Enrollment.status == EnrollmentStatus.ACTIVE
    ).count()
    
    # Capacitaciones vencidas (enrollments que deberían estar completados)
    expired_trainings = db.query(Enrollment).join(
        Course, Enrollment.course_id == Course.id
    ).filter(
        Enrollment.status.in_([EnrollmentStatus.ACTIVE, EnrollmentStatus.PENDING]),
        Course.expires_at < datetime.utcnow()
    ).count()
    
    # Calcular tasa de cumplimiento
    total_enrollments = db.query(Enrollment).count()
    completed_enrollments = db.query(Enrollment).filter(
        Enrollment.status == EnrollmentStatus.COMPLETED
    ).count()
    
    compliance_rate = (completed_enrollments / total_enrollments * 100) if total_enrollments > 0 else 0
    
    return {
        "total_employees": total_employees,
        "active_employees": active_employees,
        "inactive_employees": inactive_employees,
        "employees_in_training": employees_in_training,
        "completed_trainings": completed_trainings,
        "pending_evaluations": pending_evaluations,
        "compliance_rate": round(compliance_rate, 1),
        "expired_trainings": expired_trainings
    }


def _get_team_members(db: Session) -> List[Dict[str, Any]]:
    """
    Obtener información de los miembros del equipo
    """
    # Obtener trabajadores activos con su información de usuario y enrollments
    workers = db.query(Worker).filter(Worker.is_active == True).limit(10).all()
    
    team_members = []
    for worker in workers:
        # Obtener enrollments del usuario asociado
        if worker.user_id:
            active_courses = db.query(Enrollment).filter(
                Enrollment.user_id == worker.user_id,
                Enrollment.status == EnrollmentStatus.ACTIVE
            ).count()
            
            completed_courses = db.query(Enrollment).filter(
                Enrollment.user_id == worker.user_id,
                Enrollment.status == EnrollmentStatus.COMPLETED
            ).count()
            
            # Obtener última actividad
            last_activity = db.query(Enrollment.updated_at).filter(
                Enrollment.user_id == worker.user_id
            ).order_by(Enrollment.updated_at.desc()).first()
            
            last_activity_date = last_activity[0] if last_activity else worker.created_at
        else:
            active_courses = 0
            completed_courses = 0
            last_activity_date = worker.created_at
        
        # Determinar estado
        if active_courses > 0:
            status = "En Capacitación"
        elif completed_courses > 0:
            status = "Completado"
        else:
            status = "Sin Asignar"
        
        team_members.append({
            "id": worker.id,
            "name": worker.full_name,
            "position": worker.position,
            "active_courses": active_courses,
            "completed_courses": completed_courses,
            "status": status,
            "last_activity": last_activity_date.strftime("%Y-%m-%d") if last_activity_date else None
        })
    
    return team_members


def _get_training_alerts(db: Session) -> List[Dict[str, Any]]:
    """
    Obtener alertas de capacitación
    """
    alerts = []
    
    # Alertas de cursos próximos a vencer
    thirty_days_from_now = datetime.utcnow() + timedelta(days=30)
    expiring_courses = db.query(Course).filter(
        Course.expires_at.between(datetime.utcnow(), thirty_days_from_now),
        Course.status == "published"
    ).all()
    
    for course in expiring_courses:
        alerts.append({
            "id": f"course_expiring_{course.id}",
            "employee_name": "Todos los empleados",
            "training_name": course.title,
            "due_date": course.expires_at.strftime("%Y-%m-%d") if course.expires_at else None,
            "priority": "medium",
            "days_overdue": 0
        })
    
    # Alertas de evaluaciones pendientes por mucho tiempo
    seven_days_ago = datetime.utcnow() - timedelta(days=7)
    overdue_evaluations = db.query(UserEvaluation).filter(
        UserEvaluation.status == UserEvaluationStatus.NOT_STARTED,
        UserEvaluation.created_at < seven_days_ago
    ).count()

    if overdue_evaluations > 0:
        alerts.append({
            "id": "overdue_evaluations",
            "employee_name": "Varios empleados",
            "training_name": "Evaluaciones pendientes",
            "due_date": seven_days_ago.strftime("%Y-%m-%d"),
            "priority": "high",
            "days_overdue": 7
        })
    
    # Alertas de trabajadores sin capacitación
    workers_without_training = db.query(Worker).outerjoin(
        User, Worker.user_id == User.id
    ).outerjoin(
        Enrollment, User.id == Enrollment.user_id
    ).filter(
        Worker.is_active == True,
        Enrollment.id.is_(None)
    ).count()
    
    if workers_without_training > 0:
        alerts.append({
            "id": "workers_without_training",
            "employee_name": f"{workers_without_training} trabajadores",
            "training_name": "Sin capacitación asignada",
            "due_date": datetime.utcnow().strftime("%Y-%m-%d"),
            "priority": "low",
            "days_overdue": 0
        })
    
    return alerts[:5]  # Limitar a 5 alertas


def _get_compliance_data(db: Session) -> List[Dict[str, Any]]:
    """
    Obtener datos de cumplimiento por curso
    """
    # Obtener cursos con estadísticas de cumplimiento
    courses = db.query(Course).filter(
        Course.status == "published"
    ).limit(5).all()
    
    compliance_data = []
    for course in courses:
        total_enrollments = db.query(Enrollment).filter(
            Enrollment.course_id == course.id
        ).count()
        
        completed_enrollments = db.query(Enrollment).filter(
            Enrollment.course_id == course.id,
            Enrollment.status == EnrollmentStatus.COMPLETED
        ).count()
        
        compliance_percentage = (completed_enrollments / total_enrollments * 100) if total_enrollments > 0 else 0
        
        compliance_data.append({
            "course_id": course.id,
            "course_name": course.title,
            "total_enrolled": total_enrollments,
            "completed": completed_enrollments,
            "compliance_percentage": round(compliance_percentage, 1)
        })
    
    return compliance_data