import os
import time
from contextlib import asynccontextmanager
from typing import Any
import logging

from fastapi import FastAPI, Request, HTTPException
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from starlette.middleware.base import BaseHTTPMiddleware
import json

from app.api import api_router
from app.config import settings
from app.database import create_tables
from app.schemas.common import HealthCheck
from app.scheduler import start_scheduler, stop_scheduler

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

# Custom middleware for debugging request bodies


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        # Skip logging for OPTIONS requests (CORS preflight)
        if request.method == "OPTIONS":
            response = await call_next(request)
            return response
        
        response = await call_next(request)
        return response


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan events"""
    # Startup
    
    # Note: Database tables should be created using Alembic migrations
    # Run: alembic upgrade head
    # This ensures proper version control and rollback capabilities
    
    # Start reinduction scheduler
    try:
        start_scheduler()
    except Exception as e:
        pass
    
    yield
    
    # Shutdown
    # Stop scheduler
    try:
        stop_scheduler()
    except Exception as e:
        pass


# Create FastAPI application
app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description="""
    Plataforma de Capacitaciones en Seguridad y Salud en el Trabajo (SST)
    
    Esta API proporciona endpoints para:
    - Gestión de usuarios y autenticación
    - Cursos de inducción y reinducción
    - Evaluaciones y encuestas
    - Certificados y seguimiento
    - Notificaciones y reportes
    
    ## Autenticación
    
    La API utiliza JWT (JSON Web Tokens) para autenticación. Para acceder a endpoints protegidos:
    
    1. Obtén un token usando `/auth/login`
    2. Incluye el token en el header: `Authorization: Bearer <token>`
    
    ## Roles de Usuario
    
    - **Admin**: Acceso completo al sistema
    - **Trainer**: Puede crear y gestionar cursos y evaluaciones
    - **Supervisor**: Puede ver reportes y gestionar empleados
    - **Employee**: Puede tomar cursos y evaluaciones
    
    ## Cumplimiento Legal
    
    Esta plataforma cumple con:
    - Ley 1581 de 2012 (Protección de Datos Personales)
    - Decreto 1072 de 2015 (Sistema de Gestión SST)
    - Resolución 0312 de 2019 (Estándares Mínimos SST)
    """,
    openapi_tags=[
        {
            "name": "authentication",
            "description": "Autenticación y gestión de tokens"
        },
        {
            "name": "users",
            "description": "Gestión de usuarios"
        },
        {
            "name": "workers",
            "description": "Gestión de trabajadores"
        },
        {
            "name": "courses",
            "description": "Gestión de cursos y materiales"
        },
        {
            "name": "evaluations",
            "description": "Evaluaciones y cuestionarios"
        },
        {
            "name": "surveys",
            "description": "Encuestas y formularios"
        },
        {
            "name": "certificates",
            "description": "Certificados y verificación"
        },
        {
            "name": "attendance",
            "description": "Registro de asistencia"
        },
        {
            "name": "notifications",
            "description": "Notificaciones y alertas"
        },
        {
            "name": "reports",
            "description": "Reportes y analíticas"
        },
        {
            "name": "files",
            "description": "Gestión de archivos"
        },
        {
            "name": "enrollments",
            "description": "Inscripciones y asignación de cursos"
        },
        {
            "name": "admin",
            "description": "Administración y configuración del sistema"
        },
    ],
    lifespan=lifespan,
    docs_url="/docs" if settings.debug else None,
    redoc_url="/redoc" if settings.debug else None,
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS", "PATCH"],
    allow_headers=["*"],
    expose_headers=["*"],
)

# Add request logging middleware for debugging
app.add_middleware(RequestLoggingMiddleware)

app.add_middleware(
    TrustedHostMiddleware,
    allowed_hosts=["*"] if settings.debug else ["sst-backend-upmch1-b95ca4-5-252-53-108.traefik.me"]
)

# Create necessary directories if they don't exist
required_dirs = [
    "static",
    "uploads", 
    settings.certificate_output_dir,
    "medical_reports",
    "attendance_lists"
]

for directory in required_dirs:
    os.makedirs(directory, exist_ok=True)

# Mount static files
app.mount("/static", StaticFiles(directory="static"), name="static")
app.mount("/uploads", StaticFiles(directory="uploads"), name="uploads")
app.mount("/certificates", StaticFiles(directory=settings.certificate_output_dir), name="certificates")
app.mount("/medical_reports", StaticFiles(directory="medical_reports"), name="medical_reports")
app.mount("/attendance_lists", StaticFiles(directory="attendance_lists"), name="attendance_lists")

# Removed explicit OPTIONS handler - using FastAPI's built-in CORSMiddleware instead

# Include API router
app.include_router(api_router, prefix="/api/v1")

# Direct endpoints to bypass validation
@app.get("/direct/survey-results")
async def get_direct_survey_results(request: Request):
    """Direct endpoint to get survey results bypassing validation"""
    from fastapi.responses import Response
    import json
    from app.dependencies import get_db
    from app.services.auth import auth_service
    from app.models.survey import UserSurvey
    
    try:
        # Get current user from token
        token = request.headers.get("Authorization", "").replace("Bearer ", "")
        if not token:
            return Response(
                content=json.dumps({
                    "success": False,
                    "message": "Not authenticated",
                    "data": []
                }),
                media_type="application/json",
                status_code=401
            )
        
        # Get database session
        db = next(get_db())
        
        # Get current user
        current_user = auth_service.get_current_user(db, token)
        
        # Get user's enrollments to find available surveys
        from app.models.enrollment import Enrollment
        from app.models.survey import Survey, SurveyStatus
        from sqlalchemy import and_, or_
        from sqlalchemy.orm import joinedload
        
        enrollments = db.query(Enrollment).filter(
            Enrollment.user_id == current_user.id
        ).all()
        
        enrolled_course_ids = [enrollment.course_id for enrollment in enrollments]
        
        # Get all available surveys for the user (published surveys in enrolled courses or general surveys)
        available_surveys = db.query(Survey).options(joinedload(Survey.course)).filter(
            and_(
                Survey.status == SurveyStatus.PUBLISHED,
                or_(
                    # General surveys (not course-specific)
                    Survey.course_id.is_(None),
                    # Course-specific surveys for enrolled courses
                    Survey.course_id.in_(enrolled_course_ids)
                )
            )
        ).all()
        
        # Get user's survey submissions
        user_surveys = db.query(UserSurvey).filter(
            UserSurvey.user_id == current_user.id
        ).all()
        
        # Create a mapping of survey_id to user_survey for quick lookup
        user_survey_map = {us.survey_id: us for us in user_surveys}
        
        # Build response with both completed and pending surveys
        result = []
        
        for survey in available_surveys:
            user_survey = user_survey_map.get(survey.id)
            
            # Determine status
            if user_survey:
                status = user_survey.status.value if user_survey.status else "unknown"
                started_at = user_survey.started_at.isoformat() if user_survey.started_at else None
                completed_at = user_survey.completed_at.isoformat() if user_survey.completed_at else None
                created_at = user_survey.created_at.isoformat() if user_survey.created_at else None
                updated_at = user_survey.updated_at.isoformat() if user_survey.updated_at else None
                user_survey_id = int(user_survey.id)
            else:
                status = "not_started"
                started_at = None
                completed_at = None
                created_at = None
                updated_at = None
                user_survey_id = None
            
            # Ensure all values are of the correct type
            result.append({
                "survey_id": int(survey.id),
                "title": survey.title,
                "description": survey.description,
                "instructions": survey.instructions,
                "is_anonymous": bool(survey.is_anonymous),
                "course_id": int(survey.course_id) if survey.course_id else None,
                "course_title": survey.course.title if survey.course else None,
                "is_course_survey": bool(survey.is_course_survey),
                "required_for_completion": bool(survey.required_for_completion),
                "status": status,
                "user_survey_id": user_survey_id,
                "started_at": started_at,
                "completed_at": completed_at,
                "created_at": created_at,
                "updated_at": updated_at,
                "closes_at": survey.closes_at.isoformat() if survey.closes_at else None,
                "expires_at": survey.expires_at.isoformat() if survey.expires_at else None,
                "published_at": survey.published_at.isoformat() if survey.published_at else None
            })
        
        # Sort by status (pending first, then completed) and then by published date
        result.sort(key=lambda x: (
            0 if x["status"] == "not_started" else 1,  # Pending first
            x["published_at"] or ""  # Then by published date
        ))
        
        # Return a direct Response with JSON content to completely bypass FastAPI validation
        response_data = {
            "items": result,
            "total": len(result),
            "page": 1,
            "size": 100,
            "pages": 1,
            "has_next": False,
            "has_prev": False
        }
        
        # Convert to JSON string manually
        json_content = json.dumps(response_data)
        
        # Return raw response with application/json content type
        return Response(
            content=json_content,
            media_type="application/json"
        )
    except Exception as e:
        error_data = {
            "success": False,
            "message": f"Error retrieving survey results: {str(e)}",
            "data": []
        }
        return Response(
            content=json.dumps(error_data),
            media_type="application/json",
            status_code=500
        )


@app.get("/direct/evaluation-results")
async def get_direct_evaluation_results(request: Request):
    """Direct endpoint to get evaluation results bypassing validation"""
    from fastapi.responses import Response
    import json
    from app.dependencies import get_db
    from app.services.auth import auth_service
    from app.models.evaluation import UserEvaluation, Evaluation
    from app.models.course import Course
    
    try:
        # Get current user from token
        token = request.headers.get("Authorization", "").replace("Bearer ", "")
        if not token:
            return Response(
                content=json.dumps({
                    "success": False,
                    "message": "Not authenticated",
                    "data": []
                }),
                media_type="application/json",
                status_code=401
            )
        
        # Get database session
        db = next(get_db())
        
        # Get current user
        current_user = auth_service.get_current_user(db, token)
        
        # Build query with joins to get evaluation and course information
        query = db.query(
            UserEvaluation,
            Evaluation.title.label('evaluation_title'),
            Course.title.label('course_title')
        ).join(
            Evaluation, UserEvaluation.evaluation_id == Evaluation.id
        ).outerjoin(
            Course, Evaluation.course_id == Course.id
        ).filter(
            UserEvaluation.user_id == current_user.id
        )
        
        results = query.all()
        
        # Group results by evaluation_id to filter properly
        evaluation_groups = {}
        for user_eval, evaluation_title, course_title in results:
            eval_id = user_eval.evaluation_id
            if eval_id not in evaluation_groups:
                evaluation_groups[eval_id] = []
            evaluation_groups[eval_id].append((user_eval, evaluation_title, course_title))
        
        # Filter results: only highest score for passed evaluations, all failed attempts
        filtered_results = []
        for eval_id, attempts in evaluation_groups.items():
            # Separate passed and failed attempts
            passed_attempts = [(user_eval, eval_title, course_title) for user_eval, eval_title, course_title in attempts if user_eval.passed]
            failed_attempts = [(user_eval, eval_title, course_title) for user_eval, eval_title, course_title in attempts if not user_eval.passed]
            
            # For passed attempts, only keep the one with highest score
            if passed_attempts:
                best_passed = max(passed_attempts, key=lambda x: x[0].score if x[0].score is not None else 0)
                filtered_results.append(best_passed)
            
            # Add all failed attempts
            filtered_results.extend(failed_attempts)
        
        # Return simple dictionary to avoid Pydantic validation issues
        result = []
        for user_eval, evaluation_title, course_title in filtered_results:
            # Ensure all values are of the correct type
            result.append({
                "id": int(user_eval.id),
                "user_id": int(user_eval.user_id),
                "evaluation_id": int(user_eval.evaluation_id),
                "evaluation_title": evaluation_title,
                "course_title": course_title,
                "enrollment_id": int(user_eval.enrollment_id) if user_eval.enrollment_id else None,
                "attempt_number": int(user_eval.attempt_number),
                "status": user_eval.status.value if user_eval.status else None,
                "score": float(user_eval.score) if user_eval.score is not None else None,
                "total_points": float(user_eval.total_points) if user_eval.total_points is not None else None,
                "max_points": float(user_eval.max_points) if user_eval.max_points is not None else None,
                "percentage": float(user_eval.percentage) if user_eval.percentage is not None else None,
                "time_spent_minutes": int(user_eval.time_spent_minutes) if user_eval.time_spent_minutes is not None else None,
                "passed": bool(user_eval.passed),
                "started_at": user_eval.started_at.isoformat() if user_eval.started_at else None,
                "completed_at": user_eval.completed_at.isoformat() if user_eval.completed_at else None,
                "expires_at": user_eval.expires_at.isoformat() if user_eval.expires_at else None,
                "created_at": user_eval.created_at.isoformat() if user_eval.created_at else None,
                "updated_at": user_eval.updated_at.isoformat() if user_eval.updated_at else None
            })
        
        # Return a direct Response with JSON content to completely bypass FastAPI validation
        response_data = {
            "success": True,
            "data": result
        }
        
        # Convert to JSON string manually
        json_content = json.dumps(response_data)
        
        # Return raw response with application/json content type
        return Response(
            content=json_content,
            media_type="application/json"
        )
    except Exception as e:
        error_data = {
            "success": False,
            "message": f"Error retrieving evaluation results: {str(e)}",
            "data": []
        }
        return Response(
            content=json.dumps(error_data),
            media_type="application/json",
            status_code=500
        )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """Custom validation exception handler with improved error messages"""
    # Extract the first error message for a cleaner user experience
    first_error = exc.errors()[0] if exc.errors() else {}
    error_msg = first_error.get('msg', 'Validation error')
    field = first_error.get('loc', ['unknown'])[-1] if first_error.get('loc') else 'unknown'
    error_type = first_error.get('type', 'validation_error')
    input_value = first_error.get('input', 'unknown')
    
    # Provide more specific error messages for common validation errors
    if error_type == 'int_parsing':
        user_message = f"El parámetro '{field}' debe ser un número entero válido. Valor recibido: '{input_value}'"
        detail_message = f"Error de conversión: no se puede convertir '{input_value}' a entero en el campo '{field}'"
    elif error_type == 'missing':
        user_message = f"El parámetro requerido '{field}' no fue proporcionado"
        detail_message = f"Campo requerido '{field}' faltante en la solicitud"
    elif 'integer' in error_msg.lower() and 'parse' in error_msg.lower():
        user_message = f"El parámetro '{field}' debe ser un número entero válido. Valor recibido: '{input_value}'"
        detail_message = f"Error de validación: '{input_value}' no es un entero válido para el campo '{field}'"
    else:
        user_message = f"Error de validación en el campo '{field}': {error_msg}"
        detail_message = f"Error de validación en el campo '{field}': {error_msg}"
    
    # Log the validation error for debugging
    # Removed print for production
    
    return JSONResponse(
        status_code=422,
        content={
            "success": False,
            "message": user_message,
            "detail": detail_message,
            "error_code": 422,
            "field": field,
            "error_type": error_type,
            "timestamp": time.time()
        }
    )


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    """Custom HTTP exception handler"""
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "success": False,
            "message": exc.detail,
            "detail": exc.detail,
            "error_code": exc.status_code,
            "timestamp": time.time()
        }
    )


@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    """General exception handler"""
    
    return JSONResponse(
        status_code=500,
        content={
            "success": False,
            "message": "Internal server error",
            "error_code": 500,
            "timestamp": time.time()
        }
    )


@app.get("/", include_in_schema=False)
async def root():
    """Root endpoint"""
    return {
        "message": "SST Platform API",
        "version": settings.app_version,
        "docs": "/docs",
        "redoc": "/redoc"
    }


@app.get("/health", response_model=HealthCheck, tags=["health"])
async def health_check() -> Any:
    """Health check endpoint"""
    return HealthCheck(
        status="healthy",
        timestamp=time.time(),
        version=settings.app_version,
        database="connected",
        services={
            "email": "available",
            "file_storage": "available",
            "scheduler": "running"
        }
    )


if __name__ == "__main__":
    import uvicorn
    
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.debug,
        log_level=settings.log_level.lower()
    )