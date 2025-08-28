import os
import io
from datetime import datetime
from typing import Optional, Dict, Any
from reportlab.lib.pagesizes import letter, A4
from reportlab.lib.units import inch
from reportlab.lib.colors import Color, black, gold, darkblue
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Image, Table, TableStyle
from reportlab.pdfgen import canvas
from reportlab.lib.utils import ImageReader
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from PIL import Image as PILImage
from sqlalchemy.orm import Session

from app.models.certificate import Certificate
from app.models.user import User
from app.models.course import Course
from app.utils.storage import StorageManager
from app.config import settings


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
        Genera un certificado en PDF y retorna la URL del archivo
        """
        # Obtener datos del certificado
        certificate = self.db.query(Certificate).filter(Certificate.id == certificate_id).first()
        if not certificate:
            raise ValueError("Certificate not found")
        
        user = self.db.query(User).filter(User.id == certificate.user_id).first()
        course = self.db.query(Course).filter(Course.id == certificate.course_id).first()
        
        if not user or not course:
            raise ValueError("User or course not found")
        
        # Generar nombre del archivo
        filename = f"certificate_{certificate.certificate_number}.pdf"
        local_filepath = os.path.join(self.certificates_dir, filename)
        
        # Crear el PDF localmente
        self._create_certificate_pdf(local_filepath, certificate, user, course)
        
        # Subir a Firebase Storage si está habilitado
        if settings.use_firebase_storage:
            firebase_path = f"{settings.firebase_certificates_path}/{filename}"
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
                
            # Actualizar la ruta del archivo en la base de datos
            certificate.file_path = file_url
        else:
            # Usar ruta local
            certificate.file_path = local_filepath
            file_url = f"/certificates/{filename}"
        
        self.db.commit()
        
        return file_url
    
    def _create_certificate_pdf(self, filepath: str, certificate: Certificate, user: User, course: Course):
        """
        Crea el archivo PDF del certificado con diseño profesional
        """
        # Registrar fuentes estándar para asegurar compatibilidad
        try:
            # Verificar que las fuentes estén disponibles
            from reportlab.pdfbase._fontdata import standardFonts
            available_fonts = pdfmetrics.getRegisteredFontNames()
        except:
            pass
        
        # Configurar el documento con márgenes más amplios
        doc = SimpleDocTemplate(
            filepath,
            pagesize=A4,
            rightMargin=50,
            leftMargin=50,
            topMargin=50,
            bottomMargin=50
        )
        
        # Obtener estilos base
        styles = getSampleStyleSheet()
        
        # Definir colores personalizados
        primary_blue = Color(0.18, 0.31, 0.67, 1)  # Azul corporativo (#2E4FAB)
        accent_gold = Color(1.0, 0.84, 0.0, 1)     # Dorado elegante (#FFD700)
        text_gray = Color(0.17, 0.24, 0.31, 1)     # Gris oscuro (#2C3E50)
        light_blue = Color(0.85, 0.91, 0.98, 1)    # Azul claro para fondo
        
        # Crear estilos personalizados más elegantes con fuentes seguras
        title_style = ParagraphStyle(
            'CertificateTitle',
            parent=styles['Heading1'],
            fontSize=36,
            spaceAfter=30,
            spaceBefore=20,
            alignment=TA_CENTER,
            textColor=primary_blue,
            fontName='Helvetica-Bold',
            leading=42
        )
        
        subtitle_style = ParagraphStyle(
            'CertificateSubtitle',
            parent=styles['Heading2'],
            fontSize=16,
            spaceAfter=25,
            alignment=TA_CENTER,
            textColor=text_gray,
            fontName='Helvetica',
            leading=20
        )
        
        name_style = ParagraphStyle(
            'RecipientName',
            parent=styles['Heading1'],
            fontSize=32,
            spaceAfter=25,
            spaceBefore=15,
            alignment=TA_CENTER,
            textColor=primary_blue,
            fontName='Helvetica-Bold',
            leading=38
        )
        
        course_style = ParagraphStyle(
            'CourseName',
            parent=styles['Heading2'],
            fontSize=24,
            spaceAfter=30,
            spaceBefore=15,
            alignment=TA_CENTER,
            textColor=primary_blue,
            fontName='Helvetica-Bold',
            leading=28
        )
        
        body_style = ParagraphStyle(
            'CertificateBody',
            parent=styles['Normal'],
            fontSize=14,
            spaceAfter=15,
            alignment=TA_CENTER,
            fontName='Helvetica',
            textColor=text_gray,
            leading=18
        )
        
        info_style = ParagraphStyle(
            'CertificateInfo',
            parent=styles['Normal'],
            fontSize=11,
            spaceAfter=8,
            alignment=TA_LEFT,
            fontName='Helvetica',
            textColor=text_gray
        )
        
        signature_style = ParagraphStyle(
            'SignatureStyle',
            parent=styles['Normal'],
            fontSize=12,
            spaceAfter=5,
            alignment=TA_CENTER,
            fontName='Helvetica-Oblique',
            textColor=text_gray
        )
        
        # Contenido del certificado
        story = []
        
        # Título principal
        story.append(Paragraph("CERTIFICADO DE FINALIZACIÓN", title_style))
        story.append(Spacer(1, 12))
        
        # Subtítulo
        story.append(Paragraph("Se certifica que", subtitle_style))
        story.append(Spacer(1, 6))
        
        # Nombre del usuario
        story.append(Paragraph(f"<b>{user.full_name}</b>", name_style))
        story.append(Spacer(1, 6))
        
        # Cédula de Ciudadanía debajo del nombre
        story.append(Paragraph(f"Cédula de Ciudadanía: <b>{user.document_number}</b>", body_style))
        story.append(Spacer(1, 12))
        
        # Descripción del logro
        story.append(Paragraph(
            f"ha completado satisfactoriamente el curso",
            body_style
        ))
        story.append(Spacer(1, 6))
        
        # Nombre del curso
        story.append(Paragraph(f"<b>{course.title}</b>", course_style))
        story.append(Spacer(1, 18))
        
        # Información adicional
        if certificate.score_achieved:
            story.append(Paragraph(
                f"Con una calificación de: <b>{certificate.score_achieved:.1f}%</b>",
                body_style
            ))
            story.append(Spacer(1, 15))
        
        # Fecha de finalización
        completion_date = certificate.completion_date.strftime("%d de %B de %Y")
        story.append(Paragraph(
            f"Fecha de finalización: <b>{completion_date}</b>",
            body_style
        ))
        story.append(Spacer(1, 20))
        
        # Información del certificado
        cert_info = [
            ["Número de Certificado:", certificate.certificate_number],
            ["Fecha de Emisión:", certificate.issue_date.strftime("%d de %B de %Y")],
            ["Código de Verificación:", certificate.verification_code[:8] + "..."]
        ]
        
        if certificate.expiry_date:
            cert_info.append(["Fecha de Expiración:", certificate.expiry_date.strftime("%d/%m/%Y")])
        
        # Crear tabla con información del certificado con estilos mejorados
        cert_table = Table(cert_info, colWidths=[2.5*inch, 3*inch])
        cert_table.setStyle(TableStyle([
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
            ('FONTNAME', (1, 0), (1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
            ('TOPPADDING', (0, 0), (-1, -1), 6),
            ('TEXTCOLOR', (0, 0), (0, -1), text_gray),
            ('TEXTCOLOR', (1, 0), (1, -1), black),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ]))
        
        story.append(cert_table)
        story.append(Spacer(1, 15))
        
        # Línea de firma (simulada) - centrada
        story.append(Spacer(1, 3))
        story.append(Paragraph("<b>Bernardino de Aguas - Profesional en SST</b>", signature_style))
        story.append(Paragraph("Firma Autorizada", signature_style))
        story.append(Spacer(1, 2))
        
        # Construir el PDF con decoración personalizada
        def add_border_decoration(canvas, doc):
            """Añade bordes decorativos al certificado"""
            try:
                canvas.saveState()
                
                # Obtener dimensiones de la página
                width, height = A4
                
                # Borde exterior decorativo
                canvas.setStrokeColor(primary_blue)
                canvas.setLineWidth(4)
                canvas.rect(30, 30, width-60, height-60)
                
                # Borde interior
                canvas.setStrokeColor(accent_gold)
                canvas.setLineWidth(2)
                canvas.rect(45, 45, width-90, height-90)
                
                # Líneas decorativas en las esquinas
                canvas.setStrokeColor(primary_blue)
                canvas.setLineWidth(1)
                
                # Esquina superior izquierda
                canvas.line(60, height-60, 120, height-60)
                canvas.line(60, height-60, 60, height-120)
                
                # Esquina superior derecha
                canvas.line(width-120, height-60, width-60, height-60)
                canvas.line(width-60, height-60, width-60, height-120)
                
                # Esquina inferior izquierda
                canvas.line(60, 60, 120, 60)
                canvas.line(60, 60, 60, 120)
                
                # Esquina inferior derecha
                canvas.line(width-120, 60, width-60, 60)
                canvas.line(width-60, 60, width-60, 120)
                
                canvas.restoreState()
            except Exception as e:
                # Si hay error en la decoración, continuar sin ella
                print(f"Error adding border decoration: {e}")
                pass
        
        # Construir el PDF con decoración
        try:
            doc.build(story, onFirstPage=add_border_decoration)
        except Exception as e:
            # Si falla con decoración, intentar sin ella
            print(f"Error building PDF with decoration: {e}")
            doc.build(story)
    
    def create_certificate_with_border(self, filepath: str, certificate: Certificate, user: User, course: Course):
        """
        Versión alternativa con bordes decorativos
        """
        c = canvas.Canvas(filepath, pagesize=A4)
        width, height = A4
        
        # Dibujar borde decorativo
        c.setStrokeColor(darkblue)
        c.setLineWidth(3)
        c.rect(50, 50, width-100, height-100)
        
        # Borde interno
        c.setLineWidth(1)
        c.rect(70, 70, width-140, height-140)
        
        # Título
        c.setFont("Helvetica-Bold", 28)
        c.setFillColor(darkblue)
        c.drawCentredText(width/2, height-150, "CERTIFICADO DE FINALIZACIÓN")
        
        # Subtítulo
        c.setFont("Helvetica", 18)
        c.setFillColor(black)
        c.drawCentredText(width/2, height-200, "CERTIFICA QUE:")
        
        # Nombre del usuario
        c.setFont("Helvetica-Bold", 24)
        c.setFillColor(gold)
        c.drawCentredText(width/2, height-250, user.full_name)
        
        # Descripción
        c.setFont("Helvetica", 16)
        c.setFillColor(black)
        c.drawCentredText(width/2, height-300, "Ha completado satisfactoriamente el curso")
        
        # Nombre del curso
        c.setFont("Helvetica-Bold", 20)
        c.setFillColor(darkblue)
        c.drawCentredText(width/2, height-350, course.title)
        
        # Información adicional
        y_pos = height - 420
        c.setFont("Helvetica", 12)
        
        if certificate.score_achieved:
            c.drawCentredText(width/2, y_pos, f"Calificación: {certificate.score_achieved:.1f}%")
            y_pos -= 30
        
        completion_date = certificate.completion_date.strftime("%d de %B de %Y")
        c.drawCentredText(width/2, y_pos, f"Fecha de finalización: {completion_date}")
        
        # Información del certificado en la parte inferior
        c.setFont("Helvetica", 10)
        c.drawString(100, 150, f"Número de Certificado: {certificate.certificate_number}")
        c.drawString(100, 130, f"Fecha de Emisión: {certificate.issue_date.strftime('%d/%m/%Y')}")
        c.drawString(100, 110, f"Código de Verificación: {certificate.verification_code}")
        
        # Línea de firma
        c.line(width-250, 200, width-100, 200)
        c.drawString(width-220, 180, "Firma Autorizada")
        
        c.save()
    
    def get_certificate_path(self, certificate_id: int) -> Optional[str]:
        """
        Obtiene la ruta del certificado si existe
        """
        certificate = self.db.query(Certificate).filter(Certificate.id == certificate_id).first()
        if certificate and certificate.file_path and os.path.exists(certificate.file_path):
            return certificate.file_path
        return None
    
    def delete_certificate_file(self, certificate_id: int) -> bool:
        """
        Elimina el archivo PDF del certificado
        """
        certificate = self.db.query(Certificate).filter(Certificate.id == certificate_id).first()
        if certificate and certificate.file_path and os.path.exists(certificate.file_path):
            try:
                os.remove(certificate.file_path)
                certificate.file_path = None
                self.db.commit()
                return True
            except Exception:
                return False
        return False