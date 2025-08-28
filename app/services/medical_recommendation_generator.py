import os
import io
from datetime import datetime
from typing import Optional, Dict, Any
from reportlab.lib.pagesizes import letter, A4
from reportlab.lib.units import inch, cm
from reportlab.lib.colors import Color, black, white, darkblue
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Image, Table, TableStyle, PageBreak, KeepTogether
from reportlab.pdfgen import canvas
from reportlab.lib.utils import ImageReader
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from PIL import Image as PILImage
from sqlalchemy.orm import Session

from app.models.user import User
from app.models.seguimiento import Seguimiento
from app.models.worker import Worker
from app.models.occupational_exam import OccupationalExam
from app.utils.storage import StorageManager
from app.config import settings


class MedicalRecommendationGenerator:
    def __init__(self, db: Session):
        self.db = db
        self.storage_manager = StorageManager()
        self.reports_dir = "medical_reports"
        
        # Crear directorio local si no existe (para fallback)
        if not os.path.exists(self.reports_dir):
            os.makedirs(self.reports_dir)
    
    async def generate_medical_recommendation_pdf(self, seguimiento_id: int) -> str:
        """
        Genera un PDF de notificación de recomendaciones médicas y retorna la URL del archivo
        """
        # Obtener datos del seguimiento
        seguimiento = self.db.query(Seguimiento).filter(Seguimiento.id == seguimiento_id).first()
        if not seguimiento:
            raise ValueError("Seguimiento not found")
        
        worker = self.db.query(Worker).filter(Worker.id == seguimiento.worker_id).first()
        if not worker:
            raise ValueError("Worker not found")
        
        # Obtener el examen ocupacional más reciente del trabajador
        latest_exam = self.db.query(OccupationalExam).filter(
            OccupationalExam.worker_id == seguimiento.worker_id
        ).order_by(OccupationalExam.exam_date.desc()).first()
        
        # Generar nombre del archivo
        filename = f"recomendaciones_medicas_{worker.document_number}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
        local_filepath = os.path.join(self.reports_dir, filename)
        
        # Crear el PDF localmente
        self._create_medical_recommendation_pdf(local_filepath, seguimiento, worker, latest_exam)
        
        # Subir a Firebase Storage si está habilitado
        if settings.use_firebase_storage:
            firebase_path = f"{settings.firebase_medical_reports_path}/{filename}"
            file_url = await self.storage_manager.upload_file(
                local_filepath, 
                firebase_path,
                storage_type="firebase"
            )
            
            # Limpiar archivo local después de subir
            try:
                os.remove(local_filepath)
            except OSError:
                pass
                
            return file_url
        else:
            # Usar ruta local
            return f"/medical_reports/{filename}"
    
    def _create_medical_recommendation_pdf(self, filepath: str, seguimiento: Seguimiento, worker: Worker, exam: Optional[OccupationalExam]):
        """
        Crea el archivo PDF de notificación de recomendaciones médicas con diseño profesional
        """
        # Configurar el documento con márgenes optimizados
        doc = SimpleDocTemplate(
            filepath,
            pagesize=A4,
            rightMargin=1.5*cm,
            leftMargin=1.5*cm,
            topMargin=2*cm,
            bottomMargin=1.5*cm,
            title="Notificación de Recomendaciones Médicas Ocupacionales",
            author="Sistema SST",
            subject="Recomendaciones Médicas Ocupacionales"
        )
        
        # Obtener estilos base
        styles = getSampleStyleSheet()
        
        # Paleta de colores corporativa profesional
        primary_blue = Color(0.12, 0.29, 0.53, 1)    # Azul corporativo principal
        secondary_blue = Color(0.85, 0.91, 0.98, 1)  # Azul claro para fondos
        accent_blue = Color(0.25, 0.41, 0.67, 1)     # Azul de acento
        text_dark = Color(0.13, 0.13, 0.13, 1)       # Texto principal
        text_medium = Color(0.35, 0.35, 0.35, 1)     # Texto secundario
        border_gray = Color(0.75, 0.75, 0.75, 1)     # Bordes de tablas
        background_light = Color(0.98, 0.98, 0.98, 1) # Fondo claro
        
        # Crear estilos tipográficos profesionales
        title_style = ParagraphStyle(
            'DocumentTitle',
            parent=styles['Heading1'],
            fontSize=18,
            spaceAfter=30,
            spaceBefore=20,
            alignment=TA_CENTER,
            textColor=primary_blue,
            fontName='Helvetica-Bold',
            leading=22,
            borderWidth=0,
            borderPadding=0
        )
        
        section_header_style = ParagraphStyle(
            'SectionHeader',
            parent=styles['Heading2'],
            fontSize=13,
            spaceAfter=12,
            spaceBefore=20,
            alignment=TA_LEFT,
            textColor=primary_blue,
            fontName='Helvetica-Bold',
            leading=16,
            borderWidth=1,
            borderColor=primary_blue,
            borderPadding=8,
            backColor=secondary_blue,
            leftIndent=0,
            rightIndent=0
        )
        
        body_text_style = ParagraphStyle(
            'BodyText',
            parent=styles['Normal'],
            fontSize=11,
            spaceAfter=10,
            spaceBefore=2,
            alignment=TA_LEFT,
            fontName='Helvetica',
            textColor=text_dark,
            leading=14,
            leftIndent=0
        )
        
        justified_text_style = ParagraphStyle(
            'JustifiedText',
            parent=styles['Normal'],
            fontSize=11,
            spaceAfter=12,
            spaceBefore=4,
            alignment=TA_LEFT,
            fontName='Helvetica',
            textColor=text_dark,
            leading=15,
            leftIndent=10,
            rightIndent=10
        )
        
        label_style = ParagraphStyle(
            'LabelText',
            parent=styles['Normal'],
            fontSize=10,
            spaceAfter=6,
            alignment=TA_LEFT,
            fontName='Helvetica-Bold',
            textColor=accent_blue,
            leading=12
        )
        
        date_style = ParagraphStyle(
            'DateText',
            parent=styles['Normal'],
            fontSize=10,
            spaceAfter=15,
            alignment=TA_RIGHT,
            fontName='Helvetica',
            textColor=text_medium,
            leading=12
        )
        
        # Contenido del documento
        story = []
        
        # Encabezado corporativo profesional
        header_data = [[
            "SISTEMA DE GESTIÓN DE SEGURIDAD Y SALUD EN EL TRABAJO",
            datetime.now().strftime("%d de %B de %Y")
        ]]
        
        header_table = Table(header_data, colWidths=[5*inch, 2*inch])
        header_table.setStyle(TableStyle([
            ('FONTNAME', (0, 0), (0, 0), 'Helvetica-Bold'),
            ('FONTNAME', (1, 0), (1, 0), 'Helvetica'),
            ('FONTSIZE', (0, 0), (0, 0), 12),
            ('FONTSIZE', (1, 0), (1, 0), 10),
            ('TEXTCOLOR', (0, 0), (0, 0), primary_blue),
            ('TEXTCOLOR', (1, 0), (1, 0), text_medium),
            ('ALIGN', (0, 0), (0, 0), 'LEFT'),
            ('ALIGN', (1, 0), (1, 0), 'RIGHT'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 15),
            ('LINEBELOW', (0, 0), (-1, -1), 2, primary_blue)
        ]))
        
        story.append(header_table)
        story.append(Spacer(1, 10))
        
        # Título principal con diseño mejorado
        story.append(Paragraph(
            "NOTIFICACIÓN DE RECOMENDACIONES<br/>DE LOS EXÁMENES MÉDICOS OCUPACIONALES", 
            title_style
        ))
        story.append(Spacer(1, 6))
        
        # Información de fecha y documento
        doc_info_data = [[
            f"Fecha de emisión: {datetime.now().strftime('%d de %B de %Y')}",
            f"Documento No: MED-{datetime.now().strftime('%Y%m%d')}-{seguimiento.id:04d}"
        ]]
        
        doc_info_table = Table(doc_info_data, colWidths=[4*inch, 4*inch])
        doc_info_table.setStyle(TableStyle([
            ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 0), (-1, -1), 9),
            ('TEXTCOLOR', (0, 0), (-1, -1), text_medium),
            ('ALIGN', (0, 0), (0, 0), 'LEFT'),
            ('ALIGN', (1, 0), (1, 0), 'RIGHT'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 10)
        ]))
        
        story.append(doc_info_table)
        story.append(Spacer(1, 12))
        
        # Sección de información del trabajador
        story.append(Paragraph("INFORMACIÓN DEL TRABAJADOR", section_header_style))
        story.append(Spacer(1, 8))
        
        worker_data = [
            ["Nombre completo:", worker.full_name or "No especificado"],
            ["Cargo/Posición:", worker.position or "No especificado"],
            ["Número de documento:", worker.document_number or "No especificado"],
            ["Área de trabajo:", getattr(worker, 'work_area', 'No especificado')]
        ]
        
        worker_table = Table(worker_data, colWidths=[2.8*inch, 5*inch])
        worker_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (0, -1), secondary_blue),
            ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
            ('FONTNAME', (1, 0), (1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 0), (-1, -1), 11),
            ('TEXTCOLOR', (0, 0), (0, -1), primary_blue),
            ('TEXTCOLOR', (1, 0), (1, -1), text_dark),
            ('ALIGN', (0, 0), (0, -1), 'LEFT'),
            ('ALIGN', (1, 0), (1, -1), 'LEFT'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('GRID', (0, 0), (-1, -1), 1, border_gray),
            ('LEFTPADDING', (0, 0), (-1, -1), 8),
            ('RIGHTPADDING', (0, 0), (-1, -1), 8),
            ('TOPPADDING', (0, 0), (-1, -1), 6),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
            ('ROWBACKGROUNDS', (0, 0), (-1, -1), [secondary_blue, white])
        ]))
        
        story.append(KeepTogether([worker_table]))
        story.append(Spacer(1, 12))
        
        # Sección: EXAMEN REALIZADO
        story.append(Paragraph("EXAMEN MÉDICO OCUPACIONAL REALIZADO", section_header_style))
        story.append(Spacer(1, 8))
        
        exam_type_display = "No especificado"
        exam_date_display = "No especificado"
        
        if exam:
            exam_type_map = {
                "examen_ingreso": "Examen de Ingreso",
                "examen_periodico": "Examen Periódico",
                "examen_reintegro": "Examen de Reintegro",
                "examen_retiro": "Examen de Retiro"
            }
            exam_type_display = exam_type_map.get(exam.exam_type, exam.exam_type)
            if exam.exam_date:
                exam_date_display = exam.exam_date.strftime("%d de %B de %Y")
        
        exam_data = [
            ["Tipo de examen:", exam_type_display],
            ["Fecha del examen:", exam_date_display],
            ["Estado:", "Completado"]
        ]
        
        exam_table = Table(exam_data, colWidths=[2.8*inch, 5*inch])
        exam_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (0, -1), background_light),
            ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
            ('FONTNAME', (1, 0), (1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 0), (-1, -1), 11),
            ('TEXTCOLOR', (0, 0), (0, -1), accent_blue),
            ('TEXTCOLOR', (1, 0), (1, -1), text_dark),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('GRID', (0, 0), (-1, -1), 1, border_gray),
            ('LEFTPADDING', (0, 0), (-1, -1), 12),
            ('RIGHTPADDING', (0, 0), (-1, -1), 12),
            ('TOPPADDING', (0, 0), (-1, -1), 8),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 8)
        ]))
        
        story.append(KeepTogether([exam_table]))
        story.append(Spacer(1, 25))
        
        # Sección: RECOMENDACIONES EMITIDAS POR EL MÉDICO LABORAL
        story.append(Paragraph("RECOMENDACIONES MÉDICAS OCUPACIONALES", section_header_style))
        story.append(Spacer(1, 15))
        
        # Motivo de inclusión en seguimiento
        motivo = seguimiento.motivo_inclusion or "No se ha especificado el motivo de inclusión en el seguimiento médico."
        story.append(Paragraph("1. MOTIVO DE INCLUSIÓN EN SEGUIMIENTO MÉDICO", label_style))
        story.append(Paragraph(motivo, justified_text_style))
        story.append(Spacer(1, 15))
        
        # Conductas ocupacionales a prevenir
        conductas = seguimiento.conductas_ocupacionales_prevenir or "No se han especificado conductas ocupacionales específicas a prevenir."
        story.append(Paragraph("2. CONDUCTAS OCUPACIONALES A PREVENIR", label_style))
        story.append(Paragraph(conductas, justified_text_style))
        story.append(Spacer(1, 15))
        
        # Recomendaciones generales
        recomendaciones = seguimiento.recomendaciones_generales or "No se han establecido recomendaciones generales específicas."
        story.append(Paragraph("3. RECOMENDACIONES GENERALES", label_style))
        story.append(Paragraph(recomendaciones, justified_text_style))
        story.append(Spacer(1, 25))
        
        # Nota importante
        nota_importante_text = (
            "<b>NOTA IMPORTANTE:</b> Las recomendaciones médicas ocupacionales son de cumplimiento obligatorio "
            "según la normatividad vigente en Seguridad y Salud en el Trabajo. El incumplimiento de estas "
            "recomendaciones puede generar riesgos para la salud del trabajador y responsabilidades legales "
            "para la empresa."
        )
        
        # Crear un estilo especial para la nota importante
        nota_style = ParagraphStyle(
            'NotaImportante',
            parent=styles['Normal'],
            fontSize=10,
            fontName='Helvetica',
            textColor=Color(0.6, 0.3, 0, 1),
            alignment=TA_LEFT,
            leftIndent=10,
            rightIndent=10,
            spaceAfter=0,
            spaceBefore=0
        )
        
        nota_paragraph = Paragraph(nota_importante_text, nota_style)
        nota_table = Table([[nota_paragraph]], colWidths=[7.8*inch])
        nota_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (0, 0), Color(1, 0.95, 0.8, 1)),  # Fondo amarillo claro
            ('VALIGN', (0, 0), (0, 0), 'MIDDLE'),
            ('GRID', (0, 0), (0, 0), 1, Color(0.8, 0.6, 0.2, 1)),  # Borde dorado
            ('LEFTPADDING', (0, 0), (0, 0), 5),
            ('RIGHTPADDING', (0, 0), (0, 0), 5),
            ('TOPPADDING', (0, 0), (0, 0), 8),
            ('BOTTOMPADDING', (0, 0), (0, 0), 8)
        ]))
        
        story.append(KeepTogether([nota_table]))
        story.append(Spacer(1, 25))
        
        # Sección: ACCIONES DEL COLABORADOR
        story.append(Paragraph("COMPROMISOS Y ACCIONES DEL TRABAJADOR", section_header_style))
        story.append(Spacer(1, 15))
        
        # Texto introductorio
        intro_text = (
            "El trabajador se compromete a cumplir con las siguientes acciones para dar seguimiento "
            "a las recomendaciones médicas ocupacionales:"
        )
        story.append(Paragraph(intro_text, body_text_style))
        story.append(Spacer(1, 12))
        
        # Compromisos del trabajador
        compromisos = [
            "• Cumplir estrictamente con las recomendaciones médicas establecidas",
            "• Informar inmediatamente cualquier cambio en su estado de salud",
            "• Asistir puntualmente a las citas médicas de seguimiento programadas",
            "• Utilizar correctamente los elementos de protección personal indicados",
            "• Participar activamente en las capacitaciones de seguridad y salud",
            "• Reportar cualquier incidente o accidente de trabajo"
        ]
        
        for compromiso in compromisos:
            story.append(Paragraph(compromiso, body_text_style))
        
        story.append(Spacer(1, 15))
        
        # Comentarios adicionales del seguimiento
        comentarios = seguimiento.comentario or "No se han registrado comentarios adicionales."
        story.append(Paragraph("OBSERVACIONES ADICIONALES:", label_style))
        story.append(Paragraph(comentarios, justified_text_style))
        story.append(Spacer(1, 15))
        
        # Sección de firmas mejorada
        story.append(Paragraph("FIRMAS Y COMPROMISOS", section_header_style))
        story.append(Spacer(1, 10))
        
        # Tabla de firmas con diseño profesional
        signature_data = [
            ["TRABAJADOR", "RESPONSABLE SST"],
            ["", ""],
            ["", ""],
            ["_" * 35, "_" * 35],
            [f"Nombre: {worker.full_name or 'N/A'}", "Nombre: ________________________"],
            [f"C.C.: {worker.document_number or 'N/A'}", "C.C.: ____________________________"],
            ["Fecha: ___________________", "Fecha: ___________________"]
        ]
        
        signature_table = Table(signature_data, colWidths=[3.9*inch, 3.9*inch])
        signature_table.setStyle(TableStyle([
            # Encabezados
            ('BACKGROUND', (0, 0), (-1, 0), secondary_blue),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 11),
            ('TEXTCOLOR', (0, 0), (-1, 0), primary_blue),
            ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
            
            # Resto de la tabla
            ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 1), (-1, -1), 10),
            ('TEXTCOLOR', (0, 1), (-1, -1), text_dark),
            ('ALIGN', (0, 1), (-1, -1), 'CENTER'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            
            # Espaciado
            ('TOPPADDING', (0, 0), (-1, -1), 6),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
            ('LEFTPADDING', (0, 0), (-1, -1), 8),
            ('RIGHTPADDING', (0, 0), (-1, -1), 8),
            
            # Bordes
            ('GRID', (0, 0), (-1, -1), 1, border_gray),
            ('LINEBELOW', (0, 0), (-1, 0), 2, primary_blue)
        ]))
        
        story.append(KeepTogether([signature_table]))
        story.append(Spacer(1, 25))
        
        # Pie de página profesional
        footer_data = [[
            "Este documento ha sido generado automáticamente por el Sistema de Gestión de Seguridad y Salud en el Trabajo",
            f"Generado el: {datetime.now().strftime('%d/%m/%Y a las %H:%M')}"
        ]]
        
        footer_table = Table(footer_data, colWidths=[5*inch, 2*inch])
        footer_table.setStyle(TableStyle([
            ('FONTNAME', (0, 0), (-1, -1), 'Helvetica-Oblique'),
            ('FONTSIZE', (0, 0), (-1, -1), 8),
            ('TEXTCOLOR', (0, 0), (-1, -1), text_medium),
            ('ALIGN', (0, 0), (0, 0), 'LEFT'),
            ('ALIGN', (1, 0), (1, 0), 'RIGHT'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('TOPPADDING', (0, 0), (-1, -1), 15),
            ('LINEABOVE', (0, 0), (-1, -1), 1, border_gray)
        ]))
        
        story.append(footer_table)
        
        # Información adicional de contacto
        story.append(Spacer(1, 10))
        contact_info = (
            "Para consultas sobre este documento, contacte al área de Seguridad y Salud en el Trabajo. "
            "Este documento tiene validez legal según la normatividad colombiana vigente."
        )
        
        contact_style = ParagraphStyle(
            'ContactInfo',
            parent=styles['Normal'],
            fontSize=7,
            alignment=TA_CENTER,
            fontName='Helvetica',
            textColor=text_medium,
            leading=9
        )
        
        story.append(Paragraph(contact_info, contact_style))
        
        # Construir el PDF
        doc.build(story)
    
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