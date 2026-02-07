from datetime import date, datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field

from app.models.occupational_exam import MedicalAptitude


class OccupationalExamBase(BaseModel):
    exam_type: Optional[str] = Field(None, description="Tipo de examen (INGRESO, PERIODICO, REINTEGRO, RETIRO)")
    exam_date: date = Field(..., description="Fecha del examen")
    departamento: Optional[str] = Field(None, description="Departamento (Art. 15)")
    ciudad: Optional[str] = Field(None, description="Ciudad (Art. 15)")
    programa: Optional[str] = Field(None, description="Programa asociado al examen")
    duracion_cargo_actual_meses: Optional[int] = Field(None, description="Duración cargo actual en meses (Art. 15)")
    factores_riesgo_evaluados: Optional[List[Dict[str, Any]]] = Field(None, description="Factores de riesgo evaluados (JSON) (Art. 15)")
    cargo_id_momento_examen: Optional[int] = Field(None, description="Cargo (ID) al momento del examen (Art. 15)")
    occupational_conclusions: Optional[str] = Field(None, description="Conclusiones ocupacionales")
    preventive_occupational_behaviors: Optional[str] = Field(None, description="Conductas ocupacionales a prevenir")
    general_recommendations: Optional[str] = Field(None, description="Recomendaciones generales")
    medical_aptitude_concept: MedicalAptitude = Field(..., description="Concepto médico de aptitud ocupacional")
    observations: Optional[str] = Field(None, description="Observaciones adicionales")
    examining_doctor: Optional[str] = Field(None, description="Médico que realizó el examen")
    medical_center: Optional[str] = Field(None, description="Centro médico donde se realizó")
    pdf_file_path: Optional[str] = Field(None, description="Ruta del archivo PDF del examen")
    requires_follow_up: Optional[bool] = Field(False, description="Indica si el examen requiere seguimiento")
    supplier_id: Optional[int] = Field(None, description="ID del centro médico/proveedor")
    doctor_id: Optional[int] = Field(None, description="ID del médico examinador")


class OccupationalExamCreate(OccupationalExamBase):
    worker_id: int = Field(..., description="ID del trabajador")


class OccupationalExamUpdate(BaseModel):
    exam_type: Optional[str] = Field(None, description="Tipo de examen (INGRESO, PERIODICO, REINTEGRO, RETIRO)")
    exam_date: Optional[date] = Field(None, description="Fecha del examen")
    departamento: Optional[str] = Field(None, description="Departamento (Art. 15)")
    ciudad: Optional[str] = Field(None, description="Ciudad (Art. 15)")
    programa: Optional[str] = Field(None, description="Programa asociado al examen")
    duracion_cargo_actual_meses: Optional[int] = Field(None, description="Duración cargo actual en meses (Art. 15)")
    factores_riesgo_evaluados: Optional[List[Dict[str, Any]]] = Field(None, description="Factores de riesgo evaluados (JSON) (Art. 15)")
    cargo_id_momento_examen: Optional[int] = Field(None, description="Cargo (ID) al momento del examen (Art. 15)")
    occupational_conclusions: Optional[str] = Field(None, description="Conclusiones ocupacionales")
    preventive_occupational_behaviors: Optional[str] = Field(None, description="Conductas ocupacionales a prevenir")
    general_recommendations: Optional[str] = Field(None, description="Recomendaciones generales")
    medical_aptitude_concept: Optional[MedicalAptitude] = Field(None, description="Concepto médico de aptitud ocupacional")
    observations: Optional[str] = Field(None, description="Observaciones adicionales")
    examining_doctor: Optional[str] = Field(None, description="Médico que realizó el examen")
    medical_center: Optional[str] = Field(None, description="Centro médico donde se realizó")
    pdf_file_path: Optional[str] = Field(None, description="Ruta del archivo PDF del examen")
    requires_follow_up: Optional[bool] = Field(None, description="Indica si el examen requiere seguimiento")
    supplier_id: Optional[int] = Field(None, description="ID del centro médico/proveedor")
    doctor_id: Optional[int] = Field(None, description="ID del médico examinador")


class OccupationalExamResponse(OccupationalExamBase):
    id: int
    worker_id: int
    worker_name: Optional[str] = Field(None, description="Nombre completo del trabajador")
    worker_document: Optional[str] = Field(None, description="Número de documento del trabajador")
    worker_position: Optional[str] = Field(None, description="Cargo del trabajador")
    worker_hire_date: Optional[str] = Field(None, description="Fecha de ingreso del trabajador")
    next_exam_date: Optional[str] = Field(None, description="Fecha del próximo examen")

    # Campos legacy para compatibilidad con el frontend
    status: Optional[str] = Field("realizado", description="Estado del examen (legacy)")
    result: Optional[str] = Field(None, description="Resultado del examen (legacy)")
    restrictions: Optional[str] = Field(None, description="Restricciones (legacy)")

    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class OccupationalExamListResponse(BaseModel):
    id: int
    exam_type: Optional[str] = None
    exam_date: date
    medical_aptitude_concept: MedicalAptitude
    examining_doctor: Optional[str]
    medical_center: Optional[str]
    created_at: datetime

    class Config:
        from_attributes = True
