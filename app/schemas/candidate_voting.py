"""
Esquemas Pydantic para votaciones de candidatos
"""
from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, Field, validator


class CandidateVotingCandidateBase(BaseModel):
    worker_id: int
    description: Optional[str] = None
    is_active: bool = True


class CandidateVotingCandidateCreate(CandidateVotingCandidateBase):
    pass


class CandidateVotingCandidateUpdate(BaseModel):
    description: Optional[str] = None
    is_active: Optional[bool] = None


class WorkerInfo(BaseModel):
    id: int
    first_name: str
    last_name: str
    full_name: str
    document_number: str
    position: str
    department: Optional[str] = None
    email: str
    is_active: bool

    class Config:
        from_attributes = True


class CandidateVotingCandidate(CandidateVotingCandidateBase):
    id: int
    voting_id: int
    worker: WorkerInfo
    vote_count: int = 0
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class CandidateVoteBase(BaseModel):
    candidate_id: int
    comments: Optional[str] = None


class CandidateVoteCreate(CandidateVoteBase):
    pass


class CandidateVote(CandidateVoteBase):
    id: int
    voting_id: int
    voter_id: int
    vote_date: datetime
    created_at: datetime

    class Config:
        from_attributes = True


class CandidateVotingResultBase(BaseModel):
    candidate_id: int
    total_votes: int
    percentage: Optional[str] = None
    position: Optional[int] = None
    is_winner: bool = False


class CandidateVotingResult(CandidateVotingResultBase):
    id: int
    voting_id: int
    candidate: CandidateVotingCandidate
    created_at: datetime

    class Config:
        from_attributes = True


class CandidateVotingBase(BaseModel):
    title: str = Field(..., min_length=1, max_length=300)
    description: Optional[str] = None
    committee_type: str = Field(..., min_length=1, max_length=100)
    start_date: datetime
    end_date: datetime
    max_votes_per_user: int = Field(default=1, ge=1)
    is_secret: bool = True
    allow_multiple_candidates: bool = False
    winner_count: int = Field(default=1, ge=1)
    notes: Optional[str] = None

    @validator('end_date')
    def end_date_must_be_after_start_date(cls, v, values):
        if 'start_date' in values and v <= values['start_date']:
            raise ValueError('La fecha de fin debe ser posterior a la fecha de inicio')
        return v


class CandidateVotingCreate(CandidateVotingBase):
    candidate_worker_ids: List[int] = Field(..., min_items=1)


class CandidateVotingUpdate(BaseModel):
    title: Optional[str] = Field(None, min_length=1, max_length=300)
    description: Optional[str] = None
    committee_type: Optional[str] = Field(None, min_length=1, max_length=100)
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    max_votes_per_user: Optional[int] = Field(None, ge=1)
    is_secret: Optional[bool] = None
    allow_multiple_candidates: Optional[bool] = None
    winner_count: Optional[int] = Field(None, ge=1)
    notes: Optional[str] = None
    status: Optional[str] = None

    @validator('end_date')
    def end_date_must_be_after_start_date(cls, v, values):
        if v is not None and 'start_date' in values and values['start_date'] is not None and v <= values['start_date']:
            raise ValueError('La fecha de fin debe ser posterior a la fecha de inicio')
        return v


class CandidateVoting(CandidateVotingBase):
    id: int
    status: str
    results_summary: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    created_by: int
    candidates: List[CandidateVotingCandidate] = []
    total_votes: int = 0
    total_voters: int = 0

    class Config:
        from_attributes = True


class CandidateVotingDetail(CandidateVoting):
    votes: List[CandidateVote] = []
    results: List[CandidateVotingResult] = []


class CandidateVotingList(BaseModel):
    id: int
    title: str
    committee_type: str
    status: str
    start_date: datetime
    end_date: datetime
    candidate_count: int = 0
    total_votes: int = 0
    created_at: datetime

    class Config:
        from_attributes = True


class VotingStats(BaseModel):
    total_votings: int
    active_votings: int
    completed_votings: int
    total_votes_cast: int
    total_candidates: int


class CandidateVotingPublic(BaseModel):
    """Información pública de votación para empleados"""
    id: int
    title: str
    description: Optional[str] = None
    committee_type: str
    start_date: datetime
    end_date: datetime
    max_votes_per_user: int
    allow_multiple_candidates: bool
    candidates: List[CandidateVotingCandidate] = []
    user_has_voted: bool = False
    user_votes: List[int] = []  # IDs de candidatos por los que ya votó

    class Config:
        from_attributes = True