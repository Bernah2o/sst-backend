"""
API endpoints for Committee Votings Management
"""
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import and_, or_, desc, asc, func
from datetime import datetime, date

from app.database import get_db
from app.dependencies import get_current_user
from app.models.committee import (
    Committee, CommitteeVoting, CommitteeVote, CommitteeMember
)
from app.models.user import User
from app.schemas.committee import (
    CommitteeVoting as CommitteeVotingSchema,
    CommitteeVotingCreate,
    CommitteeVotingUpdate,
    CommitteeVote as CommitteeVoteSchema,
    CommitteeVoteCreate,
    CommitteeVoteUpdate,
    VotingStatusEnum,
    VoteChoiceEnum
)

router = APIRouter()

# Committee Voting endpoints
@router.get("/", response_model=List[CommitteeVotingSchema])
async def get_committee_votings(
    committee_id: Optional[int] = Query(None),
    status: Optional[VotingStatusEnum] = Query(None),
    date_from: Optional[date] = Query(None),
    date_to: Optional[date] = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Obtener votaciones de comités con filtros"""
    query = db.query(CommitteeVoting).options(
        joinedload(CommitteeVoting.committee)
    )
    
    # Filtros
    if committee_id:
        query = query.filter(CommitteeVoting.committee_id == committee_id)
    
    if status:
        query = query.filter(CommitteeVoting.status == status)
    
    if date_from:
        query = query.filter(CommitteeVoting.start_date >= date_from)
    
    if date_to:
        query = query.filter(CommitteeVoting.end_date <= date_to)
    
    # Ordenar por fecha de inicio descendente
    query = query.order_by(desc(CommitteeVoting.start_date))
    
    votings = query.offset(skip).limit(limit).all()
    
    return votings

@router.post("/", response_model=CommitteeVotingSchema, status_code=status.HTTP_201_CREATED)
async def create_committee_voting(
    voting: CommitteeVotingCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Crear una nueva votación de comité"""
    # Verificar que el comité existe
    committee = db.query(Committee).filter(Committee.id == voting.committee_id).first()
    if not committee:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Comité no encontrado"
        )
    
    # Verificar fechas
    if voting.start_date < date.today():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="La fecha de inicio no puede ser en el pasado"
        )
    
    if voting.end_date <= voting.start_date:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="La fecha de fin debe ser posterior a la fecha de inicio"
        )
    
    voting_data = voting.model_dump()
    voting_data["created_by"] = current_user.id
    
    db_voting = CommitteeVoting(**voting_data)
    db.add(db_voting)
    db.commit()
    db.refresh(db_voting)
    
    return db_voting

@router.get("/{voting_id}", response_model=CommitteeVotingSchema)
async def get_committee_voting(
    voting_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Obtener una votación de comité por ID"""
    voting = db.query(CommitteeVoting).options(
        joinedload(CommitteeVoting.committee)
    ).filter(CommitteeVoting.id == voting_id).first()
    
    if not voting:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Votación no encontrada"
        )
    
    return voting

@router.put("/{voting_id}", response_model=CommitteeVotingSchema)
async def update_committee_voting(
    voting_id: int,
    voting_update: CommitteeVotingUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Actualizar una votación de comité"""
    voting = db.query(CommitteeVoting).filter(CommitteeVoting.id == voting_id).first()
    
    if not voting:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Votación no encontrada"
        )
    
    # Verificar que no se pueda modificar una votación completada
    if voting.status == VotingStatusEnum.completed:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No se puede modificar una votación completada"
        )
    
    # Verificar fechas si se están actualizando
    if voting_update.start_date and voting_update.start_date < date.today():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="La fecha de inicio no puede ser en el pasado"
        )
    
    if voting_update.end_date and voting_update.start_date:
        if voting_update.end_date <= voting_update.start_date:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="La fecha de fin debe ser posterior a la fecha de inicio"
            )
    elif voting_update.end_date and voting_update.end_date <= voting.start_date:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="La fecha de fin debe ser posterior a la fecha de inicio"
        )
    
    update_data = voting_update.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(voting, field, value)
    
    db.commit()
    db.refresh(voting)
    
    return voting

