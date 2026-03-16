"""
Tests de envío de las plantillas de correo mejoradas.

Ejecución rápida (sin cobertura):
    pytest tests/test_email_templates.py -m email --override-ini="addopts=-ra -v --tb=short -p no:warnings"

Ejecución individual de un test:
    pytest tests/test_email_templates.py::TestEmailTemplates::test_birthday_greeting -m email --override-ini="addopts=-ra -v --tb=short -p no:warnings"
"""
import pytest
from datetime import date, datetime
from pathlib import Path
from jinja2 import Environment, FileSystemLoader

from app.config import settings
from app.services.email_service import EmailService

# ─── Destinatario de prueba ────────────────────────────────────────────────────
TEST_RECIPIENT = "bernardino.deaguas@gmail.com"
CC_RECIPIENT   = ["bernardino.deaguas@gmail.com"]

# ─── Jinja2 sobre la carpeta de plantillas ────────────────────────────────────
TEMPLATES_DIR = Path(__file__).parent.parent / "app" / "templates" / "emails"
jinja_env = Environment(loader=FileSystemLoader(str(TEMPLATES_DIR)))


def render(template_name: str, context: dict) -> str:
    """Renderiza una plantilla Jinja2 y devuelve el HTML resultante."""
    tpl = jinja_env.get_template(f"{template_name}.html")
    return tpl.render(**context)


def smtp_available() -> bool:
    """Devuelve True si la configuración SMTP está completa."""
    return all([
        settings.smtp_host,
        settings.smtp_username,
        settings.smtp_password,
        settings.email_from,
    ])


# ─── Saltar todos los tests si no hay SMTP configurado ────────────────────────
pytestmark = [
    pytest.mark.email,
    pytest.mark.skipif(
        not smtp_available(),
        reason="SMTP no configurado (SMTP_HOST / SMTP_USERNAME / SMTP_PASSWORD / EMAIL_FROM)"
    ),
]


