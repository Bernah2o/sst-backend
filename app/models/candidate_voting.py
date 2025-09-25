"""
Modelos para el sistema de votaciones de candidatos
"""
from sqlalchemy import Column, Integer, String, Text, DateTime, Boolean, ForeignKey, Date, CheckConstraint, Index
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from enum import Enum as PyEnum

from app.database import Base


class CandidateVotingStatus(PyEnum):
    """Estados de las votaciones de candidatos"""
    DRAFT = "draft"
    ACTIVE = "active"
    CLOSED = "closed"
    CANCELLED = "cancelled"


class CandidateVoting(Base):
    """Votaciones para seleccionar candidatos de comités"""
    __tablename__ = "candidate_votings"
    
    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(300), nullable=False)
    description = Column(Text)
    committee_type = Column(String(100), nullable=False)  # Tipo de comité (COCOLA, COPASST, etc.)
    status = Column(String(50), default=CandidateVotingStatus.DRAFT.value, nullable=False)
    start_date = Column(DateTime, nullable=False)
    end_date = Column(DateTime, nullable=False)
    max_votes_per_user = Column(Integer, default=1, nullable=False)  # Máximo de votos por usuario
    is_secret = Column(Boolean, default=True, nullable=False)
    allow_multiple_candidates = Column(Boolean, default=False, nullable=False)  # Si se pueden votar múltiples candidatos
    winner_count = Column(Integer, default=1, nullable=False)  # Número de ganadores
    results_summary = Column(Text)
    notes = Column(Text)
    created_at = Column(DateTime, default=func.now(), nullable=False)
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now(), nullable=False)
    created_by = Column(Integer, ForeignKey("users.id"), nullable=False)
    
    # Constraints
    __table_args__ = (
        CheckConstraint('end_date > start_date', name='check_end_after_start_candidate_voting'),
        CheckConstraint('max_votes_per_user > 0', name='check_positive_max_votes'),
        CheckConstraint('winner_count > 0', name='check_positive_winner_count'),
        Index('idx_candidate_voting_status', 'status'),
        Index('idx_candidate_voting_dates', 'start_date', 'end_date'),
        Index('idx_candidate_voting_type', 'committee_type'),
    )
    
    # Relationships
    candidates = relationship("CandidateVotingCandidate", back_populates="voting", cascade="all, delete-orphan")
    votes = relationship("CandidateVote", back_populates="voting", cascade="all, delete-orphan")
    creator = relationship("User", foreign_keys=[created_by])


class CandidateVotingCandidate(Base):
    """Candidatos en una votación"""
    __tablename__ = "candidate_voting_candidates"
    
    id = Column(Integer, primary_key=True, index=True)
    voting_id = Column(Integer, ForeignKey("candidate_votings.id"), nullable=False)
    worker_id = Column(Integer, ForeignKey("workers.id"), nullable=False)
    description = Column(Text)  # Descripción del candidato o propuesta
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=func.now(), nullable=False)
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now(), nullable=False)
    
    # Constraints
    __table_args__ = (
        Index('idx_voting_candidate', 'voting_id', 'worker_id'),
    )
    
    # Relationships
    voting = relationship("CandidateVoting", back_populates="candidates")
    worker = relationship("Worker")
    votes = relationship("CandidateVote", back_populates="candidate", cascade="all, delete-orphan")
    
    @property
    def vote_count(self):
        """Cuenta total de votos para este candidato"""
        return len(self.votes)


class CandidateVote(Base):
    """Votos individuales para candidatos"""
    __tablename__ = "candidate_votes"
    
    id = Column(Integer, primary_key=True, index=True)
    voting_id = Column(Integer, ForeignKey("candidate_votings.id"), nullable=False)
    candidate_id = Column(Integer, ForeignKey("candidate_voting_candidates.id"), nullable=False)
    voter_id = Column(Integer, ForeignKey("users.id"), nullable=False)  # Usuario que vota
    vote_date = Column(DateTime, default=func.now(), nullable=False)
    comments = Column(Text)  # Comentarios opcionales del votante
    created_at = Column(DateTime, default=func.now(), nullable=False)
    
    # Constraints
    __table_args__ = (
        # Un usuario solo puede votar una vez por candidato en cada votación
        Index('idx_unique_vote_per_candidate', 'voting_id', 'candidate_id', 'voter_id', unique=True),
        Index('idx_voting_voter', 'voting_id', 'voter_id'),
    )
    
    # Relationships
    voting = relationship("CandidateVoting", back_populates="votes")
    candidate = relationship("CandidateVotingCandidate", back_populates="votes")
    voter = relationship("User")


class CandidateVotingResult(Base):
    """Resultados finales de las votaciones"""
    __tablename__ = "candidate_voting_results"
    
    id = Column(Integer, primary_key=True, index=True)
    voting_id = Column(Integer, ForeignKey("candidate_votings.id"), nullable=False)
    candidate_id = Column(Integer, ForeignKey("candidate_voting_candidates.id"), nullable=False)
    total_votes = Column(Integer, default=0, nullable=False)
    percentage = Column(String(10))  # Porcentaje de votos
    position = Column(Integer)  # Posición en el ranking (1 = ganador)
    is_winner = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime, default=func.now(), nullable=False)
    
    # Constraints
    __table_args__ = (
        Index('idx_voting_results', 'voting_id', 'position'),
    )
    
    # Relationships
    voting = relationship("CandidateVoting")
    candidate = relationship("CandidateVotingCandidate")