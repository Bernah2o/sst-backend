from datetime import datetime
from typing import List, Dict, Any, Optional
from pydantic import BaseModel


class SupervisorStats(BaseModel):
    total_employees: int
    active_employees: int
    inactive_employees: int
    employees_in_training: int
    completed_trainings: int
    pending_evaluations: int
    compliance_rate: float
    expired_trainings: int


class TeamMember(BaseModel):
    id: int
    name: str
    position: str
    active_courses: int
    completed_courses: int
    status: str
    last_activity: Optional[str]


class TrainingAlert(BaseModel):
    id: str
    employee_name: str
    training_name: str
    due_date: Optional[str] = None
    priority: str  # "high", "medium", "low"
    days_overdue: int


class ComplianceData(BaseModel):
    course_id: int
    course_name: str
    total_enrolled: int
    completed: int
    compliance_percentage: float


class SupervisorDashboardResponse(BaseModel):
    stats: SupervisorStats
    team_members: List[TeamMember]
    training_alerts: List[TrainingAlert]
    compliance_data: List[ComplianceData]
    
    class Config:
        from_attributes = True