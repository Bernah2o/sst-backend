import os
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
            if settings.email_use_ssl:
                with smtplib.SMTP_SSL(settings.smtp_host, settings.smtp_port, context=context) as server:
                    # server.set_debuglevel(1) # Debug disabled for production
                    server.login(settings.smtp_username, settings.smtp_password)
            else:
                with smtplib.SMTP(settings.smtp_host, settings.smtp_port) as server:
                    # server.set_debuglevel(1) # Debug disabled for production
                    if settings.email_use_tls:
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
            if settings.email_use_ssl:
                with smtplib.SMTP_SSL(settings.smtp_host, settings.smtp_port, context=context) as server:
                    server.login(settings.smtp_username, settings.smtp_password)
                    recipients = [to_email]
                    if cc:
                        recipients.extend(cc)
                    server.sendmail(settings.email_from, recipients, msg.as_string())
            else:
                with smtplib.SMTP(settings.smtp_host, settings.smtp_port) as server:
                    if settings.email_use_tls:
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

    @staticmethod
    def send_password_reset_email(to_email: str, reset_token: str, user_name: str):
        """Envía un correo de recuperación de contraseña."""
        subject = "Recuperación de Contraseña - Sistema SST"
        
        # URL del frontend para reset de contraseña
        reset_url = f"{settings.frontend_url}/reset-password?token={reset_token}"
        
        html_content = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <title>Recuperación de Contraseña</title>
        </head>
        <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
            <div style="max-width: 600px; margin: 0 auto; padding: 20px;">
                <h2 style="color: #2c3e50;">Recuperación de Contraseña</h2>
                
                <p>Hola {user_name},</p>
                
                <p>Hemos recibido una solicitud para restablecer la contraseña de tu cuenta en el Sistema SST.</p>
                
                <p>Para restablecer tu contraseña, haz clic en el siguiente enlace:</p>
                
                <div style="text-align: center; margin: 30px 0;">
                    <a href="{reset_url}" 
                       style="background-color: #3498db; color: white; padding: 12px 30px; 
                              text-decoration: none; border-radius: 5px; display: inline-block;">
                        Restablecer Contraseña
                    </a>
                </div>
                
                <p><strong>Este enlace expirará en 1 hora por motivos de seguridad.</strong></p>
                
                <p>Si no solicitaste este cambio, puedes ignorar este correo. Tu contraseña permanecerá sin cambios.</p>
                
                <hr style="border: none; border-top: 1px solid #eee; margin: 30px 0;">
                
                <p style="font-size: 12px; color: #666;">
                    Si tienes problemas con el enlace, copia y pega la siguiente URL en tu navegador:<br>
                    {reset_url}
                </p>
                
                <p style="font-size: 12px; color: #666;">
                    Este es un correo automático, por favor no respondas a este mensaje.
                </p>
            </div>
        </body>
        </html>
        """
        
        return EmailService.send_email(to_email, subject, html_content)
    @staticmethod
    def send_homework_reminder(to_email: str, user_name: str, due_date: str = "Lo antes posible"):
        """Envía un recordatorio para la autoevaluación de trabajo en casa."""
        try:
            subject = "Recordatorio: Autoevaluación de Trabajo en Casa Pendiente - SST"
            
            # Cargar template
            template_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "templates", "emails", "homework_reminder.html")
            
            with open(template_path, "r", encoding="utf-8") as f:
                template_content = f.read()
            
            # Reemplazar variables
            action_url = f"{settings.frontend_url}/employee/homework-assessments"
            
            html_content = template_content.replace("{{ user_name }}", user_name)                                            .replace("{{ due_date }}", due_date)                                            .replace("{{ action_url }}", action_url)
            
            return EmailService.send_email(to_email, subject, html_content)
        except Exception as e:
            logging.error(f"Error al enviar recordatorio de autoevaluación: {e}")
            return False
