import os
import jinja2
import weasyprint
import base64
import tempfile
import io
import logging
from datetime import datetime
from pathlib import Path

# Configurar logging para debug
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class HTMLToPDFConverter:
    def __init__(self, template_dir=None):
        """
        Inicializa el convertidor de HTML a PDF.
        
        Args:
            template_dir: Directorio donde se encuentran las plantillas HTML.
        """
        if template_dir is None:
            # Usar el directorio de plantillas por defecto
            base_dir = Path(__file__).resolve().parent.parent
            self.template_dir = os.path.join(base_dir, 'templates', 'reports')
        else:
            self.template_dir = template_dir
            
        # Verificar que el directorio existe
        if not os.path.exists(self.template_dir):
            os.makedirs(self.template_dir, exist_ok=True)
            logger.warning(f"Directorio de plantillas creado: {self.template_dir}")
            
        # Configurar el entorno de Jinja2
        self.env = jinja2.Environment(
            loader=jinja2.FileSystemLoader(self.template_dir),
            autoescape=jinja2.select_autoescape(['html', 'xml'])
        )
    
    def _get_file_url(self, path):
        """
        Convierte una ruta de archivo a URL válida multiplataforma.
        
        Args:
            path: Ruta del archivo
            
        Returns:
            URL válida para WeasyPrint
        """
        abs_path = os.path.abspath(path).replace('\\', '/')
        if os.name == 'nt':  # Windows
            return f'file:///{abs_path}'
        else:  # Unix/Linux/Mac
            return f'file://{abs_path}'
    
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
        if not html_content.strip().startswith('<!DOCTYPE'):
            html_content = '<!DOCTYPE html>\n' + html_content
        
        # Asegurar encoding UTF-8
        if '<meta charset=' not in html_content:
            html_content = html_content.replace(
                '<head>',
                '<head>\n    <meta charset="UTF-8">'
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
            return self._generate_fallback_html(f"Plantilla {template_name} no encontrada")
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
    
    def generate_pdf(self, html_content, css_files=None, output_path=None):
        """
        Genera un archivo PDF a partir del contenido HTML.
        
        Args:
            html_content: Contenido HTML a convertir.
            css_files: Lista de archivos CSS a incluir.
            output_path: Ruta donde guardar el PDF generado.
            
        Returns:
            Bytes del PDF generado o ruta al archivo si output_path es proporcionado.
        """
        try:
            # Validar HTML
            html_content = self._validate_html(html_content)
            
            # Añadir metadatos básicos si no están presentes
            if '<meta name="creator"' not in html_content:
                meta_tags = '''
    <meta name="creator" content="SST Sistema">
    <meta name="producer" content="WeasyPrint">
    <meta name="author" content="SST Sistema">
    <meta name="title" content="Documento SST">
    <meta name="subject" content="Reporte SST">
    <meta name="keywords" content="sst, reporte, documento">
    <meta http-equiv="Content-Type" content="text/html; charset=utf-8">
    <meta http-equiv="Content-Language" content="es">'''
                
                html_content = html_content.replace('</head>', f'{meta_tags}\n</head>')
            
            # Configurar base_url
            base_url = self._get_file_url(self.template_dir)
            
            # Crear objeto HTML
            html_obj = weasyprint.HTML(
                string=html_content, 
                base_url=base_url,
                encoding='utf-8'
            )
            
            # Preparar estilos CSS
            stylesheets = []
            if css_files:
                for css_file in css_files:
                    css_path = os.path.join(self.template_dir, 'css', css_file)
                    if os.path.exists(css_path):
                        try:
                            css = weasyprint.CSS(filename=css_path)
                            stylesheets.append(css)
                            logger.info(f"CSS cargado: {css_path}")
                        except Exception as e:
                            logger.warning(f"Error al cargar CSS {css_file}: {str(e)}")
            
            # Metadatos para el PDF
            pdf_metadata = {
                'title': 'Documento SST',
                'author': 'SST Sistema',
                'subject': 'Reporte del Sistema SST',
                'keywords': 'reporte, sistema, sst, documento',
                'creator': 'SST Sistema',
                'producer': 'WeasyPrint'
            }
            
            # Configuración básica para mayor compatibilidad
            pdf_options = {
                'stylesheets': stylesheets,
                'metadata': pdf_metadata,
                'pdf_version': (1, 7)  # Versión más compatible
            }
            
            # Generar PDF
            pdf_content = html_obj.write_pdf(**pdf_options)
            
            # Validar que el PDF se generó correctamente
            if not pdf_content or len(pdf_content) < 1000:
                raise ValueError("PDF generado está vacío o corrupto")
            
            logger.info(f"PDF generado exitosamente ({len(pdf_content)} bytes)")
            
            # Guardar archivo si se especifica ruta
            if output_path:
                output_dir = os.path.dirname(output_path)
                if output_dir:
                    os.makedirs(output_dir, exist_ok=True)
                
                with open(output_path, 'wb') as f:
                    f.write(pdf_content)
                logger.info(f"PDF guardado en: {output_path}")
                return output_path
            
            return pdf_content
            
        except Exception as e:
            logger.error(f"Error al generar PDF: {str(e)}")
            return self._generate_emergency_pdf(str(e))
    
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
                pdf_version=(1, 7),
                metadata={'title': 'Error', 'author': 'SST Sistema'}
            )
        except Exception as e:
            logger.critical(f"Error crítico en PDF de emergencia: {str(e)}")
            return f"Error crítico al generar PDF: {str(e)}".encode('utf-8')
    
    def _load_logo_base64(self, logo_filename='logo_3.png'):
        """
        Carga el logo y lo convierte a base64.
        
        Args:
            logo_filename: Nombre del archivo de logo
            
        Returns:
            String base64 del logo o cadena vacía si hay error
        """
        logo_path = os.path.join(self.template_dir, logo_filename)
        
        if not os.path.exists(logo_path):
            logger.warning(f"Logo no encontrado: {logo_path}")
            return ''
        
        try:
            with open(logo_path, 'rb') as image_file:
                logo_data = image_file.read()
                logo_base64 = base64.b64encode(logo_data).decode('utf-8')
            logger.info(f"Logo cargado correctamente: {logo_path}")
            return logo_base64
        except Exception as e:
            logger.error(f"Error al cargar logo: {str(e)}")
            return ''
    
    def generate_attendance_list_pdf(self, template_data, output_path=None):
        """
        Genera un PDF de lista de asistencia a partir de los datos proporcionados.
        
        Args:
            template_data: Diccionario con los datos para la plantilla
            output_path: Ruta donde guardar el PDF generado.
            
        Returns:
            Bytes del PDF generado o ruta al archivo si output_path es proporcionado.
        """
        try:
            # Preparar el contexto
            now = datetime.now()
            logo_base64 = self._load_logo_base64()
            
            # Verificar si template_data es un diccionario o necesita ser convertido
            if not isinstance(template_data, dict):
                # Si no es un diccionario, intentar convertirlo
                if hasattr(template_data, '__dict__'):
                    template_data = template_data.__dict__
                else:
                    template_data = {}
            
            # Validar datos de entrada
            session_data = template_data.get('session', {})
            attendees_data = template_data.get('attendees', [])
            
            if not session_data:
                logger.warning("Datos de sesión vacíos")
                session_data = {'title': 'Sesión sin título', 'date': now.strftime('%d/%m/%Y')}
            
            if not attendees_data:
                logger.warning("Lista de asistentes vacía")
            
            # Crear contexto
            context = {
                'logo_base64': logo_base64,
                'session': session_data,
                'attendees': attendees_data,
                'generation_date': now.strftime('%d/%m/%Y'),
                'generation_time': now.strftime('%H:%M:%S')
            }
            
            # Renderizar plantilla
            html_content = self.render_template('attendance_list.html', context)
            
            # Procesar CSS
            css_path = os.path.join(self.template_dir, 'css', 'attendance_list.css')
            if os.path.exists(css_path):
                css_url = self._get_file_url(css_path)
                html_content = html_content.replace(
                    'href="css/attendance_list.css"',
                    f'href="{css_url}"'
                )
            
            # Añadir metadatos específicos
            specific_meta = '''
    <meta name="title" content="Lista de Asistencia">
    <meta name="subject" content="Lista de Asistencia a Capacitación">
    <meta name="keywords" content="asistencia, capacitación, lista">'''
            
            html_content = html_content.replace('</head>', f'{specific_meta}\n</head>')
            
            # Generar PDF con configuración específica
            base_url = self._get_file_url(self.template_dir)
            html_obj = weasyprint.HTML(
                string=html_content,
                base_url=base_url,
                encoding='utf-8'
            )
            
            # Cargar CSS
            stylesheets = []
            if os.path.exists(css_path):
                try:
                    css = weasyprint.CSS(filename=css_path)
                    stylesheets.append(css)
                except Exception as e:
                    logger.warning(f"Error al cargar CSS: {str(e)}")
            
            # Metadatos específicos
            pdf_metadata = {
                'title': 'Lista de Asistencia',
                'author': 'SST Sistema',
                'subject': 'Lista de Asistencia a Capacitación',
                'keywords': 'asistencia, capacitación, lista',
                'creator': 'SST Sistema',
                'producer': 'WeasyPrint'
            }
            
            # Generar PDF con configuración básica para mayor compatibilidad
            pdf_content = html_obj.write_pdf(
                stylesheets=stylesheets,
                metadata=pdf_metadata,
                pdf_version=(1, 7)
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
                
                with open(output_path, 'wb') as f:
                    f.write(pdf_content)
                return output_path
            
            return pdf_content
            
        except Exception as e:
            logger.error(f"Error en generate_attendance_list_pdf: {str(e)}")
            return self._generate_emergency_pdf(f"Error en lista de asistencia: {str(e)}")
    
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
                if hasattr(template_data, '__dict__'):
                    template_data = template_data.__dict__
                else:
                    template_data = {}
            
            # Crear contexto
            context = {
                'logo_base64': logo_base64,
                'statistics': template_data.get('statistics', {}),
                'pending_exams': template_data.get('pending_exams', []),
                'overdue_exams': template_data.get('overdue_exams', []),
                'total_pending': template_data.get('total_pending', 0),
                'total_overdue': template_data.get('total_overdue', 0),
                'generated_at': now.strftime('%d/%m/%Y %H:%M:%S')
            }
            
            # Renderizar plantilla
            html_content = self.render_template('occupational_exam_report.html', context)
            
            # Procesar CSS
            css_path = os.path.join(self.template_dir, 'css', 'occupational_exam_report.css')
            if os.path.exists(css_path):
                css_url = self._get_file_url(css_path)
                html_content = html_content.replace(
                    'href="css/occupational_exam_report.css"',
                    f'href="{css_url}"'
                )
            
            # Generar PDF
            return self.generate_pdf(html_content, ['occupational_exam_report.css'], output_path)
            
        except Exception as e:
            logger.error(f"Error en generate_occupational_exam_report_pdf: {str(e)}")
            return self._generate_emergency_pdf(f"Error en reporte ocupacional: {str(e)}")