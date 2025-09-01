
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
                # server.set_debuglevel(1) # Debug disabled for production
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
