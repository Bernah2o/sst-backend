from datetime import date, datetime
from typing import Optional
from pydantic import BaseModel, Field

from app.models.occupational_exam import ExamType, MedicalAptitude


class OccupationalExamBase(BaseModel):
    exam_type: ExamType = Field(..., description="Tipo de examen ocupacional")
    exam_date: date = Field(..., description="Fecha del examen")
    programa: Optional[str] = Field(None, description="Programa asociado al examen")
    occupational_conclusions: Optional[str] = Field(None, description="Conclusiones ocupacionales")
    preventive_occupational_behaviors: Optional[str] = Field(None, description="Conductas ocupacionales a prevenir")
    general_recommendations: Optional[str] = Field(None, description="Recomendaciones generales")
    medical_aptitude_concept: MedicalAptitude = Field(..., description="Concepto médico de aptitud ocupacional")
    observations: Optional[str] = Field(None, description="Observaciones adicionales")
    examining_doctor: Optional[str] = Field(None, description="Médico que realizó el examen")
    medical_center: Optional[str] = Field(None, description="Centro médico donde se realizó")


class OccupationalExamCreate(OccupationalExamBase):
    worker_id: int = Field(..., description="ID del trabajador")


class OccupationalExamUpdate(BaseModel):
    exam_type: Optional[ExamType] = Field(None, description="Tipo de examen ocupacional")
    exam_date: Optional[date] = Field(None, description="Fecha del examen")
    programa: Optional[str] = Field(None, description="Programa asociado al examen")
    occupational_conclusions: Optional[str] = Field(None, description="Conclusiones ocupacionales")
    preventive_occupational_behaviors: Optional[str] = Field(None, description="Conductas ocupacionales a prevenir")
    general_recommendations: Optional[str] = Field(None, description="Recomendaciones generales")
    medical_aptitude_concept: Optional[MedicalAptitude] = Field(None, description="Concepto médico de aptitud ocupacional")
    observations: Optional[str] = Field(None, description="Observaciones adicionales")
    examining_doctor: Optional[str] = Field(None, description="Médico que realizó el examen")
    medical_center: Optional[str] = Field(None, description="Centro médico donde se realizó")


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
    exam_type: ExamType
    exam_date: date
    medical_aptitude_concept: MedicalAptitude
    examining_doctor: Optional[str]
    medical_center: Optional[str]
    created_at: datetime

    class Config:
        from_attributes = True