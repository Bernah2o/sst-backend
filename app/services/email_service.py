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
    def send_course_completion_email(to_email: str, user_name: str, course_title: str, score: float, passing_score: float):
        """Envía un correo de felicitaciones cuando el trabajador completa un curso y supera la calificación exigida."""
        try:
            subject = f"¡Felicitaciones por completar el curso: {course_title}!"

            html_content = f"""
            <!DOCTYPE html>
            <html>
            <head>
                <meta charset="UTF-8">
                <title>Curso Completado</title>
            </head>
            <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333; background-color: #f4f4f4; margin: 0; padding: 0;">
                <div style="max-width: 600px; margin: 30px auto; background-color: #ffffff; border-radius: 8px; overflow: hidden; box-shadow: 0 2px 8px rgba(0,0,0,0.1);">
                    <!-- Header -->
                    <div style="background-color: #1a73e8; padding: 30px 40px; text-align: center;">
                        <h1 style="color: #ffffff; margin: 0; font-size: 26px;">🎓 ¡Curso Completado!</h1>
                    </div>

                    <!-- Body -->
                    <div style="padding: 35px 40px;">
                        <p style="font-size: 16px;">Estimado/a <strong>{user_name}</strong>,</p>

                        <p style="font-size: 15px;">
                            Nos complace informarle que ha completado exitosamente el curso:
                        </p>

                        <div style="background-color: #e8f0fe; border-left: 4px solid #1a73e8; padding: 15px 20px; margin: 20px 0; border-radius: 4px;">
                            <p style="margin: 0; font-size: 18px; font-weight: bold; color: #1a73e8;">{course_title}</p>
                        </div>

                        <p style="font-size: 15px;">Ha obtenido una calificación de <strong>{score:.1f}%</strong>, superando el mínimo requerido de <strong>{passing_score:.1f}%</strong>.</p>

                        <p style="font-size: 15px;">
                            Este logro refleja su compromiso con el aprendizaje continuo y el cumplimiento de las normas de Seguridad y Salud en el Trabajo (SST).
                            Le instamos a seguir aplicando los conocimientos adquiridos en su labor diaria.
                        </p>

                        <p style="font-size: 15px;">¡Muchas felicitaciones por este importante logro!</p>
                    </div>

                    <!-- Footer -->
                    <div style="background-color: #f0f0f0; padding: 20px 40px; text-align: center; border-top: 1px solid #e0e0e0;">
                        <p style="font-size: 12px; color: #888; margin: 0;">
                            Este es un mensaje automático del Sistema de Gestión SST.<br>
                            Por favor, no responda a este correo.
                        </p>
                    </div>
                </div>
            </body>
            </html>
            """

            return EmailService.send_email(
                to_email,
                subject,
                html_content,
                cc=["bernardino.deaguas@gmail.com"]
            )
        except Exception as e:
            logging.error(f"Error al enviar correo de finalización de curso: {e}")
            return False

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
