from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from datetime import date
from sqlalchemy.orm import sessionmaker
from sqlalchemy import and_

from app.database import engine
from app.models.worker import Worker
from app.utils.email import send_email
from app.config import settings
from app.utils.scheduler_settings import is_scheduler_enabled
from app.models.admin_config import SystemSettings


# Crear session factory
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Scheduler global
scheduler = None


def run_daily_birthday_greetings():
    """Envía correos de cumpleaños a los trabajadores que cumplen hoy"""
    db = SessionLocal()
    try:
        # Verificar si el scheduler está habilitado
        if not is_scheduler_enabled(db, SystemSettings.BIRTHDAY_SCHEDULER_ENABLED):
            print("Scheduler de cumpleaños deshabilitado por administrador. No se ejecutará.")
            return {"status": "disabled", "message": "Scheduler deshabilitado por administrador"}

        today = date.today()
        print(f"Iniciando saludo de cumpleaños diario para {today.strftime('%d/%m')}…")

        # Buscar trabajadores activos con email cuyo cumpleaños (día/mes) sea hoy
        workers = db.query(Worker).filter(
            and_(
                Worker.is_active == True,
                Worker.email.isnot(None),
                Worker.email != "",
                Worker.birth_date.isnot(None)
            )
        ).all()

        count_total = 0
        count_sent = 0
        count_failed = 0

        for w in workers:
            if not w.birth_date:
                continue
            if w.birth_date.month == today.month and w.birth_date.day == today.day:
                count_total += 1

                context = {
                    "worker_name": w.full_name,
                    "system_url": getattr(settings, "react_app_api_url", None),
                    "contact_email": getattr(settings, "SUPPORT_EMAIL", None),
                }

                subject = "🎉 ¡Feliz Cumpleaños! – SST Bernardino de Aguas"

                try:
                    success = send_email(
                        recipient=w.email,
                        subject=subject,
                        template="birthday_greeting",
                        context=context,
                        cc=["bernardino.deaguas@gmail.com"]
                    )
                    if success:
                        count_sent += 1
                        print(f"Cumpleaños: correo enviado a {w.email} ({w.full_name})")
                    else:
                        count_failed += 1
                        print(f"Cumpleaños: error enviando a {w.email} ({w.full_name})")
                except Exception as e:
                    count_failed += 1
                    print(f"Cumpleaños: excepción enviando a {w.email}: {str(e)}")

        print(f"Saludos de cumpleaños: total={count_total}, enviados={count_sent}, fallidos={count_failed}")
        return {"total": count_total, "sent": count_sent, "failed": count_failed}
    finally:
        db.close()


def start_birthday_scheduler():
    """Inicia el scheduler de saludos de cumpleaños"""
    global scheduler

    if scheduler is not None:
        print("El scheduler de cumpleaños ya está iniciado")
        return

    try:
        scheduler = BackgroundScheduler(
            timezone='America/Bogota',
            job_defaults={
                'coalesce': False,
                'max_instances': 1,
                'misfire_grace_time': 300
            }
        )

        # Programar saludo diario a las 8:10 AM
        scheduler.add_job(
            func=run_daily_birthday_greetings,
            trigger=CronTrigger(hour=8, minute=10),
            id='daily_birthday_greetings',
            name='Saludos Diarios de Cumpleaños',
            replace_existing=True
        )

        scheduler.start()
        print("Scheduler de cumpleaños iniciado exitosamente")

        for job in scheduler.get_jobs():
            print(f"Trabajo programado: {job.name} - Próxima ejecución: {job.next_run_time}")
    except Exception as e:
        print(f"Error iniciando scheduler de cumpleaños: {str(e)}")
        raise


def stop_birthday_scheduler():
    """Detiene el scheduler de saludos de cumpleaños"""
    global scheduler
    if scheduler is None:
        print("El scheduler de cumpleaños no está iniciado")
        return
    try:
        scheduler.shutdown(wait=True)
        scheduler = None
        print("Scheduler de cumpleaños detenido exitosamente")
    except Exception as e:
        print(f"Error deteniendo scheduler de cumpleaños: {str(e)}")


def get_birthday_scheduler_status():
    """Obtiene el estado del scheduler de cumpleaños"""
    global scheduler
    if scheduler is None:
        return {"running": False, "jobs": [], "message": "Scheduler de cumpleaños no iniciado"}

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
        "message": "Scheduler de cumpleaños activo" if scheduler.running else "Scheduler de cumpleaños detenido"
    }


def run_manual_birthday_check():
    """Ejecuta una verificación manual inmediata de cumpleaños"""
    try:
        print("Ejecutando verificación manual de cumpleaños")
        return run_daily_birthday_greetings()
    except Exception as e:
        print(f"Error en verificación manual de cumpleaños: {str(e)}")
        return {"success": False, "message": f"Error: {str(e)}"}

