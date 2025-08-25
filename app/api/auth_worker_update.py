from sqlalchemy.orm import Session
from fastapi import HTTPException, status
from app.models.worker import Worker
from app.models.user import User

def update_worker_after_registration(db: Session, user: User) -> None:
    """
    Update worker record after user registration to set is_registered=True and user_id
    Validates both document number and email to ensure the user is an authorized employee
    """
    # Find worker by both document number and email for enhanced security
    worker = db.query(Worker).filter(
        Worker.document_number == user.document_number,
        Worker.email == user.email,
        Worker.is_active == True
    ).first()
    
    if not worker:
        # Enhanced error message to indicate both validations
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No se encontró un trabajador activo con ese número de documento y correo electrónico. Solo los empleados registrados por el administrador pueden crear una cuenta."
        )
    
    # Check if worker is already registered with a verified account
    if worker.is_registered and worker.user_id:
        # Check if the existing user is already verified
        existing_user = db.query(User).filter(User.id == worker.user_id).first()
        if existing_user and existing_user.is_verified:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Este empleado ya tiene una cuenta registrada en el sistema. Puede iniciar sesión directamente."
            )
    
    # Update worker to mark as registered and link to user
    worker.is_registered = True
    worker.user_id = user.id
    
    # No need to commit here as it will be committed in the calling function
    return worker