@router.delete("/{voting_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_committee_voting(
    voting_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Eliminar una votación de comité"""
    voting = db.query(CommitteeVoting).filter(CommitteeVoting.id == voting_id).first()
    
    if not voting:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Votación no encontrada"
        )
    
    # Verificar que no se pueda eliminar una votación completada
    if voting.status == VotingStatusEnum.completed:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No se puede eliminar una votación completada"
        )
    
    # Eliminar votos asociados
    db.query(CommitteeVote).filter(
        CommitteeVote.voting_id == voting_id
    ).delete()
    
    db.delete(voting)
    db.commit()

@router.post("/{voting_id}/start", response_model=CommitteeVotingSchema)
async def start_voting(
    voting_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Iniciar una votación"""
    voting = db.query(CommitteeVoting).filter(CommitteeVoting.id == voting_id).first()
    
    if not voting:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Votación no encontrada"
        )
    
    if voting.status != VotingStatusEnum.draft:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Solo se pueden iniciar votaciones en borrador"
        )
    
    if voting.start_date > date.today():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No se puede iniciar una votación antes de su fecha programada"
        )
    
    voting.status = VotingStatusEnum.active
    
    db.commit()
    db.refresh(voting)
    
    return voting

@router.post("/{voting_id}/complete", response_model=CommitteeVotingSchema)
async def complete_voting(
    voting_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Completar una votación"""
    voting = db.query(CommitteeVoting).filter(CommitteeVoting.id == voting_id).first()
    
    if not voting:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Votación no encontrada"
        )
    
    if voting.status != VotingStatusEnum.active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Solo se pueden completar votaciones activas"
        )
    
    voting.status = VotingStatusEnum.completed
    
    db.commit()
    db.refresh(voting)
    
    return voting

@router.post("/{voting_id}/cancel", response_model=CommitteeVotingSchema)
async def cancel_voting(
    voting_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Cancelar una votación"""
    voting = db.query(CommitteeVoting).filter(CommitteeVoting.id == voting_id).first()
    
    if not voting:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Votación no encontrada"
        )
    
    if voting.status == VotingStatusEnum.completed:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No se puede cancelar una votación completada"
        )
    
    voting.status = VotingStatusEnum.cancelled
    
    db.commit()
    db.refresh(voting)
    
    return voting

# Committee Vote endpoints
@router.get("/{voting_id}/votes", response_model=List[CommitteeVoteSchema])
async def get_voting_votes(
    voting_id: int,
    choice: Optional[VoteChoiceEnum] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Obtener los votos de una votación"""
    # Verificar que la votación existe
    voting = db.query(CommitteeVoting).filter(CommitteeVoting.id == voting_id).first()
    if not voting:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Votación no encontrada"
        )
    
    query = db.query(CommitteeVote).filter(
        CommitteeVote.voting_id == voting_id
    )
    
    if choice:
        query = query.filter(CommitteeVote.choice == choice)
    
    votes = query.order_by(CommitteeVote.voted_at).all()
    
    return votes

@router.post("/{voting_id}/votes", response_model=CommitteeVoteSchema, status_code=status.HTTP_201_CREATED)
async def cast_vote(
    voting_id: int,
    vote: CommitteeVoteCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Emitir un voto en una votación"""
    # Verificar que la votación existe
    voting = db.query(CommitteeVoting).filter(CommitteeVoting.id == voting_id).first()
    if not voting:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Votación no encontrada"
        )
    
    # Verificar que la votación está activa
    if voting.status != VotingStatusEnum.active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Solo se puede votar en votaciones activas"
        )
    
    # Verificar que estamos dentro del período de votación
    today = date.today()
    if today < voting.start_date or today > voting.end_date:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="La votación no está en período activo"
        )
    
    # Verificar que el usuario es miembro del comité
    member = db.query(CommitteeMember).filter(
        and_(
            CommitteeMember.committee_id == voting.committee_id,
            CommitteeMember.user_id == vote.user_id,
            CommitteeMember.is_active == True
        )
    ).first()
    
    if not member:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El usuario no es miembro activo del comité"
        )
    
    # Verificar que el usuario no ha votado ya
    existing_vote = db.query(CommitteeVote).filter(
        and_(
            CommitteeVote.voting_id == voting_id,
            CommitteeVote.user_id == vote.user_id
        )
    ).first()
    
    if existing_vote:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El usuario ya ha emitido su voto en esta votación"
        )
    
    vote_data = vote.model_dump()
    vote_data["voting_id"] = voting_id
    vote_data["voted_at"] = datetime.now()
    
    db_vote = CommitteeVote(**vote_data)
    db.add(db_vote)
    db.commit()
    db.refresh(db_vote)
    
    return db_vote

