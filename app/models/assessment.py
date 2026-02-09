from sqlalchemy import Column, Integer, String, Boolean, DateTime, Text, ForeignKey, Date
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.database import Base

class HomeworkAssessment(Base):
    __tablename__ = "homework_assessments"

    id = Column(Integer, primary_key=True, index=True)
    worker_id = Column(Integer, ForeignKey("workers.id"), nullable=False)
    evaluation_date = Column(Date, nullable=False)
    
    # Condiciones Ergonómicas y de Seguridad
    # 1. Iluminación
    lighting_check = Column(Boolean, default=False)
    lighting_obs = Column(Text, nullable=True)
    
    # 2. Ventilación
    ventilation_check = Column(Boolean, default=False)
    ventilation_obs = Column(Text, nullable=True)
    
    # 3. Mesa de Trabajo
    desk_check = Column(Boolean, default=False)
    desk_obs = Column(Text, nullable=True)
    
    # 4. Silla
    chair_check = Column(Boolean, default=False)
    chair_obs = Column(Text, nullable=True)
    
    # 5. Posición Pantalla
    screen_check = Column(Boolean, default=False)
    screen_obs = Column(Text, nullable=True)
    
    # 6. Teclado y Ratón
    mouse_keyboard_check = Column(Boolean, default=False)
    mouse_keyboard_obs = Column(Text, nullable=True)
    
    # 7. Espacio Disponible
    space_check = Column(Boolean, default=False)
    space_obs = Column(Text, nullable=True)
    
    # 8. Piso
    floor_check = Column(Boolean, default=False)
    floor_obs = Column(Text, nullable=True)
    
    # 9. Ruido Ambiental
    noise_check = Column(Boolean, default=False)
    noise_obs = Column(Text, nullable=True)
    
    # 10. Conectividad
    connectivity_check = Column(Boolean, default=False)
    connectivity_obs = Column(Text, nullable=True)
    
    # 11. Seguridad de Equipos
    equipment_check = Column(Boolean, default=False)
    equipment_obs = Column(Text, nullable=True)
    
    # 12. Confidencialidad
    confidentiality_check = Column(Boolean, default=False)
    confidentiality_obs = Column(Text, nullable=True)
    
    # 13. Pausas Activas
    active_breaks_check = Column(Boolean, default=False)
    active_breaks_obs = Column(Text, nullable=True)
    
    # 14. Riesgos Psicosociales
    psychosocial_check = Column(Boolean, default=False)
    psychosocial_obs = Column(Text, nullable=True)
    
    # Firmas y Evidencias
    worker_signature = Column(String(255), nullable=True)  # Path to signature image
    sst_signature = Column(String(255), nullable=True)     # Path to SST signature
    sst_observations = Column(Text, nullable=True)
    
    # Nuevos campos solicitados
    home_address = Column(String(255), nullable=True)
    status = Column(String(20), default="PENDING")  # PENDING, COMPLETED
    attachments_data = Column(Text, nullable=True) # JSON string: {"doc1": "url", "doc2": "url"}
    
    # Fotos (almacenadas como paths separados por coma o JSON, usaremos JSON string para flexibilidad)
    photos_data = Column(Text, nullable=True)  # JSON string: {"general": "path", "desk": "path", ...}
    
    # Seguimiento SST y Plan de Acción
    # Estructura sugerida: {"lighting": {"status": "OPEN", "action": "...", "date": "..."}, ...}
    sst_management_data = Column(Text, nullable=True) 
    
    # Metadatos
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    created_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    
    # Relaciones
    worker = relationship("Worker", backref="homework_assessments")
    creator = relationship("User", foreign_keys=[created_by])
