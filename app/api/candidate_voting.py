"""
Endpoints para votaciones de candidatos
"""
from datetime import datetime
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import and_, func, desc

from app.database import get_db
from app.dependencies import get_current_user
from app.models import (
    User, Worker, CandidateVoting, CandidateVotingCandidate, 
    CandidateVote, CandidateVotingStatus
)
from app.models.candidate_voting import CandidateVotingResult as CandidateVotingResultModel
from app.schemas.candidate_voting import (
    CandidateVoting as CandidateVotingSchema,
    CandidateVotingCreate,
    CandidateVotingUpdate,
    CandidateVotingList,
    CandidateVotingDetail,
    CandidateVotingPublic,
    CandidateVoteCreate,
    CandidateVote as CandidateVoteSchema,
    CandidateVotingResult,
    VotingStats
)

router = APIRouter()


def check_admin_permissions(current_user: User):
    """Verifica que el usuario tenga permisos de administrador"""
    if current_user.role not in ["admin", "super_admin"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No tienes permisos para realizar esta acción"
        )


@router.get("/stats", response_model=VotingStats)
def get_voting_stats(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Obtiene estadísticas generales de votaciones"""
    check_admin_permissions(current_user)
    
    total_votings = db.query(CandidateVoting).count()
    active_votings = db.query(CandidateVoting).filter(
        CandidateVoting.status == CandidateVotingStatus.ACTIVE.value
    ).count()
    completed_votings = db.query(CandidateVoting).filter(
        CandidateVoting.status == CandidateVotingStatus.CLOSED.value
    ).count()
    total_votes_cast = db.query(CandidateVote).count()
    total_candidates = db.query(CandidateVotingCandidate).count()
    
    return VotingStats(
        total_votings=total_votings,
        active_votings=active_votings,
        completed_votings=completed_votings,
        total_votes_cast=total_votes_cast,
        total_candidates=total_candidates
    )


@router.get("/", response_model=List[CandidateVotingList])
def get_votings(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    status: Optional[str] = Query(None),
    committee_type: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Obtiene lista de votaciones (solo administradores)"""
    check_admin_permissions(current_user)
    
    query = db.query(CandidateVoting)
    
    if status:
        query = query.filter(CandidateVoting.status == status)
    if committee_type:
        query = query.filter(CandidateVoting.committee_type == committee_type)
    
    votings = query.order_by(desc(CandidateVoting.created_at)).offset(skip).limit(limit).all()
    
    # Agregar conteos
    result = []
    for voting in votings:
        candidate_count = db.query(CandidateVotingCandidate).filter(
            CandidateVotingCandidate.voting_id == voting.id
        ).count()
        total_votes = db.query(CandidateVote).filter(
            CandidateVote.voting_id == voting.id
        ).count()
        
        voting_data = CandidateVotingList.from_orm(voting)
        voting_data.candidate_count = candidate_count
        voting_data.total_votes = total_votes
        result.append(voting_data)
    
    return result


@router.get("/active", response_model=List[CandidateVotingPublic])
def get_active_votings_for_employees(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Obtiene votaciones activas para empleados"""
    now = datetime.utcnow()
    
    votings = db.query(CandidateVoting).options(
        joinedload(CandidateVoting.candidates).joinedload(CandidateVotingCandidate.worker)
    ).filter(
        and_(
            CandidateVoting.status == CandidateVotingStatus.ACTIVE.value,
            CandidateVoting.start_date <= now,
            CandidateVoting.end_date >= now
        )
    ).all()
    
    result = []
    for voting in votings:
        # Verificar si el usuario ya votó
        user_votes = db.query(CandidateVote).filter(
            and_(
                CandidateVote.voting_id == voting.id,
                CandidateVote.voter_id == current_user.id
            )
        ).all()
        
        user_has_voted = len(user_votes) > 0
        user_vote_candidate_ids = [vote.candidate_id for vote in user_votes]
        
        voting_data = CandidateVotingPublic.from_orm(voting)
        voting_data.user_has_voted = user_has_voted
        voting_data.user_votes = user_vote_candidate_ids
        result.append(voting_data)
    
    return result


@router.get("/{voting_id}", response_model=CandidateVotingDetail)
def get_voting(
    voting_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Obtiene detalles de una votación específica"""
    check_admin_permissions(current_user)
    
    voting = db.query(CandidateVoting).options(
        joinedload(CandidateVoting.candidates).joinedload(CandidateVotingCandidate.worker),
        joinedload(CandidateVoting.votes)
    ).filter(CandidateVoting.id == voting_id).first()
    
    if not voting:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Votación no encontrada"
        )
    
    # Agregar conteos
    total_votes = len(voting.votes)
    total_voters = db.query(CandidateVote.voter_id).filter(
        CandidateVote.voting_id == voting_id
    ).distinct().count()
    
    voting_data = CandidateVotingDetail.from_orm(voting)
    voting_data.total_votes = total_votes
    voting_data.total_voters = total_voters
    
    return voting_data


@router.post("/", response_model=CandidateVotingSchema)
def create_voting(
    voting_data: CandidateVotingCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Crea una nueva votación de candidatos"""
    check_admin_permissions(current_user)
    
    # Verificar que los trabajadores existan y estén activos
    workers = db.query(Worker).filter(
        and_(
            Worker.id.in_(voting_data.candidate_worker_ids),
            Worker.is_active == True
        )
    ).all()
    
    if len(workers) != len(voting_data.candidate_worker_ids):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Algunos trabajadores no existen o no están activos"
        )
    
    # Crear la votación
    voting = CandidateVoting(
        title=voting_data.title,
        description=voting_data.description,
        committee_type=voting_data.committee_type,
        start_date=voting_data.start_date,
        end_date=voting_data.end_date,
        max_votes_per_user=voting_data.max_votes_per_user,
        is_secret=voting_data.is_secret,
        allow_multiple_candidates=voting_data.allow_multiple_candidates,
        winner_count=voting_data.winner_count,
        notes=voting_data.notes,
        created_by=current_user.id
    )
    
    db.add(voting)
    db.flush()  # Para obtener el ID
    
    # Crear los candidatos
    for worker_id in voting_data.candidate_worker_ids:
        candidate = CandidateVotingCandidate(
            voting_id=voting.id,
            worker_id=worker_id
        )
        db.add(candidate)
    
    db.commit()
    db.refresh(voting)
    
    return voting


@router.put("/{voting_id}", response_model=CandidateVotingSchema)
def update_voting(
    voting_id: int,
    voting_data: CandidateVotingUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Actualiza una votación existente"""
    check_admin_permissions(current_user)
    
    voting = db.query(CandidateVoting).filter(CandidateVoting.id == voting_id).first()
    if not voting:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Votación no encontrada"
        )
    
    # No permitir modificar votaciones activas o cerradas
    if voting.status in [CandidateVotingStatus.ACTIVE.value, CandidateVotingStatus.CLOSED.value]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No se puede modificar una votación activa o cerrada"
        )
    
    # Actualizar campos
    for field, value in voting_data.dict(exclude_unset=True).items():
        setattr(voting, field, value)
    
    db.commit()
    db.refresh(voting)
    
    return voting