@router.put("/{voting_id}/votes/{user_id}", response_model=CommitteeVoteSchema)
async def update_vote(
    voting_id: int,
    user_id: int,
    vote_update: CommitteeVoteUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Actualizar un voto (solo si la votación permite cambios)"""
    # Verificar que la votación existe
    voting = db.query(CommitteeVoting).filter(CommitteeVoting.id == voting_id).first()
    if not voting:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Votación no encontrada"
        )
    
    # Verificar que la votación permite cambios
    if not voting.allow_change_vote:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Esta votación no permite cambiar el voto"
        )
    
    # Verificar que la votación está activa
    if voting.status != VotingStatusEnum.active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Solo se puede cambiar el voto en votaciones activas"
        )
    
    vote = db.query(CommitteeVote).filter(
        and_(
            CommitteeVote.voting_id == voting_id,
            CommitteeVote.user_id == user_id
        )
    ).first()
    
    if not vote:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Voto no encontrado"
        )
    
    update_data = vote_update.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(vote, field, value)
    
    vote.voted_at = datetime.now()  # Actualizar timestamp
    
    db.commit()
    db.refresh(vote)
    
    return vote

@router.get("/committee/{committee_id}", response_model=List[CommitteeVotingSchema])
async def get_votings_by_committee(
    committee_id: int,
    status: Optional[VotingStatusEnum] = Query(None),
    active_only: bool = Query(False),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Obtener todas las votaciones de un comité específico"""
    # Verificar que el comité existe
    committee = db.query(Committee).filter(Committee.id == committee_id).first()
    if not committee:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Comité no encontrado"
        )
    
    query = db.query(CommitteeVoting).filter(
        CommitteeVoting.committee_id == committee_id
    )
    
    if status:
        query = query.filter(CommitteeVoting.status == status)
    
    if active_only:
        today = date.today()
        query = query.filter(
            and_(
                CommitteeVoting.status == VotingStatusEnum.active,
                CommitteeVoting.start_date <= today,
                CommitteeVoting.end_date >= today
            )
        )
    
    query = query.order_by(desc(CommitteeVoting.start_date))
    
    votings = query.offset(skip).limit(limit).all()
    
    return votings

@router.get("/{voting_id}/results")
async def get_voting_results(
    voting_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Obtener los resultados de una votación"""
    # Verificar que la votación existe
    voting = db.query(CommitteeVoting).filter(CommitteeVoting.id == voting_id).first()
    if not voting:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Votación no encontrada"
        )
    
    # Contar votos por opción
    vote_counts = db.query(
        CommitteeVote.choice,
        func.count(CommitteeVote.id).label('count')
    ).filter(
        CommitteeVote.voting_id == voting_id
    ).group_by(CommitteeVote.choice).all()
    
    # Total de miembros elegibles para votar
    total_eligible = db.query(CommitteeMember).filter(
        and_(
            CommitteeMember.committee_id == voting.committee_id,
            CommitteeMember.is_active == True
        )
    ).count()
    
    # Total de votos emitidos
    total_votes = db.query(CommitteeVote).filter(
        CommitteeVote.voting_id == voting_id
    ).count()
    
    results = {
        "voting_id": voting_id,
        "title": voting.title,
        "status": voting.status.value,
        "total_eligible_voters": total_eligible,
        "total_votes_cast": total_votes,
        "participation_rate": round((total_votes / total_eligible * 100), 2) if total_eligible > 0 else 0,
        "votes_by_choice": {vote.choice.value: vote.count for vote in vote_counts},
        "is_quorum_met": total_votes >= voting.quorum_required if voting.quorum_required else True
    }
    
    # Determinar resultado si la votación está completada
    if voting.status == VotingStatusEnum.completed:
        vote_counts_dict = results["votes_by_choice"]
        max_votes = max(vote_counts_dict.values()) if vote_counts_dict else 0
        winning_choices = [choice for choice, count in vote_counts_dict.items() if count == max_votes]
        
        results["result"] = {
            "winning_choice": winning_choices[0] if len(winning_choices) == 1 else None,
            "is_tie": len(winning_choices) > 1,
            "winning_choices": winning_choices if len(winning_choices) > 1 else None
        }
    
    return results

@router.get("/user/{user_id}/votes", response_model=List[CommitteeVoteSchema])
async def get_user_votes(
    user_id: int,
    committee_id: Optional[int] = Query(None),
    voting_id: Optional[int] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Obtener todos los votos de un usuario específico"""
    query = db.query(CommitteeVote).filter(CommitteeVote.user_id == user_id)
    
    if voting_id:
        query = query.filter(CommitteeVote.voting_id == voting_id)
    elif committee_id:
        # Filtrar por comité a través de la votación
        query = query.join(CommitteeVoting).filter(
            CommitteeVoting.committee_id == committee_id
        )
    
    votes = query.order_by(desc(CommitteeVote.voted_at)).all()
    
    return votes