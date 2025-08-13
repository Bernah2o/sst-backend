
import smtplib
import ssl
import logging
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from app.config import settings

class EmailService:
    @staticmethod
    def test_smtp_connection():
        """Prueba la conexión y autenticación con el servidor SMTP."""
        try:
            context = ssl.create_default_context()
            with smtplib.SMTP(settings.smtp_host, settings.smtp_port) as server:
                server.set_debuglevel(1) # Muestra la comunicación detallada
                server.starttls(context=context)
                server.login(settings.smtp_username, settings.smtp_password)
            return True
        except Exception as e:
            logging.error(f"Error en conexión SMTP: {e}")
            return False

    @staticmethod
    def send_email(to_email: str, subject: str, message_html: str, cc: list = None):
        """Envía un correo electrónico."""
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = settings.email_from
        msg["To"] = to_email
        
        if cc:
            msg["Cc"] = ", ".join(cc)

        # Adjuntar la parte HTML
        part = MIMEText(message_html, "html")
        msg.attach(part)

        try:
            context = ssl.create_default_context()
            with smtplib.SMTP(settings.smtp_host, settings.smtp_port) as server:
                server.starttls(context=context)
                server.login(settings.smtp_username, settings.smtp_password)
                recipients = [to_email]
                if cc:
                    recipients.extend(cc)
                server.sendmail(settings.email_from, recipients, msg.as_string())
            return True
        except Exception as e:
            logging.error(f"Error al enviar correo: {e}")
            return False
