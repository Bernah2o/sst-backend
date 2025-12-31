from typing import List, Dict, Any
import logging
from datetime import datetime

from sqlalchemy.orm import Session
from sqlalchemy import and_

from app.models.user import User
from app.models.course import Course
from app.models.enrollment import Enrollment, EnrollmentStatus
from app.models.survey import Survey, UserSurvey, UserSurveyStatus, SurveyStatus
from app.models.evaluation import Evaluation, UserEvaluation, UserEvaluationStatus
from app.services.email_service import EmailService
from app.config import settings

logger = logging.getLogger(__name__)

class CourseNotificationService:
    def __init__(self, db: Session):
        self.db = db

    def get_pending_items(self, enrollment: Enrollment) -> Dict[str, Any]:
        """
        Identify pending items for a given enrollment.
        Returns a dictionary with pending surveys, evaluations, modules, etc.
        """
        course = enrollment.course
        user = enrollment.user
        
        pending_items = {
            "surveys": [],
            "evaluations": [],
            "modules": [], # Can be expanded if module progress tracking is granular
            "materials": [],
            "is_pending": False
        }

        # Check if course is already completed
        if enrollment.status == EnrollmentStatus.COMPLETED.value:
            return pending_items

        # 1. Check Surveys
        required_surveys = self.db.query(Survey).filter(
            and_(
                Survey.course_id == course.id,
                Survey.required_for_completion == True,
                Survey.status == SurveyStatus.PUBLISHED
            )
        ).all()
        
        for survey in required_surveys:
            user_submission = self.db.query(UserSurvey).filter(
                and_(
                    UserSurvey.user_id == user.id,
                    UserSurvey.survey_id == survey.id,
                    UserSurvey.status == UserSurveyStatus.COMPLETED
                )
            ).first()
            
            if not user_submission:
                pending_items["surveys"].append({
                    "id": survey.id,
                    "title": survey.title
                })

        # 2. Check Evaluations
        # Logic: If all required surveys are done (or none required), check evaluations
        # Note: This logic depends on course rules. Assuming evaluations are always required if they exist.
        course_evaluations = self.db.query(Evaluation).filter(
            and_(
                Evaluation.course_id == course.id,
                Evaluation.status == "published"
            )
        ).all()
        
        for evaluation in course_evaluations:
            completed_evaluation = self.db.query(UserEvaluation).filter(
                and_(
                    UserEvaluation.user_id == user.id,
                    UserEvaluation.evaluation_id == evaluation.id,
                    UserEvaluation.status == UserEvaluationStatus.COMPLETED
                )
            ).first()
            
            if not completed_evaluation:
                pending_items["evaluations"].append({
                    "id": evaluation.id,
                    "title": evaluation.title
                })

        # 3. Check General Progress (Modules/Materials)
        # If progress < 100%, we consider it as "pending modules/materials"
        if enrollment.progress < 100:
             pending_items["modules"].append({
                 "title": f"Completar contenido del curso (Progreso actual: {enrollment.progress}%)"
             })

        if pending_items["surveys"] or pending_items["evaluations"] or pending_items["modules"]:
            pending_items["is_pending"] = True

        return pending_items

    def send_reminder(self, enrollment_id: int) -> bool:
        """
        Send a reminder email to the user for the given enrollment.
        """
        enrollment = self.db.query(Enrollment).filter(Enrollment.id == enrollment_id).first()
        if not enrollment:
            logger.error(f"Enrollment {enrollment_id} not found")
            return False

        user = enrollment.user
        if not user or not user.email:
            logger.warning(f"User {enrollment.user_id} has no email")
            return False

        pending = self.get_pending_items(enrollment)
        if not pending["is_pending"]:
            logger.info(f"No pending items for enrollment {enrollment_id}")
            return False

        # Construct Email Content
        subject = f"Recordatorio de Avance - Curso: {enrollment.course.title}"
        
        items_html = "<ul>"
        for item in pending["modules"]:
            items_html += f"<li>{item['title']}</li>"
        for item in pending["surveys"]:
            items_html += f"<li>Encuesta pendiente: {item['title']}</li>"
        for item in pending["evaluations"]:
            items_html += f"<li>Evaluación pendiente: {item['title']}</li>"
        items_html += "</ul>"

        html_content = f"""
        <!DOCTYPE html>
        <html>
        <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
            <div style="max-width: 600px; margin: 0 auto; padding: 20px;">
                <h2 style="color: #2c3e50;">Recordatorio de Curso Pendiente</h2>
                <p>Hola {user.first_name},</p>
                <p>Te recordamos que tienes actividades pendientes en el curso <strong>{enrollment.course.title}</strong>.</p>
                
                <h3>Actividades Pendientes:</h3>
                {items_html}
                
                <p>Por favor, ingresa a la plataforma para completar estas actividades lo antes posible.</p>
                
                <div style="text-align: center; margin: 30px 0;">
                    <a href="{settings.frontend_url}/my-courses" 
                       style="background-color: #3498db; color: white; padding: 12px 30px; 
                              text-decoration: none; border-radius: 5px; display: inline-block;">
                        Ir a mis Cursos
                    </a>
                </div>
            </div>
        </body>
        </html>
        """

        return EmailService.send_email(user.email, subject, html_content)

    def run_daily_course_reminders(self) -> Dict[str, int]:
        """
        Check all active enrollments and send reminders if items are pending.
        """
        logger.info("Starting daily course reminders check")
        stats = {"total_checked": 0, "reminders_sent": 0, "errors": 0}
        
        # Get all active enrollments
        active_enrollments = self.db.query(Enrollment).filter(
            Enrollment.status == EnrollmentStatus.ACTIVE.value
        ).all()
        
        stats["total_checked"] = len(active_enrollments)
        
        for enrollment in active_enrollments:
            try:
                # We can add logic here to avoid spamming (e.g. check last_reminder_date if added to model)
                # For now, we simply check pending items. 
                # Ideally, we should only send if it's been X days since start or last activity.
                
                if self.send_reminder(enrollment.id):
                    stats["reminders_sent"] += 1
            except Exception as e:
                logger.error(f"Error sending reminder for enrollment {enrollment.id}: {e}")
                stats["errors"] += 1
                
        logger.info(f"Daily course reminders completed: {stats}")
        return stats
