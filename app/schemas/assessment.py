from typing import Optional, List, Dict
from datetime import date, datetime
from pydantic import BaseModel

class HomeworkAssessmentBase(BaseModel):
    evaluation_date: date
    
    # Checks y Observaciones
    lighting_check: bool = False
    lighting_obs: Optional[str] = None
    
    ventilation_check: bool = False
    ventilation_obs: Optional[str] = None
    
    desk_check: bool = False
    desk_obs: Optional[str] = None
    
    chair_check: bool = False
    chair_obs: Optional[str] = None
    
    screen_check: bool = False
    screen_obs: Optional[str] = None
    
    mouse_keyboard_check: bool = False
    mouse_keyboard_obs: Optional[str] = None
    
    space_check: bool = False
    space_obs: Optional[str] = None
    
    floor_check: bool = False
    floor_obs: Optional[str] = None
    
    noise_check: bool = False
    noise_obs: Optional[str] = None
    
    connectivity_check: bool = False
    connectivity_obs: Optional[str] = None
    
    equipment_check: bool = False
    equipment_obs: Optional[str] = None
    
    confidentiality_check: bool = False
    confidentiality_obs: Optional[str] = None
    
    active_breaks_check: bool = False
    active_breaks_obs: Optional[str] = None
    
    psychosocial_check: bool = False
    psychosocial_obs: Optional[str] = None
    
    sst_observations: Optional[str] = None
    home_address: Optional[str] = None
    status: Optional[str] = "PENDING"
    sst_management_data: Optional[str] = None

class HomeworkAssessmentCreate(HomeworkAssessmentBase):
    worker_id: int
    worker_signature: Optional[str] = None  # Base64 string para creación
    sst_signature: Optional[str] = None     # Base64 string para creación
    photos: Optional[Dict[str, str]] = None # Dict {tipo: base64}
    attachments: Optional[Dict[str, str]] = None # Dict {nombre: url}

class HomeworkAssessmentUpdate(HomeworkAssessmentBase):
    pass

# Schema para datos mínimos del worker en la respuesta
class WorkerBasicInfo(BaseModel):
    first_name: str
    last_name: str
    document_number: str
    email: str

    class Config:
        from_attributes = True

class HomeworkAssessment(HomeworkAssessmentBase):
    id: int
    worker_id: int
    worker_signature: Optional[str] = None
    sst_signature: Optional[str] = None
    photos_data: Optional[str] = None
    attachments_data: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    created_by: Optional[int] = None
    worker: Optional[WorkerBasicInfo] = None  # Información del trabajador

    class Config:
        from_attributes = True

class BulkAssessmentCreate(BaseModel):
    worker_ids: List[int]
    evaluation_date: date