@router.post("/{voting_id}/activate")
def activate_voting(
    voting_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Activa una votación"""
    check_admin_permissions(current_user)
    
    voting = db.query(CandidateVoting).filter(CandidateVoting.id == voting_id).first()
    if not voting:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Votación no encontrada"
        )
    
    if voting.status != CandidateVotingStatus.DRAFT.value:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Solo se pueden activar votaciones en borrador"
        )
    
    # Verificar que tenga candidatos
    candidate_count = db.query(CandidateVotingCandidate).filter(
        CandidateVotingCandidate.voting_id == voting_id
    ).count()
    
    if candidate_count == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="La votación debe tener al menos un candidato"
        )
    
    voting.status = CandidateVotingStatus.ACTIVE.value
    db.commit()
    
    return {"message": "Votación activada exitosamente"}


@router.post("/{voting_id}/close")
def close_voting(
    voting_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Cierra una votación y calcula resultados"""
    check_admin_permissions(current_user)
    
    voting = db.query(CandidateVoting).filter(CandidateVoting.id == voting_id).first()
    if not voting:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Votación no encontrada"
        )
    
    if voting.status != CandidateVotingStatus.ACTIVE.value:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Solo se pueden cerrar votaciones activas"
        )
    
    # Calcular resultados
    candidates = db.query(CandidateVotingCandidate).filter(
        CandidateVotingCandidate.voting_id == voting_id
    ).all()
    
    total_votes = db.query(CandidateVote).filter(
        CandidateVote.voting_id == voting_id
    ).count()
    
    results = []
    for candidate in candidates:
        candidate_votes = db.query(CandidateVote).filter(
            and_(
                CandidateVote.voting_id == voting_id,
                CandidateVote.candidate_id == candidate.id
            )
        ).count()
        
        percentage = (candidate_votes / total_votes * 100) if total_votes > 0 else 0
        
        results.append({
            'candidate_id': candidate.id,
            'votes': candidate_votes,
            'percentage': f"{percentage:.2f}%"
        })
    
    # Ordenar por votos descendente
    results.sort(key=lambda x: x['votes'], reverse=True)
    
    # Crear registros de resultados
    for i, result in enumerate(results):
        is_winner = i < voting.winner_count
        
        voting_result = CandidateVotingResultModel(
            voting_id=voting_id,
            candidate_id=result['candidate_id'],
            total_votes=result['votes'],
            percentage=result['percentage'],
            position=i + 1,
            is_winner=is_winner
        )
        db.add(voting_result)
    
    # Actualizar estado y resumen
    voting.status = CandidateVotingStatus.CLOSED.value
    voting.results_summary = f"Votación cerrada con {total_votes} votos totales"
    
    db.commit()
    
    return {"message": "Votación cerrada y resultados calculados"}


