import os
import jinja2
import weasyprint
import base64
import tempfile
import io
from datetime import datetime
from pathlib import Path
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
            
        # Configurar el entorno de Jinja2
        self.env = jinja2.Environment(
            loader=jinja2.FileSystemLoader(self.template_dir),
            autoescape=jinja2.select_autoescape(['html', 'xml'])
        )
    
    def render_template(self, template_name, context):
        """
        Renderiza una plantilla HTML con el contexto proporcionado.
        
        Args:
            template_name: Nombre del archivo de plantilla HTML.
            context: Diccionario con las variables para la plantilla.
            
        Returns:
            String con el HTML renderizado.
        """
        template = self.env.get_template(template_name)
        return template.render(**context)
    
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
            # Crear el objeto HTML de WeasyPrint con base_url absoluta
            base_url = os.path.abspath(self.template_dir)
            html = weasyprint.HTML(string=html_content, base_url=base_url)
            
            # Preparar los estilos CSS
            stylesheets = []
            if css_files:
                for css_file in css_files:
                    css_path = os.path.join(self.template_dir, 'css', css_file)
                    if os.path.exists(css_path):
                        try:
                            css = weasyprint.CSS(filename=css_path)
                            stylesheets.append(css)
                        except Exception as e:
                            print(f"Error al cargar CSS {css_file}: {str(e)}")
            
            # Configurar opciones de PDF para mejorar compatibilidad
            pdf_options = {
                'optimize_size': ('fonts', 'images'),
                'presentational_hints': True,
                'compress': False,  # Desactivar compresión para mejor compatibilidad
                'pdf_version': (1, 6),  # Usar versión 1.6 de PDF para mejor compatibilidad
                'attachments': []  # No incluir archivos adjuntos
            }
            
            # Generar el PDF directamente en memoria
            pdf_content = html.write_pdf(stylesheets=stylesheets, **pdf_options)
            
            # Si se especificó una ruta de salida, guardar el PDF
            if output_path:
                # Asegurarse de que el directorio exista
                os.makedirs(os.path.dirname(output_path), exist_ok=True)
                # Guardar el PDF en el archivo
                with open(output_path, 'wb') as f:
                    f.write(pdf_content)
            
            # Guardar en la ruta de salida si se especificó
            if output_path:
                # Asegurarse de que el directorio exista
                os.makedirs(os.path.dirname(output_path), exist_ok=True)
                # Guardar el PDF en el archivo
                with open(output_path, 'wb') as f:
                    f.write(pdf_content)
                return output_path
            else:
                # Devolver el PDF como bytes
                return pdf_content
        except Exception as e:
            print(f"Error al generar PDF: {str(e)}")
            # En caso de error, intentar generar un PDF básico sin estilos
            try:
                # Crear un HTML simplificado para generar un PDF básico
                simple_html = """<!DOCTYPE html>
                <html>
                <head><meta charset="UTF-8"></head>
                <body>
                <h1>Reporte de Asistencia</h1>
                <p>No se pudo generar el reporte completo. Por favor, contacte al administrador.</p>
                </body>
                </html>"""
                return weasyprint.HTML(string=simple_html).write_pdf()
            except:
                # Si todo falla, devolver un PDF vacío
                from reportlab.pdfgen import canvas
                buffer = io.BytesIO()
                c = canvas.Canvas(buffer)
                c.drawString(100, 750, "Error al generar el reporte de asistencia")
                c.save()
                buffer.seek(0)
                return buffer.getvalue()
    
    def generate_attendance_list_pdf(self, session_data, attendees_data, output_path=None):
        """
        Genera un PDF de lista de asistencia a partir de los datos proporcionados.
        
        Args:
            session_data: Diccionario con los datos de la sesión.
            attendees_data: Lista de diccionarios con los datos de los asistentes.
            output_path: Ruta donde guardar el PDF generado.
            
        Returns:
            Bytes del PDF generado o ruta al archivo si output_path es proporcionado.
        """
        # Preparar el contexto para la plantilla
        now = datetime.now()
        # Convertir el logo a base64
        logo_path = os.path.abspath(os.path.join(self.template_dir, 'logo_3.png'))
        with open(logo_path, 'rb') as image_file:
            logo_base64 = base64.b64encode(image_file.read()).decode('utf-8')
        context = {
            'logo_base64': logo_base64,
            'session_title': session_data.get('title', ''),
            'session_date': session_data.get('session_date', ''),
            'course_title': session_data.get('course_title', ''),
            'instructor_name': session_data.get('instructor_name', ''),
            'location': session_data.get('location', ''),
            'duration': session_data.get('duration', ''),
            'attendees': attendees_data,
            'total_attendees': len(attendees_data),
            'attendance_percentage': session_data.get('attendance_percentage', 0),
            'generation_date': now.strftime('%d/%m/%Y'),
            'generation_time': now.strftime('%H:%M:%S')
        }
        
        # Renderizar la plantilla HTML
        html_content = self.render_template('attendance_list.html', context)
        
        # Añadir metadatos al HTML para mejorar compatibilidad
        html_content = html_content.replace('</head>', '<meta name="creator" content="SST Sistema"><meta name="producer" content="WeasyPrint"><meta http-equiv="Content-Type" content="text/html; charset=utf-8"></head>')
        
        # Generar el PDF
        if output_path:
            # Asegurarse de que el directorio exista
            os.makedirs(os.path.dirname(output_path), exist_ok=True)
        
        # Configurar opciones de PDF específicas para este reporte
        pdf_options = {
            'optimize_size': ('fonts', 'images'),
            'presentational_hints': True,
            'compress': False,  # Desactivar compresión para mejor compatibilidad
            'pdf_version': (1, 6),  # Usar versión 1.6 de PDF para mejor compatibilidad
            'attachments': []  # No incluir archivos adjuntos
        }
        
        # Crear el objeto HTML de WeasyPrint con base_url absoluta
        base_url = os.path.abspath(self.template_dir)
        html = weasyprint.HTML(string=html_content, base_url=base_url)
        
        # Preparar los estilos CSS
        stylesheets = []
        css_path = os.path.join(self.template_dir, 'css', 'attendance_list.css')
        if os.path.exists(css_path):
            try:
                css = weasyprint.CSS(filename=css_path)
                stylesheets.append(css)
            except Exception as e:
                print(f"Error al cargar CSS attendance_list.css: {str(e)}")
        
        # Generar el PDF directamente
        pdf_content = html.write_pdf(stylesheets=stylesheets, **pdf_options)
        
        # Si se especificó una ruta de salida, guardar el PDF
        if output_path:
            with open(output_path, 'wb') as f:
                f.write(pdf_content)
            return output_path
        
        return pdf_content