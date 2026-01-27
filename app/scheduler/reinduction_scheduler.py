from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from datetime import datetime
from sqlalchemy.orm import sessionmaker

from app.database import engine
from app.services.reinduction_service import ReinductionService
from app.utils.scheduler_settings import is_scheduler_enabled
from app.models.admin_config import SystemSettings

# Crear session factory
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Scheduler global
scheduler = None


def run_daily_reinduction_check():
    """Función que ejecuta la verificación diaria de reinducciones"""
    db = SessionLocal()
    try:
        # Verificar si el scheduler está habilitado
        if not is_scheduler_enabled(db, SystemSettings.REINDUCTION_SCHEDULER_ENABLED):
            print("Scheduler de reinducciones deshabilitado por administrador. No se ejecutará.")
            return {"status": "disabled", "message": "Scheduler deshabilitado por administrador"}

        print("Iniciando verificación diaria de reinducciones")

        service = ReinductionService(db)
        results = service.run_daily_check()

        print(f"Verificación diaria completada: {results}")
        return results

    except Exception as e:
        print(f"Error en verificación diaria de reinducciones: {str(e)}")
        db.rollback()
        return {"status": "error", "message": str(e)}
    finally:
        db.close()


def start_scheduler():
    """Inicia el scheduler de reinducciones"""
    global scheduler
    
    if scheduler is not None:
        print("El scheduler ya está iniciado")
        return
    
    try:
        scheduler = BackgroundScheduler(
            timezone='America/Bogota',  # Zona horaria de Colombia
            job_defaults={
                'coalesce': False,
                'max_instances': 1,
                'misfire_grace_time': 300  # 5 minutos de gracia
            }
        )
        
        # Programar verificación diaria a las 8:00 AM
        scheduler.add_job(
            func=run_daily_reinduction_check,
            trigger=CronTrigger(hour=8, minute=0),
            id='daily_reinduction_check',
            name='Verificación Diaria de Reinducciones',
            replace_existing=True
        )
        
        # Programar verificación semanal adicional los lunes a las 9:00 AM
        scheduler.add_job(
            func=run_daily_reinduction_check,
            trigger=CronTrigger(day_of_week='mon', hour=9, minute=0),
            id='weekly_reinduction_check',
            name='Verificación Semanal de Reinducciones',
            replace_existing=True
        )
        
        scheduler.start()
        print("Scheduler de reinducciones iniciado exitosamente")
        
        # Log de trabajos programados
        jobs = scheduler.get_jobs()
        for job in jobs:
            print(f"Trabajo programado: {job.name} - Próxima ejecución: {job.next_run_time}")
            
    except Exception as e:
        print(f"Error iniciando scheduler de reinducciones: {str(e)}")
        raise


def stop_scheduler():
    """Detiene el scheduler de reinducciones"""
    global scheduler
    
    if scheduler is None:
        print("El scheduler no está iniciado")
        return
    
    try:
        scheduler.shutdown(wait=True)
        scheduler = None
        print("Scheduler de reinducciones detenido exitosamente")
    except Exception as e:
        print(f"Error deteniendo scheduler de reinducciones: {str(e)}")


def get_scheduler_status():
    """Obtiene el estado del scheduler"""
    global scheduler
    
    if scheduler is None:
        return {
            "running": False,
            "jobs": [],
            "message": "Scheduler no iniciado"
        }
    
    jobs_info = []
    for job in scheduler.get_jobs():
        jobs_info.append({
            "id": job.id,
            "name": job.name,
            "next_run_time": job.next_run_time.isoformat() if job.next_run_time else None,
            "trigger": str(job.trigger)
        })
    
    return {
        "running": scheduler.running,
        "jobs": jobs_info,
        "message": "Scheduler activo" if scheduler.running else "Scheduler detenido"
    }


def run_manual_check():
    """Ejecuta una verificación manual inmediata"""
    try:
        print("Ejecutando verificación manual de reinducciones")
        run_daily_reinduction_check()
        return {"success": True, "message": "Verificación manual completada"}
    except Exception as e:
        print(f"Error en verificación manual: {str(e)}")
        return {"success": False, "message": f"Error: {str(e)}"}


def add_custom_job(func, trigger_config, job_id, job_name):
    """Agrega un trabajo personalizado al scheduler"""
    global scheduler
    
    if scheduler is None:
        raise RuntimeError("El scheduler no está iniciado")
    
    try:
        scheduler.add_job(
            func=func,
            trigger=CronTrigger(**trigger_config),
            id=job_id,
            name=job_name,
            replace_existing=True
        )
        print(f"Trabajo personalizado agregado: {job_name}")
        return True
    except Exception as e:
        print(f"Error agregando trabajo personalizado: {str(e)}")
        return False


def remove_job(job_id):
    """Remueve un trabajo del scheduler"""
    global scheduler
    
    if scheduler is None:
        raise RuntimeError("El scheduler no está iniciado")
    
    try:
        scheduler.remove_job(job_id)
        print(f"Trabajo removido: {job_id}")
        return True
    except Exception as e:
        print(f"Error removiendo trabajo: {str(e)}")
        return False