@router.post("/{voting_id}/vote", response_model=CandidateVoteSchema)
def cast_vote(
    voting_id: int,
    vote_data: CandidateVoteCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Permite a un empleado votar por un candidato"""
    
    # Verificar que la votación existe y está activa
    voting = db.query(CandidateVoting).filter(CandidateVoting.id == voting_id).first()
    if not voting:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Votación no encontrada"
        )
    
    now = datetime.utcnow()
    if voting.status != CandidateVotingStatus.ACTIVE.value:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="La votación no está activa"
        )
    
    if now < voting.start_date or now > voting.end_date:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="La votación no está en el período de votación"
        )
    
    # Verificar que el candidato existe
    candidate = db.query(CandidateVotingCandidate).filter(
        and_(
            CandidateVotingCandidate.id == vote_data.candidate_id,
            CandidateVotingCandidate.voting_id == voting_id,
            CandidateVotingCandidate.is_active == True
        )
    ).first()
    
    if not candidate:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Candidato no encontrado o inactivo"
        )
    
    # Verificar límites de votos
    existing_votes = db.query(CandidateVote).filter(
        and_(
            CandidateVote.voting_id == voting_id,
            CandidateVote.voter_id == current_user.id
        )
    ).count()
    
    if existing_votes >= voting.max_votes_per_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Ya has alcanzado el límite de {voting.max_votes_per_user} votos"
        )
    
    # Verificar si ya votó por este candidato
    existing_vote = db.query(CandidateVote).filter(
        and_(
            CandidateVote.voting_id == voting_id,
            CandidateVote.candidate_id == vote_data.candidate_id,
            CandidateVote.voter_id == current_user.id
        )
    ).first()
    
    if existing_vote:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Ya has votado por este candidato"
        )
    
    # Crear el voto
    vote = CandidateVote(
        voting_id=voting_id,
        candidate_id=vote_data.candidate_id,
        voter_id=current_user.id,
        comments=vote_data.comments
    )
    
    db.add(vote)
    db.commit()
    db.refresh(vote)
    
    return vote


@router.delete("/{voting_id}")
def delete_voting(
    voting_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Elimina una votación (administradores pueden eliminar borradores y cerradas)"""
    check_admin_permissions(current_user)
    
    voting = db.query(CandidateVoting).filter(CandidateVoting.id == voting_id).first()
    if not voting:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Votación no encontrada"
        )
    
    # Los administradores pueden eliminar votaciones en borrador y cerradas, pero no activas
    if voting.status == CandidateVotingStatus.ACTIVE.value:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No se puede eliminar una votación activa. Debe cerrarla primero."
        )
    
    try:
        # Eliminar dependencias en el orden correcto para evitar errores de integridad
        
        # 1. Eliminar resultados de votación (si existen)
        db.query(CandidateVotingResultModel).filter(
            CandidateVotingResultModel.voting_id == voting_id
        ).delete()
        
        # 2. Eliminar votos individuales
        db.query(CandidateVote).filter(
            CandidateVote.voting_id == voting_id
        ).delete()
        
        # 3. Eliminar candidatos
        db.query(CandidateVotingCandidate).filter(
            CandidateVotingCandidate.voting_id == voting_id
        ).delete()
        
        # 4. Finalmente eliminar la votación
        db.delete(voting)
        
        db.commit()
        
        return {"message": "Votación eliminada exitosamente"}
        
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error al eliminar la votación: {str(e)}"
        )


@router.get("/{voting_id}/results", response_model=List[CandidateVotingResult])
def get_voting_results(
    voting_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Obtiene los resultados de una votación cerrada"""
    
    voting = db.query(CandidateVoting).filter(CandidateVoting.id == voting_id).first()
    if not voting:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Votación no encontrada"
        )
    
    if voting.status != CandidateVotingStatus.CLOSED.value:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Los resultados solo están disponibles para votaciones cerradas"
        )
    
    results = db.query(CandidateVotingResultModel).options(
        joinedload(CandidateVotingResultModel.candidate).joinedload(CandidateVotingCandidate.worker)
    ).filter(
        CandidateVotingResultModel.voting_id == voting_id
    ).order_by(CandidateVotingResultModel.position).all()
    
    return results