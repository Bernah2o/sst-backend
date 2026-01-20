import os
import tempfile
import base64
from datetime import datetime
from typing import Optional, Dict, Any
from sqlalchemy.orm import Session

from app.models.user import User
from app.models.seguimiento import Seguimiento
from app.models.worker import Worker
from app.models.occupational_exam import OccupationalExam
from app.utils.storage import StorageManager
from app.services.html_to_pdf import HTMLToPDFConverter
from app.config import settings


class MedicalRecommendationGenerator:
    def __init__(self, db: Session):
        self.db = db
        self.storage_manager = StorageManager()
        self.reports_dir = "medical_reports"
        self.html_to_pdf = HTMLToPDFConverter()
        
        # Crear directorio local si no existe (para fallback)
        if not os.path.exists(self.reports_dir):
            os.makedirs(self.reports_dir)
    
    async def generate_medical_recommendation_pdf(self, seguimiento_id: int) -> str:
        """
        Genera un PDF de notificación de recomendaciones médicas usando HTML y retorna la URL del archivo
        """
        # Obtener datos del seguimiento
        seguimiento = self.db.query(Seguimiento).filter(Seguimiento.id == seguimiento_id).first()
        if not seguimiento:
            raise ValueError("Seguimiento not found")
        
        worker = self.db.query(Worker).filter(Worker.id == seguimiento.worker_id).first()
        if not worker:
            raise ValueError("Worker not found")
        
        # Obtener el examen ocupacional más reciente del trabajador
        from sqlalchemy.orm import joinedload
        latest_exam = self.db.query(OccupationalExam).options(
            joinedload(OccupationalExam.doctor)
        ).filter(
            OccupationalExam.worker_id == seguimiento.worker_id
        ).order_by(OccupationalExam.exam_date.desc()).first()
        
        # Generar nombre del archivo
        filename = f"recomendaciones_medicas_{worker.document_number}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
        local_filepath = os.path.join(self.reports_dir, filename)
        
        # Preparar contexto para la plantilla HTML
        context = self._prepare_template_context(worker, latest_exam, seguimiento)
        
        # Generar PDF usando HTML
        await self._create_medical_recommendation_pdf_from_html(local_filepath, context)
        
        
        # Usar ruta local
        return f"/medical_reports/{filename}"
    
    def _prepare_template_context(self, worker, exam, seguimiento):
        """Prepara el contexto de datos para la plantilla HTML"""
        from datetime import datetime
        
        # Datos del trabajador
        worker_data = {
            'first_name': worker.first_name,
            'last_name': worker.last_name,
            'document_number': worker.document_number,
            'fecha_de_ingreso': worker.fecha_de_ingreso,  # Usar el campo correcto del modelo
            'position': worker.position,  # Usar position en lugar de cargo
            'cargo': {'name': worker.position} if worker.position else None  # Simular la estructura cargo.name para la plantilla
        }
        
        # Calcular próximo examen
        next_exam_date = self._calculate_next_exam_date(exam) if exam else None
        
        # Obtener información del médico examinador
        examining_doctor_name = self._get_examining_doctor_name(exam)
        
        # Datos del examen ocupacional
        exam_data = {
            'exam_type': exam.exam_type if exam else 'Examen de Ingreso',
            'exam_date': exam.exam_date if exam else None,
            'medical_aptitude_concept': exam.medical_aptitude_concept if exam else 'Apto',  # Usar el campo correcto
            'examining_doctor': examining_doctor_name,
            'medical_center': exam.medical_center if exam else 'Laboratorios Nancy Flórez Garcial A.S',
            'observations': exam.observations if exam else 'EXAMEN FÍSICO DE INGRESO CON ÉNFASIS OSTEOMUSCULAR, SIN ALTERACIÓN AL MOMENTO DE ESTE EXAMEN MÉDICO.',
            'occupational_conclusions': exam.occupational_conclusions if exam else None,
            'preventive_occupational_behaviors': exam.preventive_occupational_behaviors if exam else None,
            'general_recommendations': exam.general_recommendations if exam else None,
            'next_exam_date': next_exam_date
        }
        
        # Datos del seguimiento
        seguimiento_data = {
            'observations': seguimiento.observacion if seguimiento else 'EXAMEN FÍSICO DE INGRESO CON ÉNFASIS OSTEOMUSCULAR, SIN ALTERACIÓN AL MOMENTO DE ESTE EXAMEN MÉDICO',
            'observaciones_examen': seguimiento.observaciones_examen if seguimiento else None,
            'comentario': seguimiento.comentario if seguimiento else None,
            'programa': seguimiento.programa if seguimiento else None,
            'valoracion_riesgo': seguimiento.valoracion_riesgo if seguimiento else None,
            'motivo_inclusion': seguimiento.motivo_inclusion if seguimiento else None,
            'created_by_user': None  # El modelo Seguimiento no tiene relación con User
        }
        
        # Cargar logo como base64
        company_logo = ""
        try:
            logo_path = os.path.join(self.html_to_pdf.template_dir, "logo_3.png")
            if os.path.exists(logo_path):
                with open(logo_path, "rb") as image_file:
                    encoded_string = base64.b64encode(image_file.read()).decode('utf-8')
                    company_logo = f"data:image/png;base64,{encoded_string}"
        except Exception as e:
            print(f"Error loading logo: {e}")
        
        return {
            'worker': worker_data,
            'exam': exam_data,
            'seguimiento': seguimiento_data,
            'current_date': datetime.now().strftime('%d/%m/%Y'),
            'company_logo': company_logo
        }
    
    async def _create_medical_recommendation_pdf_from_html(self, filepath: str, context: Dict[str, Any]):
        """
        Crea el archivo PDF usando la plantilla HTML y WeasyPrint
        """
        try:
            # Generar PDF usando el convertidor HTML
            await self.html_to_pdf.generate_pdf_from_template(
                template_name="medical_recommendation.html",
                context=context,
                output_path=filepath
            )
        except Exception as e:
            raise Exception(f"Error generando PDF desde HTML: {str(e)}")
    
    def _calculate_next_exam_date(self, exam) -> Optional[str]:
        """
        Calcula la fecha del próximo examen basado en el tipo de examen actual
        """
        if not exam or not exam.exam_date:
            return None
        
        from dateutil.relativedelta import relativedelta
        
        # Definir intervalos según el tipo de examen
        intervals = {
            'examen_ingreso': 12,  # 1 año
            'examen_periodico': 12,  # 1 año
            'examen_reintegro': 12,  # 1 año
            'examen_retiro': None  # No aplica próximo examen
        }
        
        exam_type = exam.exam_type
        if exam_type not in intervals or intervals[exam_type] is None:
            return None
        
        try:
            next_date = exam.exam_date + relativedelta(months=intervals[exam_type])
            return next_date.strftime('%d/%m/%Y')
        except Exception:
            return None
    
    def _get_examining_doctor_name(self, exam) -> str:
        """
        Obtiene el nombre del médico examinador desde la relación doctor o campo legacy
        """
        if not exam:
            return 'HELDA NUÑEZ'  # Valor por defecto
        
        # Intentar obtener desde la relación doctor
        if hasattr(exam, 'doctor') and exam.doctor:
            return f"{exam.doctor.first_name} {exam.doctor.last_name}".strip()
        
        # Fallback al campo legacy examining_doctor
        if exam.examining_doctor:
            return exam.examining_doctor
        
        # Valor por defecto si no hay información
        return 'HELDA NUÑEZ'
    
    def get_report_path(self, filename: str) -> Optional[str]:
        """
        Obtiene la ruta completa de un reporte
        """
        filepath = os.path.join(self.reports_dir, filename)
        if os.path.exists(filepath):
            return filepath
        return None
    
    def delete_report_file(self, filename: str) -> bool:
        """
        Elimina un archivo de reporte
        """
        try:
            filepath = os.path.join(self.reports_dir, filename)
            if os.path.exists(filepath):
                os.remove(filepath)
                return True
        except Exception as e:
            print(f"Error deleting report file: {e}")
        return False