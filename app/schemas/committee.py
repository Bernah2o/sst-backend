"""
Pydantic schemas for Committee Management System
"""
from datetime import datetime, date
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field, AliasChoices, validator, computed_field, ConfigDict
from enum import Enum

# Enums
class CommitteeTypeEnum(str, Enum):
    COPASST = "copasst"
    CONVIVENCIA = "convivencia"

class CommitteeRoleEnum(str, Enum):
    PRESIDENT = "PRESIDENT"
    VICE_PRESIDENT = "VICE_PRESIDENT"
    SECRETARY = "SECRETARY"
    MEMBER = "MEMBER"
    ALTERNATE = "ALTERNATE"

class MeetingStatusEnum(str, Enum):
    SCHEDULED = "scheduled"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    POSTPONED = "postponed"

class AttendanceStatusEnum(str, Enum):
    PRESENT = "PRESENT"
    ABSENT = "ABSENT"
    EXCUSED = "EXCUSED"
    LATE = "LATE"
    CANCELLED = "CANCELLED"

class VotingStatusEnum(str, Enum):
    DRAFT = "DRAFT"
    ACTIVE = "ACTIVE"
    CLOSED = "CLOSED"
    CANCELLED = "CANCELLED"

class VoteChoiceEnum(str, Enum):
    YES = "yes"
    NO = "no"
    ABSTAIN = "abstain"

class ActivityStatusEnum(str, Enum):
    PENDING = "PENDING"
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"
    OVERDUE = "OVERDUE"

