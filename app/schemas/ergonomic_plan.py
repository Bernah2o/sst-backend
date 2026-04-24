from typing import Optional, List
from datetime import date, datetime
from pydantic import BaseModel, ConfigDict


class ErgonomicMeasureBase(BaseModel):
    measure_type: str
    description: str
    responsible: str
    commitment_date: Optional[date] = None
    status: str = "pendiente"


class ErgonomicMeasureCreate(ErgonomicMeasureBase):
    pass


class ErgonomicMeasureUpdate(ErgonomicMeasureBase):
    pass


class ErgonomicMeasureResponse(ErgonomicMeasureBase):
    id: int
    plan_id: int
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ErgonomicActionPlanBase(BaseModel):
    non_compliant_items: Optional[str] = None       # JSON array string
    primary_risk: Optional[str] = None
    finding_description: Optional[str] = None
    work_frequency: Optional[str] = None
    sst_conclusion: Optional[str] = None
    sst_conclusion_custom: Optional[str] = None
    worker_accepts: bool = False
    worker_agreement_name: Optional[str] = None
    worker_agreement_date: Optional[date] = None
    worker_signature: Optional[str] = None
    sst_approver_name: Optional[str] = None
    sst_approval_date: Optional[date] = None
    sst_signature: Optional[str] = None
    verification_date: Optional[date] = None
    verification_method: Optional[str] = None
    followup_result: Optional[str] = None
    followup_decision: Optional[str] = None
    final_observations: Optional[str] = None
    plan_status: str = "OPEN"


class ErgonomicActionPlanCreate(ErgonomicActionPlanBase):
    assessment_id: int
    worker_id: int
    measures: Optional[List[ErgonomicMeasureCreate]] = None


class ErgonomicActionPlanUpdate(ErgonomicActionPlanBase):
    measures: Optional[List[ErgonomicMeasureCreate]] = None


class WorkerBasicInfo(BaseModel):
    id: int
    first_name: str
    last_name: str
    document_number: str
    position: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class ErgonomicActionPlanResponse(ErgonomicActionPlanBase):
    id: int
    assessment_id: int
    worker_id: int
    created_by: Optional[int] = None
    created_at: datetime
    updated_at: datetime
    measures: List[ErgonomicMeasureResponse] = []
    worker: Optional[WorkerBasicInfo] = None

    model_config = ConfigDict(from_attributes=True)


class ErgonomicFollowupUpdate(BaseModel):
    verification_date: date
    verification_method: str
    followup_result: str
    followup_decision: str
    final_observations: Optional[str] = None
    sst_signature: Optional[str] = None
    sst_approver_name: Optional[str] = None
    sst_approval_date: Optional[date] = None
