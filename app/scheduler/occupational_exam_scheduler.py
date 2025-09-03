from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from datetime import datetime
import logging
import asyncio

from app.services.occupational_exam_notifications import run_daily_exam_notifications
from app.config import settings

logger = logging.getLogger(__name__)

class OccupationalExamScheduler:
    """Programador de tareas para notificaciones de exámenes ocupacionales"""
    
    def __init__(self):
        self.scheduler = AsyncIOScheduler()
        self.is_running = False
    
    async def daily_exam_notification_task(self):
        """Tarea diaria para enviar notificaciones de exámenes ocupacionales"""
        try:
            logger.info("Iniciando tarea diaria de notificaciones de exámenes ocupacionales")
            
            # Ejecutar en un hilo separado para evitar bloquear el scheduler
            loop = asyncio.get_event_loop()
            stats = await loop.run_in_executor(None, run_daily_exam_notifications)
            
            logger.info(f"Tarea diaria completada. Estadísticas: {stats}")
            
        except Exception as e:
            logger.error(f"Error en tarea diaria de notificaciones: {str(e)}")
    
    def start(self):
        """Iniciar el programador de tareas"""
        if self.is_running:
            logger.warning("El programador ya está en ejecución")
            return
        
        try:
            # Programar tarea diaria a las 8:00 AM
            self.scheduler.add_job(
                self.daily_exam_notification_task,
                trigger=CronTrigger(hour=8, minute=0),  # 8:00 AM todos los días
                id="daily_exam_notifications",
                name="Notificaciones diarias de exámenes ocupacionales",
                replace_existing=True,
                max_instances=1  # Solo una instancia a la vez
            )
            
            # También programar una verificación semanal los lunes a las 9:00 AM
            self.scheduler.add_job(
                self.weekly_exam_summary_task,
                trigger=CronTrigger(day_of_week=0, hour=9, minute=0),  # Lunes a las 9:00 AM
                id="weekly_exam_summary",
                name="Resumen semanal de exámenes ocupacionales",
                replace_existing=True,
                max_instances=1
            )
            
            self.scheduler.start()
            self.is_running = True
            logger.info("Programador de exámenes ocupacionales iniciado")
            
        except Exception as e:
            logger.error(f"Error iniciando programador: {str(e)}")
    
    def stop(self):
        """Detener el programador de tareas"""
        if not self.is_running:
            logger.warning("El programador no está en ejecución")
            return
        
        try:
            self.scheduler.shutdown()
            self.is_running = False
            logger.info("Programador de exámenes ocupacionales detenido")
            
        except Exception as e:
            logger.error(f"Error deteniendo programador: {str(e)}")
    
    async def weekly_exam_summary_task(self):
        """Tarea semanal para enviar resumen de exámenes ocupacionales"""
        try:
            logger.info("Iniciando tarea semanal de resumen de exámenes ocupacionales")
            
            from app.database import get_db
            from app.services.occupational_exam_notifications import OccupationalExamNotificationService
            
            db = next(get_db())
            try:
                service = OccupationalExamNotificationService(db)
                stats = service.get_exam_statistics()
                
                # Aquí podrías enviar un correo de resumen a los administradores
                logger.info(f"Estadísticas semanales de exámenes: {stats}")
                
                # TODO: Implementar envío de correo de resumen a administradores
                
            finally:
                db.close()
            
        except Exception as e:
            logger.error(f"Error en tarea semanal de resumen: {str(e)}")
    
    def get_status(self):
        """Obtener estado del programador"""
        jobs = []
        if self.is_running:
            for job in self.scheduler.get_jobs():
                jobs.append({
                    "id": job.id,
                    "name": job.name,
                    "next_run": job.next_run_time.isoformat() if job.next_run_time else None,
                    "trigger": str(job.trigger)
                })
        
        return {
            "is_running": self.is_running,
            "jobs": jobs,
            "scheduler_state": self.scheduler.state if hasattr(self.scheduler, 'state') else None
        }
    
    async def run_manual_check(self):
        """Ejecutar verificación manual de notificaciones"""
        logger.info("Ejecutando verificación manual de notificaciones")
        await self.daily_exam_notification_task()


# Instancia global del programador
occupational_exam_scheduler = OccupationalExamScheduler()


def start_occupational_exam_scheduler():
    """Función para iniciar el programador desde la aplicación principal"""
    occupational_exam_scheduler.start()


def stop_occupational_exam_scheduler():
    """Función para detener el programador"""
    occupational_exam_scheduler.stop()


def get_occupational_exam_scheduler_status():
    """Función para obtener el estado del programador"""
    return occupational_exam_scheduler.get_status()


async def run_manual_occupational_exam_check():
    """Función para ejecutar verificación manual"""
    await occupational_exam_scheduler.run_manual_check()