class ActivityPriorityEnum(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"

class DocumentTypeEnum(str, Enum):
    MEETING_MINUTES = "meeting_minutes"
    VOTING_RECORD = "voting_record"
    REGULATION = "regulation"
    REPORT = "report"
    INVESTIGATION = "investigation"
    PROCEDURE = "procedure"
    FORM = "form"
    CERTIFICATE = "certificate"
    ACTIVITY_REPORT = "activity_report"
    AGREEMENT = "agreement"
    PRESENTATION = "presentation"
    OTHER = "other"

# Base schemas
class CommitteeTypeBase(BaseModel):
    name: str = Field(..., max_length=100, description="Nombre del tipo de comité")
    description: Optional[str] = Field(None, description="Descripción del tipo de comité")
    is_active: bool = Field(True, description="Si el tipo de comité está activo")

class CommitteeTypeCreate(CommitteeTypeBase):
    pass

class CommitteeTypeUpdate(BaseModel):
    name: Optional[str] = Field(None, max_length=100)
    description: Optional[str] = None
    is_active: Optional[bool] = None

class CommitteeType(CommitteeTypeBase):
    id: int
    created_at: datetime
    updated_at: datetime
    
    model_config = ConfigDict(from_attributes=True)

# Committee schemas
class CommitteeBase(BaseModel):
    name: str = Field(..., max_length=200, description="Nombre del comité")
    description: Optional[str] = Field(None, description="Descripción del comité")
    committee_type: CommitteeTypeEnum = Field(..., description="Tipo de comité")
    committee_type_id: int = Field(..., description="ID del tipo de comité")
    is_active: bool = Field(True, description="Si el comité está activo")
    establishment_date: Optional[date] = Field(None, description="Fecha de establecimiento")
    dissolution_date: Optional[date] = Field(None, description="Fecha de disolución")
    meeting_frequency_days: int = Field(30, ge=1, description="Frecuencia de reuniones en días")
    quorum_percentage: float = Field(50.0, ge=0, le=100, description="Porcentaje de quórum requerido")
    regulations_document_url: Optional[str] = Field(None, max_length=500)
    notes: Optional[str] = Field(None, description="Notas adicionales")

    @validator('dissolution_date')
    def validate_dissolution_date(cls, v, values):
        if v and 'establishment_date' in values and values['establishment_date']:
            if v < values['establishment_date']:
                raise ValueError('La fecha de disolución debe ser posterior a la fecha de establecimiento')
        return v

class CommitteeCreate(CommitteeBase):
    pass

class CommitteeUpdate(BaseModel):
    name: Optional[str] = Field(None, max_length=200)
    description: Optional[str] = None
    committee_type: Optional[CommitteeTypeEnum] = None
    committee_type_id: Optional[int] = None
    is_active: Optional[bool] = None
    establishment_date: Optional[date] = None
    dissolution_date: Optional[date] = None
    meeting_frequency_days: Optional[int] = Field(None, ge=1)
    quorum_percentage: Optional[float] = Field(None, ge=0, le=100)
    regulations_document_url: Optional[str] = Field(None, max_length=500)
    notes: Optional[str] = None

class Committee(CommitteeBase):
    id: int
    created_at: datetime
    updated_at: datetime
    created_by: Optional[int]
    members: Optional[List[Any]] = Field(None, exclude=True)

    @computed_field
    @property
    def members_count(self) -> int:
        if self.members is None:
            return 0
        return sum(1 for m in self.members if getattr(m, 'is_active', True))

    model_config = ConfigDict(from_attributes=True)

# Committee Role schemas
class CommitteeRoleBase(BaseModel):
    name: str = Field(..., max_length=100, description="Nombre del rol")
    description: Optional[str] = Field(None, description="Descripción del rol")
    is_active: bool = Field(True, description="Si el rol está activo")

class CommitteeRoleCreate(CommitteeRoleBase):
    pass

class CommitteeRoleUpdate(BaseModel):
    name: Optional[str] = Field(None, max_length=100)
    description: Optional[str] = None
    is_active: Optional[bool] = None

class CommitteeRole(CommitteeRoleBase):
    id: int
    created_at: datetime
    updated_at: datetime
    
    model_config = ConfigDict(from_attributes=True)

# Committee Member schemas
class CommitteeMemberBase(BaseModel):
    committee_id: int = Field(..., description="ID del comité")
    user_id: int = Field(..., description="ID del usuario")
    role: CommitteeRoleEnum = Field(..., description="Rol en el comité")
    role_id: Optional[int] = Field(None, description="ID del rol (se resuelve automáticamente si no se envía)")
    is_active: bool = Field(True, description="Si la membresía está activa")
    start_date: date = Field(..., description="Fecha de inicio")
    end_date: Optional[date] = Field(None, description="Fecha de fin")
    appointment_document_url: Optional[str] = Field(None, max_length=500)
    notes: Optional[str] = Field(None, description="Notas adicionales")

    @validator('end_date')
    def validate_end_date(cls, v, values):
        if v and 'start_date' in values and values['start_date']:
            if v < values['start_date']:
                raise ValueError('La fecha de fin debe ser posterior a la fecha de inicio')
        return v

class CommitteeMemberCreate(CommitteeMemberBase):
    pass

class CommitteeMemberUpdate(BaseModel):
    role: Optional[CommitteeRoleEnum] = None
    role_id: Optional[int] = None
    is_active: Optional[bool] = None
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    appointment_document_url: Optional[str] = Field(None, max_length=500)
    notes: Optional[str] = None

# User schema for committee member context
class UserInCommittee(BaseModel):
    id: int
    first_name: str
    last_name: str
    email: str
    position: Optional[str] = None
    department: Optional[str] = None
    
    model_config = ConfigDict(from_attributes=True)

class CommitteeMember(CommitteeMemberBase):
    id: int
    created_at: datetime
    updated_at: datetime
    created_by: Optional[int]
    user: Optional[UserInCommittee] = None
    
    model_config = ConfigDict(from_attributes=True)

# Committee Meeting schemas
class CommitteeMeetingBase(BaseModel):
    committee_id: int = Field(..., description="ID del comité")
    title: str = Field(..., max_length=300, description="Título de la reunión")
    description: Optional[str] = Field(None, description="Descripción de la reunión")
    meeting_date: datetime = Field(..., description="Fecha y hora de la reunión")
    duration_minutes: Optional[int] = Field(None, ge=1, description="Duración en minutos")
    location: Optional[str] = Field(None, max_length=200, description="Ubicación")
    meeting_type: str = Field("regular", description="Tipo de reunión")
    status: str = Field("scheduled", description="Estado de la reunión")
    agenda: Optional[str] = Field(None, description="Agenda de la reunión")
    minutes_content: Optional[str] = Field(None, description="Contenido del acta")
    minutes_document_url: Optional[str] = Field(None, max_length=500)
    quorum_achieved: Optional[bool] = Field(None, description="Si se logró el quórum")
    attendees_count: int = Field(0, ge=0, description="Número de asistentes")
    notes: Optional[str] = Field(None, description="Notas adicionales")

class CommitteeMeetingCreate(CommitteeMeetingBase):
    pass

class CommitteeMeetingUpdate(BaseModel):
    title: Optional[str] = Field(None, max_length=300)
    description: Optional[str] = None
    meeting_date: Optional[datetime] = None
    duration_minutes: Optional[int] = Field(None, ge=1)
    location: Optional[str] = Field(None, max_length=200)
    meeting_type: Optional[str] = None
    status: Optional[str] = None
    agenda: Optional[str] = None
    minutes_content: Optional[str] = None
    minutes_document_url: Optional[str] = Field(None, max_length=500)
    quorum_achieved: Optional[bool] = None
    attendees_count: Optional[int] = Field(None, ge=0)
    notes: Optional[str] = None

class CommitteeMeeting(CommitteeMeetingBase):
    id: int
    created_at: datetime
    updated_at: datetime
    created_by: Optional[int]
    
    model_config = ConfigDict(from_attributes=True)

# Meeting Attendance schemas
class MeetingAttendanceBase(BaseModel):
    meeting_id: int = Field(..., description="ID de la reunión")
    member_id: int = Field(..., description="ID del miembro")
    status: AttendanceStatusEnum = Field(
        ...,
        validation_alias=AliasChoices("status", "attendance_status"),
        description="Estado de asistencia"
    )
    arrival_time: Optional[datetime] = Field(None, description="Hora de llegada")
    departure_time: Optional[datetime] = Field(None, description="Hora de salida")
    excuse_reason: Optional[str] = Field(None, description="Razón de excusa")
    notes: Optional[str] = Field(None, description="Notas adicionales")

    model_config = ConfigDict(populate_by_name=True)

    @validator('departure_time')
    def validate_departure_time(cls, v, values):
        if v and 'arrival_time' in values and values['arrival_time']:
            if v < values['arrival_time']:
                raise ValueError('La hora de salida debe ser posterior a la hora de llegada')
        return v

class MeetingAttendanceCreate(MeetingAttendanceBase):
    pass

class MeetingAttendanceUpdate(BaseModel):
    status: Optional[AttendanceStatusEnum] = None
    arrival_time: Optional[datetime] = None
    departure_time: Optional[datetime] = None
    excuse_reason: Optional[str] = None
    notes: Optional[str] = None

class MeetingAttendance(MeetingAttendanceBase):
    id: int
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

# Committee Voting schemas
class CommitteeVotingBase(BaseModel):
    committee_id: int = Field(..., description="ID del comité")
    meeting_id: Optional[int] = Field(None, description="ID de la reunión")
    title: str = Field(..., max_length=300, description="Título de la votación")
    description: Optional[str] = Field(None, description="Descripción de la votación")
    voting_type: str = Field("simple", description="Tipo de votación")
    status: VotingStatusEnum = Field(VotingStatusEnum.DRAFT, description="Estado de la votación")
    start_date: Optional[datetime] = Field(None, description="Fecha de inicio")
    end_date: Optional[datetime] = Field(None, description="Fecha de fin")
    requires_quorum: bool = Field(True, description="Si requiere quórum")
    minimum_votes_required: Optional[int] = Field(None, ge=1, description="Mínimo de votos requeridos")
    allow_abstention: bool = Field(True, description="Si permite abstención")
    is_secret: bool = Field(False, description="Si es votación secreta")
    results_summary: Optional[str] = Field(None, description="Resumen de resultados")
    notes: Optional[str] = Field(None, description="Notas adicionales")

    @validator('end_date')
    def validate_end_date(cls, v, values):
        if v and 'start_date' in values and values['start_date']:
            if v < values['start_date']:
                raise ValueError('La fecha de fin debe ser posterior a la fecha de inicio')
        return v

class CommitteeVotingCreate(CommitteeVotingBase):
    pass

class CommitteeVotingUpdate(BaseModel):
    title: Optional[str] = Field(None, max_length=300)
    description: Optional[str] = None
    voting_type: Optional[str] = None
    status: Optional[VotingStatusEnum] = None
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    requires_quorum: Optional[bool] = None
    minimum_votes_required: Optional[int] = Field(None, ge=1)
    allow_abstention: Optional[bool] = None
    is_secret: Optional[bool] = None
    results_summary: Optional[str] = None
    notes: Optional[str] = None

class CommitteeVoting(CommitteeVotingBase):
    id: int
    created_at: datetime
    updated_at: datetime
    created_by: Optional[int]
    
    model_config = ConfigDict(from_attributes=True)

# Committee Vote schemas
class CommitteeVoteBase(BaseModel):
    voting_id: int = Field(..., description="ID de la votación")
    member_id: int = Field(..., description="ID del miembro")
    vote_choice: VoteChoiceEnum = Field(..., description="Elección del voto")
    vote_date: datetime = Field(default_factory=datetime.now, description="Fecha del voto")
    comments: Optional[str] = Field(None, description="Comentarios del voto")
    is_proxy_vote: bool = Field(False, description="Si es voto por poder")
    proxy_member_id: Optional[int] = Field(None, description="ID del miembro que vota por poder")

class CommitteeVoteCreate(CommitteeVoteBase):
    pass

class CommitteeVoteUpdate(BaseModel):
    vote_choice: Optional[VoteChoiceEnum] = None
    comments: Optional[str] = None
    is_proxy_vote: Optional[bool] = None
    proxy_member_id: Optional[int] = None

class CommitteeVote(CommitteeVoteBase):
    id: int
    created_at: datetime
    updated_at: datetime
    
    model_config = ConfigDict(from_attributes=True)

# Committee Activity schemas
class CommitteeActivityBase(BaseModel):
    committee_id: int = Field(..., description="ID del comité")
    meeting_id: Optional[int] = Field(None, description="ID de la reunión")
    title: str = Field(..., max_length=300, description="Título de la actividad")
    description: Optional[str] = Field(None, description="Descripción de la actividad")
    activity_type: str = Field("task", description="Tipo de actividad")
    priority: ActivityPriorityEnum = Field(ActivityPriorityEnum.MEDIUM, description="Prioridad")
    status: ActivityStatusEnum = Field(ActivityStatusEnum.PENDING, description="Estado")
    assigned_to: Optional[int] = Field(None, description="ID del miembro asignado")
    due_date: Optional[date] = Field(None, description="Fecha límite")
    completion_date: Optional[date] = Field(None, description="Fecha de completado")
    progress_percentage: int = Field(0, ge=0, le=100, description="Porcentaje de progreso")
    supporting_document_url: Optional[str] = Field(None, max_length=500)
    notes: Optional[str] = Field(None, description="Notas adicionales")

    @validator('completion_date')
    def validate_completion_date(cls, v, values):
        if v and 'due_date' in values and values['due_date']:
            if v < values['due_date']:
                raise ValueError('La fecha de completado debe ser posterior a la fecha límite')
        return v

class CommitteeActivityCreate(CommitteeActivityBase):
    pass

class CommitteeActivityUpdate(BaseModel):
    title: Optional[str] = Field(None, max_length=300)
    description: Optional[str] = None
    activity_type: Optional[str] = None
    priority: Optional[ActivityPriorityEnum] = None
    status: Optional[ActivityStatusEnum] = None
    assigned_to: Optional[int] = None
    due_date: Optional[date] = None
    completion_date: Optional[date] = None
    progress_percentage: Optional[int] = Field(None, ge=0, le=100)
    supporting_document_url: Optional[str] = Field(None, max_length=500)
    notes: Optional[str] = None

class AssignedUserInfo(BaseModel):
    id: int
    first_name: str
    last_name: str
    email: str

    model_config = ConfigDict(from_attributes=True)

class CommitteeActivity(CommitteeActivityBase):
    id: int
    created_at: datetime
    updated_at: datetime
    created_by: Optional[int]
    assigned_user: Optional[AssignedUserInfo] = None

    model_config = ConfigDict(from_attributes=True)

# Committee Document schemas
class CommitteeDocumentBase(BaseModel):
    committee_id: int = Field(..., description="ID del comité")
    title: str = Field(..., max_length=300, description="Título del documento")
    description: Optional[str] = Field(None, description="Descripción del documento")
    document_type: DocumentTypeEnum = Field(..., description="Tipo de documento")
    file_name: str = Field(..., max_length=255, description="Nombre del archivo")
    file_path: str = Field(..., max_length=500, description="Ruta del archivo")
    file_size: Optional[int] = Field(None, ge=1, description="Tamaño del archivo")
    mime_type: Optional[str] = Field(None, max_length=100, description="Tipo MIME")
    version: str = Field("1.0", max_length=20, description="Versión del documento")
    is_public: bool = Field(False, description="Si es público")
    download_count: int = Field(0, ge=0, description="Número de descargas")
    tags: Optional[str] = Field(None, max_length=500, description="Etiquetas")
    expiry_date: Optional[date] = Field(None, description="Fecha de expiración")
    notes: Optional[str] = Field(None, description="Notas adicionales")

class CommitteeDocumentCreate(CommitteeDocumentBase):
    pass

class CommitteeDocumentUpdate(BaseModel):
    title: Optional[str] = Field(None, max_length=300)
    description: Optional[str] = None
    document_type: Optional[DocumentTypeEnum] = None
    version: Optional[str] = Field(None, max_length=20)
    is_public: Optional[bool] = None
    tags: Optional[str] = Field(None, max_length=500)
    expiry_date: Optional[date] = None
    notes: Optional[str] = None

class CommitteeDocument(CommitteeDocumentBase):
    id: int
    created_at: datetime
    updated_at: datetime
    uploaded_by: Optional[int]
    
    model_config = ConfigDict(from_attributes=True)

# Committee Permission schemas
class CommitteePermissionBase(BaseModel):
    committee_id: int = Field(..., description="ID del comité")
    user_id: int = Field(..., description="ID del usuario")
    permission_type: str = Field(..., max_length=50, description="Tipo de permiso")
    granted_by: Optional[int] = Field(None, description="ID de quien otorgó el permiso")
    granted_at: datetime = Field(default_factory=datetime.now, description="Fecha de otorgamiento")
    expires_at: Optional[datetime] = Field(None, description="Fecha de expiración")
    is_active: bool = Field(True, description="Si el permiso está activo")
    notes: Optional[str] = Field(None, description="Notas adicionales")

    @validator('expires_at')
    def validate_expires_at(cls, v, values):
        if v and 'granted_at' in values and values['granted_at']:
            if v <= values['granted_at']:
                raise ValueError('La fecha de expiración debe ser posterior a la fecha de otorgamiento')
        return v

class CommitteePermissionCreate(CommitteePermissionBase):
    pass

class CommitteePermissionUpdate(BaseModel):
    permission_type: Optional[str] = Field(None, max_length=50)
    expires_at: Optional[datetime] = None
    is_active: Optional[bool] = None
    notes: Optional[str] = None

class CommitteePermission(CommitteePermissionBase):
    id: int
    created_at: datetime
    updated_at: datetime
    
    model_config = ConfigDict(from_attributes=True)

# Response schemas with relationships
class CommitteeWithMembers(Committee):
    members: List[CommitteeMember] = []

class CommitteeWithMeetings(Committee):
    meetings: List[CommitteeMeeting] = []

class CommitteeWithActivities(Committee):
    activities: List[CommitteeActivity] = []

class CommitteeWithDocuments(Committee):
    documents: List[CommitteeDocument] = []

class CommitteeDetailed(Committee):
    members: List[CommitteeMember] = []
    meetings: List[CommitteeMeeting] = []
    activities: List[CommitteeActivity] = []
    documents: List[CommitteeDocument] = []
    votings: List[CommitteeVoting] = []

class MeetingWithAttendance(CommitteeMeeting):
    attendances: List[MeetingAttendance] = []

class VotingWithVotes(CommitteeVoting):
    votes: List[CommitteeVote] = []

# Pagination schemas
class PaginatedResponse(BaseModel):
    items: List[Any]
    total: int
    page: int
    size: int
    pages: int

class CommitteeListResponse(BaseModel):
    items: List[Committee]
    total: int
    page: int
    size: int
    pages: int

class MeetingListResponse(BaseModel):
    items: List[CommitteeMeeting]
    total: int
    page: int
    size: int
    pages: int

class ActivityListResponse(BaseModel):
    items: List[CommitteeActivity]
    total: int
    page: int
    size: int
    pages: int