class TestEmailTemplates:
    """Tests de envío real de las tres plantillas mejoradas."""

    # ── 1. Cumpleaños ─────────────────────────────────────────────────────────
    def test_birthday_greeting(self):
        """Plantilla birthday_greeting.html — felicitación de cumpleaños."""
        context = {
            "worker_name": "María García",
            "contact_email": settings.email_from,
        }
        html = render("birthday_greeting", context)
        assert "María García" in html, "El nombre del trabajador no aparece en el HTML"
        assert "Feliz Cumpleaños" in html

        success = EmailService.send_email(
            to_email=TEST_RECIPIENT,
            subject="[TEST] 🎂 Cumpleaños — Plantilla mejorada",
            message_html=html,
            cc=CC_RECIPIENT,
        )
        assert success, "El correo de cumpleaños no se pudo enviar"

    # ── 2. Reinducción — aviso estándar ───────────────────────────────────────
    def test_reinduction_standard(self):
        """Plantilla reinduction_notification.html — recordatorio estándar (> 7 días)."""
        context = {
            "worker_name": "Carlos Rodríguez",
            "notification_type": "reminder",
            "is_overdue": False,
            "year": date.today().year,
            "due_date": "30/06/2026",
            "days_left": 30,
            "course_name": "Reinducción Anual SST 2026",
            "system_url": settings.frontend_url or "http://localhost:3000",
        }
        html = render("reinduction_notification", context)
        assert "Carlos Rodríguez" in html
        assert "30" in html  # días restantes

        success = EmailService.send_email(
            to_email=TEST_RECIPIENT,
            subject="[TEST] 📚 Reinducción estándar — Plantilla mejorada",
            message_html=html,
            cc=CC_RECIPIENT,
        )
        assert success, "El correo de reinducción estándar no se pudo enviar"

    def test_reinduction_urgent(self):
        """Plantilla reinduction_notification.html — recordatorio urgente (≤ 7 días)."""
        context = {
            "worker_name": "Pedro Martínez",
            "notification_type": "reminder",
            "is_overdue": False,
            "year": date.today().year,
            "due_date": "20/03/2026",
            "days_left": 5,
            "course_name": "Reinducción Anual SST 2026",
            "system_url": settings.frontend_url or "http://localhost:3000",
        }
        html = render("reinduction_notification", context)
        assert "Pedro Martínez" in html

        success = EmailService.send_email(
            to_email=TEST_RECIPIENT,
            subject="[TEST] ⚠️ Reinducción urgente (5 días) — Plantilla mejorada",
            message_html=html,
            cc=CC_RECIPIENT,
        )
        assert success, "El correo de reinducción urgente no se pudo enviar"

    def test_reinduction_overdue(self):
        """Plantilla reinduction_notification.html — reinducción vencida."""
        context = {
            "worker_name": "Ana López",
            "notification_type": "reminder",
            "is_overdue": True,
            "year": date.today().year - 1,
            "due_date": "31/12/2025",
            "days_left": -45,
            "course_name": "Reinducción Anual SST 2025",
            "system_url": settings.frontend_url or "http://localhost:3000",
        }
        html = render("reinduction_notification", context)
        assert "Ana López" in html

        success = EmailService.send_email(
            to_email=TEST_RECIPIENT,
            subject="[TEST] 🔴 Reinducción VENCIDA — Plantilla mejorada",
            message_html=html,
            cc=CC_RECIPIENT,
        )
        assert success, "El correo de reinducción vencida no se pudo enviar"

    def test_reinduction_anniversary(self):
        """Plantilla reinduction_notification.html — aniversario laboral."""
        context = {
            "worker_name": "Luis Herrera",
            "notification_type": "anniversary",
            "years_in_company": 5,
            "anniversary_date": date.today().strftime("%d/%m/%Y"),
            "is_overdue": False,
            "year": date.today().year,
            "due_date": "31/12/2026",
            "days_left": 90,
            "course_name": "Reinducción Anual SST 2026",
            "system_url": settings.frontend_url or "http://localhost:3000",
        }
        html = render("reinduction_notification", context)
        assert "Luis Herrera" in html
        assert "5" in html  # años en la empresa

        success = EmailService.send_email(
            to_email=TEST_RECIPIENT,
            subject="[TEST] 🎉 Reinducción aniversario — Plantilla mejorada",
            message_html=html,
            cc=CC_RECIPIENT,
        )
        assert success, "El correo de reinducción por aniversario no se pudo enviar"

    # ── 3. Examen ocupacional — próximo ───────────────────────────────────────
    def test_occupational_exam_upcoming(self):
        """Plantilla occupational_exam_reminder.html — examen próximo (> 7 días)."""
        context = {
            "worker_name": "Sofía Castro",
            "worker_full_name": "Sofía Castro Mejía",
            "worker_document": "1.098.765.432",
            "worker_position": "Operaria de Producción",
            "exam_type_label": "Examen Periódico",
            "exam_date": "15/04/2026",
            "periodicidad": "Anual",
            "last_exam_date": "15/04/2025",
            "days_until_exam": 30,
            "status": "proximo_a_vencer",
            "urgency": "RECORDATORIO",
            "current_date": datetime.now().strftime("%d/%m/%Y"),
            "current_time": datetime.now().strftime("%H:%M:%S"),
            "system_url": settings.frontend_url or "http://localhost:3000",
            "contact_email": settings.email_from,
            "api_base_url": settings.backend_url or None,
            "exam_id": 99,
            "worker_id": 1,
        }
        html = render("occupational_exam_reminder", context)
        assert "Sofía Castro" in html
        assert "30" in html

        success = EmailService.send_email(
            to_email=TEST_RECIPIENT,
            subject="[TEST] 📋 Examen ocupacional próximo (30 días) — Plantilla mejorada",
            message_html=html,
            cc=CC_RECIPIENT,
        )
        assert success, "El correo de examen próximo no se pudo enviar"

    def test_occupational_exam_urgent(self):
        """Plantilla occupational_exam_reminder.html — examen urgente (≤ 7 días)."""
        context = {
            "worker_name": "Jorge Vargas",
            "worker_full_name": "Jorge Vargas Pineda",
            "worker_document": "80.234.567",
            "worker_position": "Técnico Electricista",
            "exam_type_label": "Examen Periódico",
            "exam_date": datetime.now().strftime("%d/%m/%Y"),
            "periodicidad": "Semestral",
            "last_exam_date": "10/09/2025",
            "days_until_exam": 3,
            "status": "proximo_a_vencer",
            "urgency": "URGENTE",
            "current_date": datetime.now().strftime("%d/%m/%Y"),
            "current_time": datetime.now().strftime("%H:%M:%S"),
            "system_url": settings.frontend_url or "http://localhost:3000",
            "contact_email": settings.email_from,
            "api_base_url": settings.backend_url or None,
            "exam_id": 100,
            "worker_id": 2,
        }
        html = render("occupational_exam_reminder", context)
        assert "Jorge Vargas" in html

        success = EmailService.send_email(
            to_email=TEST_RECIPIENT,
            subject="[TEST] ⚠️ Examen ocupacional URGENTE (3 días) — Plantilla mejorada",
            message_html=html,
            cc=CC_RECIPIENT,
        )
        assert success, "El correo de examen urgente no se pudo enviar"

    def test_occupational_exam_overdue(self):
        """Plantilla occupational_exam_reminder.html — examen vencido."""
        context = {
            "worker_name": "Diana Torres",
            "worker_full_name": "Diana Torres Salcedo",
            "worker_document": "52.876.543",
            "worker_position": "Auxiliar de Bodega",
            "exam_type_label": "Examen Periódico",
            "exam_date": "01/01/2026",
            "periodicidad": "Anual",
            "last_exam_date": "01/01/2025",
            "days_until_exam": -74,
            "status": "vencido",
            "urgency": "INMEDIATO",
            "current_date": datetime.now().strftime("%d/%m/%Y"),
            "current_time": datetime.now().strftime("%H:%M:%S"),
            "system_url": settings.frontend_url or "http://localhost:3000",
            "contact_email": settings.email_from,
            "api_base_url": settings.backend_url or None,
            "exam_id": 101,
            "worker_id": 3,
        }
        html = render("occupational_exam_reminder", context)
        assert "Diana Torres" in html
        assert "VENCIDO" in html

        success = EmailService.send_email(
            to_email=TEST_RECIPIENT,
            subject="[TEST] 🚨 Examen ocupacional VENCIDO — Plantilla mejorada",
            message_html=html,
            cc=CC_RECIPIENT,
        )
        assert success, "El correo de examen vencido no se pudo enviar"

    # ── 4. Test de conexión SMTP ───────────────────────────────────────────────
    def test_smtp_connection(self):
        """Verifica que la conexión SMTP está operativa."""
        result = EmailService.test_smtp_connection()
        assert result is True, (
            f"No se puede conectar al servidor SMTP "
            f"{settings.smtp_host}:{settings.smtp_port}"
        )
