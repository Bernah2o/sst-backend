from typing import Dict, List, Optional, Any
from pathlib import Path
import os
from jinja2 import Environment, FileSystemLoader

from app.config import settings
from app.services.email_service import EmailService

# Configurar Jinja2 para las plantillas de correo
templates_dir = Path(__file__).parent.parent / "templates" / "emails"
templates_dir.mkdir(parents=True, exist_ok=True)
env = Environment(loader=FileSystemLoader(str(templates_dir)))


def send_email(
    recipient: str,
    subject: str,
    body: str = "",
    template: Optional[str] = None,
    context: Dict[str, Any] = None,
    cc: Optional[List[str]] = None
) -> bool:
    """
    Envía un correo electrónico utilizando el servicio de correo configurado
    
    Args:
        recipient: Dirección de correo del destinatario
        subject: Asunto del correo
        body: Cuerpo del mensaje (texto plano, opcional si se usa template)
        template: Nombre de la plantilla a utilizar (sin extensión)
        context: Contexto para renderizar la plantilla
        cc: Lista de direcciones en copia
        
    Returns:
        bool: True si el correo se envió correctamente, False en caso contrario
    """
    try:
        # Si se especifica una plantilla, renderizarla
        if template:
            try:
                template_file = f"{template}.html"
                template_obj = env.get_template(template_file)
                
                # Verificar si existe un archivo CSS correspondiente en la carpeta de reportes
                css_content = ""
                css_file_path = Path(__file__).parent.parent / "templates" / "reports" / "css" / f"{template}.css"
                
                if css_file_path.exists():
                    with open(css_file_path, "r", encoding="utf-8") as css_file:
                        css_content = css_file.read()
                    
                    # Agregar el CSS al contexto para que pueda ser utilizado en la plantilla
                    if context is None:
                        context = {}
                    context["external_css"] = css_content
                
                html_content = template_obj.render(**(context or {}))
            except Exception as e:
                print(f"Error al renderizar la plantilla de correo {template}: {str(e)}")
                # Si falla la plantilla, usar el cuerpo de texto plano
                html_content = body or f"<p>{subject}</p>"
        else:
            # Si no hay plantilla, convertir el cuerpo a HTML básico
            html_content = body or f"<p>{subject}</p>"
        
        # Enviar el correo
        return EmailService.send_email(
            to_email=recipient,
            subject=subject,
            message_html=html_content,
            cc=cc
        )
    except Exception as e:
        print(f"Error al enviar correo a {recipient}: {str(e)}")
        return False