from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
import logging
import asyncio

from app.services.course_notifications import CourseNotificationService
from app.database import get_db
from app.utils.scheduler_settings import is_scheduler_enabled
from app.models.admin_config import SystemSettings

logger = logging.getLogger(__name__)

class CourseReminderScheduler:
    """Programador de tareas para recordatorios de cursos"""
    
    def __init__(self):
        self.scheduler = AsyncIOScheduler()
        self.is_running = False
    
    async def daily_course_reminder_task(self):
        """Tarea diaria para enviar recordatorios de cursos"""
        try:
            logger.info("Iniciando tarea diaria de recordatorios de cursos")

            # Use a fresh DB session
            db = next(get_db())
            try:
                # Verificar si el scheduler está habilitado
                if not is_scheduler_enabled(db, SystemSettings.COURSE_REMINDER_SCHEDULER_ENABLED):
                    logger.info("Scheduler de recordatorios de cursos deshabilitado por administrador. No se ejecutará.")
                    return {"status": "disabled", "message": "Scheduler deshabilitado por administrador"}

                service = CourseNotificationService(db)
                # Run in executor if it's blocking (email sending is blocking)
                loop = asyncio.get_event_loop()
                stats = await loop.run_in_executor(None, service.run_daily_course_reminders)
                logger.info(f"Tarea diaria de recordatorios completada. Estadísticas: {stats}")
                return stats
            finally:
                db.close()

        except Exception as e:
            logger.error(f"Error en tarea diaria de recordatorios: {str(e)}")
            return {"status": "error", "message": str(e)}
    
    def start(self):
        """Iniciar el programador de tareas"""
        if self.is_running:
            return
        
        try:
            # Programar tarea diaria a las 7:00 AM
            self.scheduler.add_job(
                self.daily_course_reminder_task,
                trigger=CronTrigger(hour=7, minute=0),
                id="daily_course_reminders",
                name="Recordatorios diarios de cursos",
                replace_existing=True,
                max_instances=1
            )
            
            self.scheduler.start()
            self.is_running = True
            logger.info("Programador de recordatorios de cursos iniciado")
            
        except Exception as e:
            logger.error(f"Error iniciando programador de recordatorios: {str(e)}")
    
    def stop(self):
        """Detener el programador de tareas"""
        if not self.is_running:
            return
        
        try:
            self.scheduler.shutdown()
            self.is_running = False
            logger.info("Programador de recordatorios de cursos detenido")
        except Exception as e:
            logger.error(f"Error deteniendo programador: {str(e)}")

# Instancia global
course_reminder_scheduler = CourseReminderScheduler()

def start_course_reminder_scheduler():
    course_reminder_scheduler.start()

def stop_course_reminder_scheduler():
    course_reminder_scheduler.stop()
