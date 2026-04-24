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


class ErgonomicSelfInspection(Base):
    __tablename__ = "ergonomic_self_inspections"

    id = Column(Integer, primary_key=True, index=True)
    worker_id = Column(Integer, ForeignKey("workers.id"), nullable=False)
    evaluation_date = Column(Date, nullable=False)

    month_year = Column(String(7), nullable=True)
    modality = Column(String(20), nullable=True)
    evaluator_name = Column(String(200), nullable=True)

    chair_height_check = Column(Boolean, nullable=True)
    chair_height_obs = Column(Text, nullable=True)
    chair_lumbar_check = Column(Boolean, nullable=True)
    chair_lumbar_obs = Column(Text, nullable=True)
    chair_armrests_check = Column(Boolean, nullable=True)
    chair_armrests_obs = Column(Text, nullable=True)
    chair_condition_check = Column(Boolean, nullable=True)
    chair_condition_obs = Column(Text, nullable=True)

    desk_elbows_90_check = Column(Boolean, nullable=True)
    desk_elbows_90_obs = Column(Text, nullable=True)
    desk_leg_space_check = Column(Boolean, nullable=True)
    desk_leg_space_obs = Column(Text, nullable=True)
    desk_edges_check = Column(Boolean, nullable=True)
    desk_edges_obs = Column(Text, nullable=True)

    monitor_eye_level_check = Column(Boolean, nullable=True)
    monitor_eye_level_obs = Column(Text, nullable=True)
    monitor_distance_check = Column(Boolean, nullable=True)
    monitor_distance_obs = Column(Text, nullable=True)
    monitor_glare_check = Column(Boolean, nullable=True)
    monitor_glare_obs = Column(Text, nullable=True)
    laptop_setup_check = Column(Boolean, nullable=True)
    laptop_setup_obs = Column(Text, nullable=True)

    keyboard_mouse_level_check = Column(Boolean, nullable=True)
    keyboard_mouse_level_obs = Column(Text, nullable=True)
    wrist_rest_check = Column(Boolean, nullable=True)
    wrist_rest_obs = Column(Text, nullable=True)
    wrists_neutral_check = Column(Boolean, nullable=True)
    wrists_neutral_obs = Column(Text, nullable=True)

    lighting_reflection_check = Column(Boolean, nullable=True)
    lighting_reflection_obs = Column(Text, nullable=True)
    feet_on_floor_check = Column(Boolean, nullable=True)
    feet_on_floor_obs = Column(Text, nullable=True)
    active_breaks_check = Column(Boolean, nullable=True)
    active_breaks_obs = Column(Text, nullable=True)
    no_pain_check = Column(Boolean, nullable=True)
    no_pain_obs = Column(Text, nullable=True)

    pain_discomfort = Column(Boolean, nullable=True)
    pain_region = Column(String(120), nullable=True)
    pain_intensity = Column(Integer, nullable=True)
    report_description = Column(Text, nullable=True)
    needs_medical_attention = Column(Boolean, nullable=True)

    worker_signature = Column(String(255), nullable=True)
    sst_signature = Column(String(255), nullable=True)
    status = Column(String(20), default="PENDING")
    sst_management_data = Column(Text, nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    created_by = Column(Integer, ForeignKey("users.id"), nullable=True)

    worker = relationship("Worker", backref="ergonomic_self_inspections")
    creator = relationship("User", foreign_keys=[created_by])
