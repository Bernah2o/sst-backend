import os
import io
import base64
import logging
from datetime import datetime
from typing import Optional, Dict, Any
from sqlalchemy.orm import Session

from app.models.certificate import Certificate
from app.models.user import User
from app.models.course import Course
from app.utils.storage import StorageManager
from app.config import settings
from app.services.html_to_pdf import HTMLToPDFConverter

logger = logging.getLogger(__name__)


class CertificateGenerator:
    def __init__(self, db: Session):
        self.db = db
        self.storage_manager = StorageManager()
        self.certificates_dir = "certificates"
        
        # Crear directorio local si no existe (para fallback)
        if not os.path.exists(self.certificates_dir):
            os.makedirs(self.certificates_dir)
    
    async def generate_certificate_pdf(self, certificate_id: int) -> str:
        """
        Genera un certificado en PDF usando WeasyPrint y retorna la URL del archivo
        """
        # Obtener datos del certificado
        certificate = self.db.query(Certificate).filter(Certificate.id == certificate_id).first()
        if not certificate:
            raise ValueError("Certificate not found")
        
        user = self.db.query(User).filter(User.id == certificate.user_id).first()
        course = None
        if certificate.course_id:
            course = self.db.query(Course).filter(Course.id == certificate.course_id).first()
        
        if not user:
            raise ValueError("User not found")
        
        # Para certificados con curso, verificar que el curso exista
        if certificate.course_id and not course:
            raise ValueError("Course not found")
        
        # Generar nombre del archivo
        filename = f"certificate_{certificate.certificate_number}.pdf"
        local_filepath = os.path.join(self.certificates_dir, filename)
        
        # Crear el PDF localmente usando WeasyPrint
        self._create_certificate_pdf_with_weasyprint(local_filepath, certificate, user, course)
        
        # Si Firebase Storage está habilitado, subir el archivo
        if settings.use_firebase_storage:
            # Subir a Firebase Storage
            firebase_path = f"{settings.firebase_certificates_path}/{filename}"
            success = await self.storage_manager.copy_local_to_firebase(local_filepath, firebase_path)
            if success:
                file_url = f"https://storage.googleapis.com/{settings.firebase_storage_bucket}/{firebase_path}"
                logger.info(f"Certificado subido a Firebase: {file_url}")
            else:
                logger.error("Error al subir certificado a Firebase Storage")
                # Usar archivo local como fallback
                file_url = f"/certificates/{filename}"
            
            # Limpiar archivo local después de subir
            try:
                os.remove(local_filepath)
            except OSError:
                pass
                
            # Actualizar la ruta del archivo en la base de datos
            certificate.file_path = file_url
        else:
            # Usar ruta local
            certificate.file_path = local_filepath
            file_url = f"/certificates/{filename}"
        
        self.db.commit()
        
        return file_url
    
    def _create_certificate_pdf_with_weasyprint(self, filepath: str, certificate: Certificate, user: User, course: Course):
        """
        Crea el archivo PDF del certificado con diseño profesional usando WeasyPrint
        """
        try:
            # Inicializar el convertidor HTML a PDF
            converter = HTMLToPDFConverter()
            
            # Preparar datos para la plantilla
            completion_date = certificate.completion_date.strftime("%d de %B de %Y")
            issue_date = certificate.issue_date.strftime("%d de %B de %Y")
            expiry_date = certificate.expiry_date.strftime("%d/%m/%Y") if certificate.expiry_date else None
            
            template_data = {
                "certificate": certificate,
                "user": user,
                "course": course,
                "completion_date": completion_date,
                "issue_date": issue_date,
                "expiry_date": expiry_date
            }
            
            # Asegurar que template_data sea un diccionario
            if not isinstance(template_data, dict):
                if hasattr(template_data, '__dict__'):
                    template_data = template_data.__dict__
                else:
                    template_data = {}
            
            # Cargar logo si existe
            try:
                logo_path = os.path.join(converter.template_dir, 'logo_3.png')
                with open(logo_path, 'rb') as image_file:
                    template_data["logo_base64"] = base64.b64encode(image_file.read()).decode('utf-8')
            except Exception as e:
                print(f"Error al cargar el logo: {str(e)}")
                template_data["logo_base64"] = ""
            
            # Determinar qué plantilla usar según el tipo de certificado
            if certificate.template_used == "attendance":
                # Usar plantilla de certificado de asistencia
                template_name = 'attendance_certificate.html'
                css_files = ['attendance_certificate.css']
                
                # Preparar datos específicos para certificado de asistencia
                # Buscar datos de asistencia si están disponibles
                attendance_data = {
                    "course_name": course.title if course else certificate.title.replace("Certificado de Asistencia - ", ""),
                    "session_date_formatted": certificate.completion_date.strftime("%d/%m/%Y"),
                    "status": "present",
                    "status_display": "PRESENTE",
                    "completion_percentage": 100,
                    "notes": certificate.description or ""
                }
                
                participant_data = {
                    "first_name": user.first_name,
                    "last_name": user.last_name,
                    "full_name": user.full_name,
                    "document": user.document_number,
                    "phone": getattr(user, 'phone', ''),
                    "position": getattr(user, 'position', ''),
                    "area": getattr(user, 'area', '')
                }
                
                template_data = {
                    "attendance": attendance_data,
                    "participant": participant_data,
                    "generation_date": certificate.issue_date.strftime("%d/%m/%Y"),
                    "generation_time": certificate.issue_date.strftime("%H:%M:%S"),
                    "logo_base64": template_data.get("logo_base64", "")
                }
            else:
                # Usar plantilla de certificado de curso (por defecto para "default" y otros tipos)
                template_name = 'certificate.html'
                css_files = ['certificate.css']
            
            # Renderizar la plantilla HTML
            html_content = converter.render_template(template_name, template_data)
            
            # Generar el PDF usando archivo CSS externo
            pdf_content = converter.generate_pdf(
                html_content=html_content,
                css_files=css_files,
                output_path=filepath
            )
            
            return filepath
            
        except Exception as e:
            print(f"Error al generar certificado PDF: {str(e)}")
            raise e
    
    def create_certificate_with_border(self, filepath: str, certificate: Certificate, user: User, course: Course):
        """
        Crea un certificado con borde decorativo usando WeasyPrint
        """
        # Simplemente redirigimos al método que usa WeasyPrint
        # ya que los bordes decorativos están incluidos en el HTML/CSS
        return self._create_certificate_pdf_with_weasyprint(filepath, certificate, user, course)
    
    def get_certificate_path(self, certificate_id: int) -> Optional[str]:
        """
        Obtiene la ruta local del certificado PDF
        """
        # Crear directorio si no existe
        os.makedirs(self.certificates_dir, exist_ok=True)
        
        # Construir ruta del archivo
        filename = f"certificate_{certificate_id}.pdf"
        filepath = os.path.join(self.certificates_dir, filename)
        
        # Verificar si el archivo existe
        if os.path.exists(filepath):
            return filepath
        
        return None
    
    def delete_certificate_file(self, certificate_id: int) -> bool:
        """
        Elimina el archivo PDF del certificado si existe
        """
        filepath = self.get_certificate_path(certificate_id)
        if filepath and os.path.exists(filepath):
            try:
                os.remove(filepath)
                return True
            except Exception as e:
                print(f"Error al eliminar archivo de certificado: {str(e)}")
        return False