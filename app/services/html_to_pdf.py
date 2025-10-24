import os
import jinja2
import base64
import tempfile
import io
import logging
import gc
import threading
from datetime import datetime
from pathlib import Path
from functools import lru_cache
from typing import Optional, Dict, Any, List

import weasyprint

# Configurar logging para debug
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class HTMLToPDFConverter:
    def prepare_attendance_context(self, session_obj, attendees_list):
        """
        Prepara y valida el contexto para la plantilla de lista de asistencia.
        Args:
            session_obj: Objeto o dict de sesión (debe contener los campos requeridos)
            attendees_list: Lista de objetos o dicts de asistentes
        Returns:
            context: dict listo para renderizar la plantilla
        Raises:
            ValueError si falta algún campo requerido
        """
        # Validar y extraer campos de sesión
        required_session_fields = [
            "title",
            "session_date",
            "course_title",
            "location",
            "duration",
            "attendance_percentage",
        ]
        session = {}
        for field in required_session_fields:
            value = (
                getattr(session_obj, field, None)
                if not isinstance(session_obj, dict)
                else session_obj.get(field)
            )
            if value is None:
                raise ValueError(f"Falta el campo '{field}' en session para el PDF")
            session[field] = value
        # Validar y transformar asistentes
        attendees = []
        for idx, att in enumerate(attendees_list):
            attendee = {}
            for key in ["name", "document", "position", "area"]:
                value = (
                    getattr(att, key, None)
                    if not isinstance(att, dict)
                    else att.get(key)
                )
                if value is None:
                    raise ValueError(
                        f"Falta el campo '{key}' en attendee #{idx+1} para el PDF"
                    )
                attendee[key] = value
            attendees.append(attendee)
        return {"session": session, "attendees": attendees}

    def __init__(self, template_dir=None):
        """
        Inicializa el convertidor de HTML a PDF.

        Args:
            template_dir: Directorio donde se encuentran las plantillas HTML.
        """
        if template_dir is None:
            # Usar el directorio de plantillas por defecto
            base_dir = Path(__file__).resolve().parent.parent
            self.template_dir = os.path.join(base_dir, "templates", "reports")
        else:
            self.template_dir = template_dir

        # Verificar que el directorio existe
        if not os.path.exists(self.template_dir):
            os.makedirs(self.template_dir, exist_ok=True)
            logger.warning(f"Directorio de plantillas creado: {self.template_dir}")

        # Configurar el entorno de Jinja2
        self.env = jinja2.Environment(
            loader=jinja2.FileSystemLoader(self.template_dir),
            autoescape=jinja2.select_autoescape(["html", "xml"]),
        )
        
        # Cache para recursos reutilizables
        self._logo_cache = None
        self._css_cache = {}
        self._template_cache = {}
        
        # Lock para operaciones thread-safe
        self._cache_lock = threading.Lock()
        
        # Configuración de optimización
        self.optimization_config = {
            'enable_caching': True,
            'max_memory_usage': 100 * 1024 * 1024,  # 100MB
            'batch_size': 50,  # Para procesamiento masivo
            'gc_frequency': 10  # Ejecutar garbage collection cada N PDFs
        }
        
        # Configuración específica de WeasyPrint para optimizar fuentes
        self.weasyprint_config = {
            'font_config': None,  # Usar configuración del sistema
            'optimize_images': True,
            'compress': True,
            'pdf_version': (1, 7),
            'font_size': 12,  # Tamaño base de fuente
            'dpi': 96,  # DPI optimizado para web
        }

    def _get_file_url(self, path):
        """
        Convierte una ruta de archivo a URL válida multiplataforma.

        Args:
            path: Ruta del archivo

        Returns:
            URL válida para WeasyPrint
        """
        abs_path = os.path.abspath(path).replace("\\", "/")
        if os.name == "nt":  # Windows
            return f"file:///{abs_path}"
        else:  # Unix/Linux/Mac
            return f"file://{abs_path}"

    def _validate_html(self, html_content):
        """
        Valida que el HTML sea correcto y no esté vacío.

        Args:
            html_content: Contenido HTML a validar

        Returns:
            HTML validado y corregido
        """
        if not html_content or len(html_content.strip()) < 50:
            raise ValueError("El contenido HTML está vacío o es muy corto")

        # Asegurar que tiene DOCTYPE
        if not html_content.strip().startswith("<!DOCTYPE"):
            html_content = "<!DOCTYPE html>\n" + html_content

        # Asegurar encoding UTF-8
        if "<meta charset=" not in html_content:
            html_content = html_content.replace(
                "<head>", '<head>\n    <meta charset="UTF-8">'
            )

        return html_content

    def render_template(self, template_name, context):
        """
        Renderiza una plantilla HTML con el contexto proporcionado.

        Args:
            template_name: Nombre del archivo de plantilla HTML.
            context: Diccionario con las variables para la plantilla.

        Returns:
            String con el HTML renderizado.
        """
        try:
            template = self.env.get_template(template_name)
            html_content = template.render(**context)
            return self._validate_html(html_content)
        except jinja2.TemplateNotFound:
            logger.error(f"Plantilla no encontrada: {template_name}")
            return self._generate_fallback_html(
                f"Plantilla {template_name} no encontrada"
            )
        except Exception as e:
            logger.error(f"Error al renderizar plantilla {template_name}: {str(e)}")
            return self._generate_fallback_html(f"Error al renderizar: {str(e)}")

    def _generate_fallback_html(self, error_message):
        """
        Genera HTML básico en caso de error.

        Args:
            error_message: Mensaje de error a mostrar

        Returns:
            HTML básico válido
        """
        return f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>Error en Documento</title>
    <style>
        body {{ font-family: Arial, sans-serif; margin: 40px; }}
        .error {{ color: #d32f2f; border: 1px solid #d32f2f; padding: 20px; margin: 20px 0; }}
    </style>
</head>
<body>
    <h1>Documento SST - Error</h1>
    <div class="error">
        <h3>Error:</h3>
        <p>{error_message}</p>
    </div>
    <p>Fecha: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}</p>
</body>
</html>"""

    async def generate_pdf_from_template(self, template_name, context, output_path=None):
        """
        Genera un PDF a partir de una plantilla HTML y contexto.

        Args:
            template_name: Nombre del archivo de plantilla HTML.
            context: Diccionario con las variables para la plantilla.
            output_path: Ruta donde guardar el PDF generado.

        Returns:
            Bytes del PDF generado o ruta al archivo si output_path es proporcionado.
        """
        try:
            # Renderizar la plantilla HTML
            html_content = self.render_template(template_name, context)
            
            # Determinar archivos CSS basados en el nombre de la plantilla
            css_files = []
            template_base = template_name.replace('.html', '')
            css_file = f"{template_base}.css"
            css_path = os.path.join(self.template_dir, "css", css_file)
            
            if os.path.exists(css_path):
                css_files.append(css_file)
            
            # Generar PDF
            return self.generate_pdf(html_content, css_files, output_path)
            
        except Exception as e:
            logger.error(f"Error en generate_pdf_from_template: {str(e)}")
            return self._generate_emergency_pdf(f"Error al generar PDF desde plantilla: {str(e)}")

    def generate_pdf(self, html_content, css_files=None, output_path=None):
        """
        Genera un archivo PDF a partir del contenido HTML usando WeasyPrint.

        Args:
            html_content: Contenido HTML a convertir.
            css_files: Lista de archivos CSS a incluir.
            output_path: Ruta donde guardar el PDF generado.

        Returns:
            Bytes del PDF generado o ruta al archivo si output_path es proporcionado.
        """
        try:
            return self._generate_pdf_weasyprint(html_content, css_files, output_path)
        except Exception as e:
            logger.error(f"Error en generate_pdf: {str(e)}")
            return self._generate_emergency_pdf(f"Error al generar PDF: {str(e)}")

    def _generate_pdf_weasyprint(self, html_content, css_files=None, output_path=None):
        """
        Genera PDF usando WeasyPrint con optimizaciones de rendimiento.
        """
        # Validar HTML
        html_content = self._validate_html(html_content)

        # Añadir metadatos básicos si no están presentes
        if '<meta name="creator"' not in html_content:
            meta_tags = """
<meta name="creator" content="SST Sistema">
<meta name="producer" content="WeasyPrint">
<meta name="author" content="SST Sistema">
<meta name="title" content="Documento SST">
<meta name="subject" content="Reporte SST">
<meta name="keywords" content="sst, reporte, documento">
<meta http-equiv="Content-Type" content="text/html; charset=utf-8">
<meta http-equiv="Content-Language" content="es">"""

            html_content = html_content.replace("</head>", f"{meta_tags}\n</head>")

        # Configurar base_url
        base_url = self._get_file_url(self.template_dir)

        # Crear objeto HTML
        html_obj = weasyprint.HTML(
            string=html_content, base_url=base_url, encoding="utf-8"
        )

        # Preparar estilos CSS con cache
        stylesheets = []
        if css_files:
            for css_file in css_files:
                css_path = os.path.join(self.template_dir, "css", css_file)
                if os.path.exists(css_path):
                    try:
                        # Usar cache para CSS
                        css = self._load_css_cached(css_path)
                        if css:
                            stylesheets.append(css)
                            logger.info(f"CSS cargado: {css_path}")
                    except Exception as e:
                        logger.warning(f"Error al cargar CSS {css_file}: {str(e)}")

        # Metadatos para el PDF
        pdf_metadata = {
            "title": "Documento SST",
            "author": "SST Sistema",
            "subject": "Reporte del Sistema SST",
            "keywords": "reporte, sistema, sst, documento",
            "creator": "SST Sistema",
            "producer": "WeasyPrint",
        }

        # Configuración optimizada para rendimiento usando configuración predefinida
        pdf_options = {
            "stylesheets": stylesheets,
            "metadata": pdf_metadata,
            "pdf_version": self.weasyprint_config['pdf_version'],
            "optimize_images": self.weasyprint_config['optimize_images'],
            "compress": self.weasyprint_config['compress'],
            "font_config": self.weasyprint_config['font_config'],
            "dpi": self.weasyprint_config['dpi'],
        }

        # Generar PDF con timeout implícito
        try:
            pdf_content = html_obj.write_pdf(**pdf_options)
        except Exception as e:
            logger.error(f"Error en write_pdf: {str(e)}")
            # Intentar con configuración más simple
            simple_options = {
                "stylesheets": stylesheets,
                "metadata": pdf_metadata,
            }
            pdf_content = html_obj.write_pdf(**simple_options)

        # Validar que el PDF se generó correctamente
        if not pdf_content or len(pdf_content) < 1000:
            raise ValueError("PDF generado está vacío o corrupto")

        logger.info(f"PDF generado exitosamente ({len(pdf_content)} bytes)")

        # Guardar archivo si se especifica ruta
        if output_path:
            output_dir = os.path.dirname(output_path)
            if output_dir:
                os.makedirs(output_dir, exist_ok=True)

            with open(output_path, "wb") as f:
                f.write(pdf_content)
            logger.info(f"PDF guardado en: {output_path}")
            return output_path

        return pdf_content

    def _generate_emergency_pdf(self, error_message):
        """
        Genera un PDF básico de emergencia cuando falla todo lo demás.

        Args:
            error_message: Mensaje de error

        Returns:
            Bytes del PDF básico o mensaje de error
        """
        try:
            emergency_html = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>Error</title>
</head>
<body>
    <h1>Error al generar documento</h1>
    <p>Error: {error_message}</p>
    <p>Contacte al administrador del sistema.</p>
</body>
</html>"""

            html_obj = weasyprint.HTML(string=emergency_html)
            return html_obj.write_pdf(
                pdf_version=(1, 7), metadata={"title": "Error", "author": "SST Sistema"}
            )
        except Exception as e:
            logger.critical(f"Error crítico en PDF de emergencia: {str(e)}")
            return f"Error crítico al generar PDF: {str(e)}".encode("utf-8")

    @lru_cache(maxsize=1)
    def _load_logo_base64(self, logo_filename="logo_3.png"):
        """
        Carga el logo y lo convierte a base64 con cache.

        Args:
            logo_filename: Nombre del archivo de logo

        Returns:
            String base64 del logo o cadena vacía si hay error
        """
        if self.optimization_config['enable_caching'] and self._logo_cache is not None:
            return self._logo_cache
            
        logo_path = os.path.join(self.template_dir, logo_filename)

        if not os.path.exists(logo_path):
            logger.warning(f"Logo no encontrado: {logo_path}")
            return ""

        try:
            with open(logo_path, "rb") as image_file:
                logo_data = image_file.read()
                logo_base64 = base64.b64encode(logo_data).decode("utf-8")
            
            if self.optimization_config['enable_caching']:
                with self._cache_lock:
                    self._logo_cache = logo_base64
                    
            logger.info(f"Logo cargado correctamente: {logo_path}")
            return logo_base64
        except Exception as e:
            logger.error(f"Error al cargar logo: {str(e)}")
            return ""
    
    def _load_css_cached(self, css_path: str) -> Optional[weasyprint.CSS]:
        """Cargar CSS con cache para mejorar rendimiento."""
        if not self.optimization_config['enable_caching']:
            try:
                return weasyprint.CSS(filename=css_path)
            except Exception as e:
                logger.warning(f"Error al cargar CSS {css_path}: {str(e)}")
                return None
        
        with self._cache_lock:
            if css_path in self._css_cache:
                return self._css_cache[css_path]
            
            try:
                css_obj = weasyprint.CSS(filename=css_path)
                self._css_cache[css_path] = css_obj
                return css_obj
            except Exception as e:
                logger.warning(f"Error al cargar CSS {css_path}: {str(e)}")
                return None
    
    def _clear_memory_cache(self):
        """Limpiar cache de memoria para liberar recursos."""
        with self._cache_lock:
            self._css_cache.clear()
            self._template_cache.clear()
        gc.collect()
        logger.info("Cache de memoria limpiado")

    def generate_attendance_list_pdf(self, template_data, output_path=None):
        """
        Generar PDF de lista de asistencia optimizado.
        
        Args:
            template_data: Datos para la plantilla
            output_path: Ruta donde guardar el PDF (opcional)
            
        Returns:
            bytes: Contenido del PDF o ruta del archivo si se especifica output_path
        """
        try:
            now = datetime.now()
            logo_base64 = self._load_logo_base64()
            # Si no es dict, intentar convertir
            if not isinstance(template_data, dict):
                if hasattr(template_data, "__dict__"):
                    template_data = template_data.__dict__
                else:
                    template_data = {}
            # Validar y transformar contexto
            session_data = template_data.get("session", {})
            attendees_data = template_data.get("attendees", [])
            context_validated = self.prepare_attendance_context(
                session_data, attendees_data
            )
            # Agregar logo y fechas
            context_validated["logo_base64"] = logo_base64
            context_validated["generation_date"] = now.strftime("%d/%m/%Y")
            context_validated["generation_time"] = now.strftime("%H:%M:%S")
            # Renderizar plantilla
            html_content = self.render_template(
                "attendance_list.html", context_validated
            )
            # Procesar CSS
            css_path = os.path.join(self.template_dir, "css", "attendance_list.css")
            if os.path.exists(css_path):
                css_url = self._get_file_url(css_path)
                html_content = html_content.replace(
                    'href="css/attendance_list.css"', f'href="{css_url}"'
                )
            # Añadir metadatos específicos
            specific_meta = """
    <meta name="title" content="Lista de Asistencia">
    <meta name="subject" content="Lista de Asistencia a Capacitación">
    <meta name="keywords" content="asistencia, capacitación, lista">"""
            html_content = html_content.replace("</head>", f"{specific_meta}\n</head>")
            # Generar PDF con configuración específica
            base_url = self._get_file_url(self.template_dir)
            html_obj = weasyprint.HTML(
                string=html_content, base_url=base_url, encoding="utf-8"
            )
            # Cargar CSS con cache
            stylesheets = []
            if os.path.exists(css_path):
                css_obj = self._load_css_cached(css_path)
                if css_obj:
                    stylesheets.append(css_obj)
            # Metadatos específicos
            pdf_metadata = {
                "title": "Lista de Asistencia",
                "author": "SST Sistema",
                "subject": "Lista de Asistencia a Capacitación",
                "keywords": "asistencia, capacitación, lista",
                "creator": "SST Sistema",
                "producer": "WeasyPrint",
            }
            # Generar PDF con configuración optimizada
            pdf_content = html_obj.write_pdf(
                stylesheets=stylesheets, 
                metadata=pdf_metadata, 
                pdf_version=(1, 7),
                optimize_images=True,  # Optimizar imágenes
                compress=True  # Comprimir contenido
            )
            # Validar PDF generado
            if not pdf_content or len(pdf_content) < 1000:
                raise ValueError("PDF de lista de asistencia está vacío")
            logger.info(f"Lista de asistencia PDF generada ({len(pdf_content)} bytes)")
            # Guardar si se especifica ruta
            if output_path:
                output_dir = os.path.dirname(output_path)
                if output_dir:
                    os.makedirs(output_dir, exist_ok=True)
                with open(output_path, "wb") as f:
                    f.write(pdf_content)
                return output_path
            return pdf_content
        except Exception as e:
            logger.error(f"Error en generate_attendance_list_pdf: {str(e)}")
            return self._generate_emergency_pdf(
                f"Error en lista de asistencia: {str(e)}"
            )

    def generate_occupational_exam_report_pdf(self, template_data, output_path=None):
        """
        Genera un PDF de reporte de exámenes ocupacionales.
        """
        try:
            now = datetime.now()
            logo_base64 = self._load_logo_base64()

            # Verificar si template_data es un diccionario o necesita ser convertido
            if not isinstance(template_data, dict):
                # Si no es un diccionario, intentar convertirlo
                if hasattr(template_data, "__dict__"):
                    template_data = template_data.__dict__
                else:
                    template_data = {}

            # Crear contexto
            context = {
                "logo_base64": logo_base64,
                "statistics": template_data.get("statistics", {}),
                "pending_exams": template_data.get("pending_exams", []),
                "overdue_exams": template_data.get("overdue_exams", []),
                "total_pending": template_data.get("total_pending", 0),
                "total_overdue": template_data.get("total_overdue", 0),
                "generated_at": now.strftime("%d/%m/%Y %H:%M:%S"),
            }

            # Renderizar plantilla
            html_content = self.render_template(
                "occupational_exam_report.html", context
            )

            # Procesar CSS
            css_path = os.path.join(
                self.template_dir, "css", "occupational_exam_report.css"
            )
            if os.path.exists(css_path):
                css_url = self._get_file_url(css_path)
                html_content = html_content.replace(
                    'href="css/occupational_exam_report.css"', f'href="{css_url}"'
                )

            # Generar PDF
            return self.generate_pdf(
                html_content, ["occupational_exam_report.css"], output_path
            )

        except Exception as e:
            logger.error(f"Error en generate_occupational_exam_report_pdf: {str(e)}")
            return self._generate_emergency_pdf(
                f"Error en reporte ocupacional: {str(e)}"
            )

    def generate_attendance_certificate_pdf(self, attendance_data, participant_data, output_path=None):
        """
        Genera un PDF de certificado de asistencia individual en formato horizontal.
        
        Args:
            attendance_data: Diccionario con datos de asistencia
            participant_data: Diccionario con datos del participante
            output_path: Ruta donde guardar el PDF generado.
            
        Returns:
            Bytes del PDF generado o ruta al archivo si output_path es proporcionado.
        """
        try:
            now = datetime.now()
            logo_base64 = self._load_logo_base64()
            
            # Validar y procesar datos de asistencia
            if not isinstance(attendance_data, dict):
                if hasattr(attendance_data, "__dict__"):
                    attendance_data = attendance_data.__dict__
                else:
                    attendance_data = {}
            
            # Validar y procesar datos del participante
            if not isinstance(participant_data, dict):
                if hasattr(participant_data, "__dict__"):
                    participant_data = participant_data.__dict__
                else:
                    participant_data = {}
            
            # Formatear fecha de sesión
            session_date = attendance_data.get("session_date", "")
            if session_date:
                try:
                    if isinstance(session_date, str):
                        # Intentar parsear diferentes formatos de fecha
                        if "T" in session_date:
                            date_obj = datetime.fromisoformat(session_date.replace("Z", "+00:00"))
                        else:
                            date_obj = datetime.strptime(session_date, "%Y-%m-%d")
                    else:
                        date_obj = session_date
                    
                    session_date_formatted = date_obj.strftime("%d/%m/%Y")
                    session_time = date_obj.strftime("%H:%M")
                except:
                    session_date_formatted = session_date
                    session_time = "No especificada"
            else:
                session_date_formatted = "No especificada"
                session_time = "No especificada"
            
            # Formatear duración
            duration_minutes = attendance_data.get("duration_minutes", 0)
            if duration_minutes:
                hours = duration_minutes // 60
                minutes = duration_minutes % 60
                if hours > 0:
                    duration_formatted = f"{hours}h {minutes}m"
                else:
                    duration_formatted = f"{minutes}m"
            else:
                duration_formatted = "No especificada"
            
            # Mapear estado de asistencia
            status_map = {
                "present": "PRESENTE",
                "absent": "AUSENTE", 
                "late": "TARDÍO",
                "excused": "EXCUSADO",
                "partial": "PARCIAL"
            }
            
            status = attendance_data.get("status", "present").lower()
            status_display = status_map.get(status, "PRESENTE")
            
            # Crear contexto para la plantilla
            context = {
                "logo_base64": logo_base64,
                "attendance": {
                    "course_name": attendance_data.get("course_name", "Curso no especificado"),
                    "session_date_formatted": session_date_formatted,
                    "session_time": session_time,
                    "duration_formatted": duration_formatted,
                    "status": status,
                    "status_display": status_display,
                    "completion_percentage": attendance_data.get("completion_percentage", 0),
                    "notes": attendance_data.get("notes", ""),
                    "instructor_name": attendance_data.get("instructor_name", "")
                },
                "participant": {
                    "first_name": participant_data.get("first_name", participant_data.get("nombre", "")),
                    "last_name": participant_data.get("last_name", participant_data.get("apellido", "")),
                    "document": participant_data.get("document", participant_data.get("documento", "")),
                    "phone": participant_data.get("phone", participant_data.get("telefono", "")),
                    "position": participant_data.get("position", participant_data.get("cargo", "")),
                    "area": participant_data.get("area", participant_data.get("area", ""))
                },
                "generation_date": now.strftime("%d/%m/%Y"),
                "generation_time": now.strftime("%H:%M:%S")
            }
            
            # Renderizar plantilla
            html_content = self.render_template("attendance_certificate.html", context)
            
            # Procesar CSS
            css_path = os.path.join(self.template_dir, "css", "attendance_certificate.css")
            if os.path.exists(css_path):
                css_url = self._get_file_url(css_path)
                html_content = html_content.replace(
                    'href="css/attendance_certificate.css"', f'href="{css_url}"'
                )
            
            # Añadir metadatos específicos
            specific_meta = """
    <meta name="title" content="Certificado de Asistencia">
    <meta name="subject" content="Certificado de Asistencia Individual">
    <meta name="keywords" content="certificado, asistencia, capacitación">"""
            html_content = html_content.replace("</head>", f"{specific_meta}\n</head>")
            
            # Generar PDF con configuración específica para formato horizontal
            base_url = self._get_file_url(self.template_dir)
            html_obj = weasyprint.HTML(
                string=html_content, base_url=base_url, encoding="utf-8"
            )
            
            # Cargar CSS con cache
            stylesheets = []
            if os.path.exists(css_path):
                css_obj = self._load_css_cached(css_path)
                if css_obj:
                    stylesheets.append(css_obj)
            
            # Metadatos específicos
            pdf_metadata = {
                "title": "Certificado de Asistencia",
                "author": "SST Sistema",
                "subject": "Certificado de Asistencia Individual",
                "keywords": "certificado, asistencia, capacitación",
                "creator": "SST Sistema",
                "producer": "WeasyPrint",
            }
            
            # Generar PDF con configuración optimizada
            pdf_content = html_obj.write_pdf(
                stylesheets=stylesheets, 
                metadata=pdf_metadata, 
                pdf_version=(1, 7),
                optimize_images=True,  # Optimizar imágenes
                compress=True  # Comprimir contenido
            )
            
            # Validar PDF generado
            if not pdf_content or len(pdf_content) < 1000:
                raise ValueError("PDF de certificado de asistencia está vacío")
            
            logger.info(f"Certificado de asistencia PDF generado ({len(pdf_content)} bytes)")
            
            # Guardar si se especifica ruta
            if output_path:
                output_dir = os.path.dirname(output_path)
                if output_dir:
                    os.makedirs(output_dir, exist_ok=True)
                
                with open(output_path, "wb") as f:
                    f.write(pdf_content)
                return output_path
            
            return pdf_content
            
        except Exception as e:
            logger.error(f"Error en generate_attendance_certificate_pdf: {str(e)}")
            return self._generate_emergency_pdf(
                f"Error en certificado de asistencia: {str(e)}"
            )
    
    def generate_bulk_attendance_certificates(self, attendance_list: List[Dict[str, Any]], 
                                            output_dir: Optional[str] = None) -> List[bytes]:
        """
        Generar múltiples certificados de asistencia de forma optimizada.
        
        Args:
            attendance_list: Lista de datos de asistencia
            output_dir: Directorio donde guardar los PDFs (opcional)
            
        Returns:
            List[bytes]: Lista de contenidos PDF generados
        """
        results = []
        batch_size = self.optimization_config['batch_size']
        gc_frequency = self.optimization_config['gc_frequency']
        
        try:
            logger.info(f"Iniciando generación masiva de {len(attendance_list)} certificados")
            
            # Procesar en lotes para optimizar memoria
            for i in range(0, len(attendance_list), batch_size):
                batch = attendance_list[i:i + batch_size]
                batch_results = []
                
                logger.info(f"Procesando lote {i//batch_size + 1}/{(len(attendance_list) + batch_size - 1)//batch_size}")
                
                for j, attendance_data in enumerate(batch):
                    try:
                        # Extraer datos del participante y asistencia
                        participant_data = attendance_data.get('participant', {})
                        attendance_info = attendance_data.get('attendance', attendance_data)
                        
                        # Generar PDF individual
                        pdf_content = self.generate_attendance_certificate_pdf(
                            attendance_info, participant_data
                        )
                        
                        # Guardar si se especifica directorio
                        if output_dir and isinstance(pdf_content, bytes):
                            filename = f"certificado_{participant_data.get('document', f'item_{i+j}')}.pdf"
                            filepath = os.path.join(output_dir, filename)
                            os.makedirs(output_dir, exist_ok=True)
                            
                            with open(filepath, 'wb') as f:
                                f.write(pdf_content)
                        
                        batch_results.append(pdf_content)
                        
                        # Ejecutar garbage collection periódicamente
                        if (i + j + 1) % gc_frequency == 0:
                            gc.collect()
                            
                    except Exception as e:
                        logger.error(f"Error generando certificado {i+j}: {str(e)}")
                        batch_results.append(self._generate_emergency_pdf(
                            f"Error en certificado: {str(e)}"
                        ))
                
                results.extend(batch_results)
                
                # Limpiar cache entre lotes para liberar memoria
                if i + batch_size < len(attendance_list):
                    self._clear_memory_cache()
            
            logger.info(f"Generación masiva completada: {len(results)} certificados")
            return results
            
        except Exception as e:
            logger.error(f"Error en generación masiva: {str(e)}")
            # Retornar PDFs de emergencia para los elementos restantes
            emergency_results = []
            for _ in range(len(attendance_list) - len(results)):
                emergency_results.append(self._generate_emergency_pdf(
                    f"Error en generación masiva: {str(e)}"
                ))
            return results + emergency_results
