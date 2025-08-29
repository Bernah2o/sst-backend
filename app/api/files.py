import os
import uuid
import logging
from typing import Any, List
from PIL import Image
from io import BytesIO

from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File
from fastapi.responses import FileResponse, RedirectResponse, Response
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_active_user
from app.models.user import User
from app.models.course import Course, CourseModule, CourseMaterial, MaterialType
from app.schemas.common import MessageResponse
from app.config import settings
from app.utils.storage import storage_manager

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/upload")
async def upload_file(
    file: UploadFile = File(...),
    folder: str = "uploads",
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
) -> Any:
    """
    Upload a file to storage (Firebase or local)
    """
    try:
        # Validate file size (max 50MB)
        max_size = 50 * 1024 * 1024  # 50MB
        file_content = await file.read()
        if len(file_content) > max_size:
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail="File size must be less than 50MB"
            )
        
        # Reset file position
        await file.seek(0)
        
        # Upload file using storage manager
        result = await storage_manager.upload_file(file, folder)
        
        return {
            "message": "File uploaded successfully",
            "filename": result["filename"],
            "url": result["url"],
            "storage_type": result["storage_type"],
            "size": result["size"]
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error uploading file: {str(e)}"
        )


@router.get("/")
async def get_files(
    skip: int = 0,
    limit: int = 100,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
) -> Any:
    """
    Get user files
    """
    return {"message": "Get files endpoint - not implemented yet"}


@router.get("/{file_id}")
async def get_file(
    file_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
) -> Any:
    """
    Get file by ID
    """
    return {"message": f"Get file {file_id} endpoint - not implemented yet"}


@router.get("/{file_id}/download")
async def download_file(
    file_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
) -> Any:
    """
    Download file
    """
    return {"message": f"Download file {file_id} endpoint - not implemented yet"}


@router.delete("/{file_id}", response_model=MessageResponse)
async def delete_file(
    file_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
) -> Any:
    """
    Delete file
    """
    return MessageResponse(message="Delete file endpoint - not implemented yet")


@router.post("/profile-picture")
async def upload_profile_picture(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
) -> Any:
    """
    Upload profile picture using Firebase Storage or local storage
    """
    # Validate file type
    allowed_types = ["image/jpeg", "image/jpg", "image/png", "image/gif"]
    if file.content_type not in allowed_types:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only JPEG, PNG and GIF images are allowed"
        )
    
    # Validate file size (max 5MB)
    max_size = 5 * 1024 * 1024  # 5MB
    file_content = await file.read()
    if len(file_content) > max_size:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="File size must be less than 5MB"
        )
    
    try:
        # Process image
        img = Image.open(BytesIO(file_content))
        
        # Convert to RGB if necessary (for PNG with transparency)
        if img.mode in ("RGBA", "P"):
            img = img.convert("RGB")
        
        # Resize maintaining aspect ratio
        img.thumbnail((300, 300), Image.Resampling.LANCZOS)
        
        # Create a square image with white background
        square_img = Image.new("RGB", (300, 300), (255, 255, 255))
        
        # Center the resized image
        x = (300 - img.width) // 2
        y = (300 - img.height) // 2
        square_img.paste(img, (x, y))
        
        # Save processed image to BytesIO
        processed_image = BytesIO()
        square_img.save(processed_image, "JPEG", quality=85)
        processed_image.seek(0)
        
        # Generate unique filename
        file_extension = ".jpg"  # Always save as JPEG
        unique_filename = f"profile_{current_user.id}_{uuid.uuid4().hex}{file_extension}"
        
        # Delete old profile picture if exists
        if current_user.profile_picture:
            # Extract storage info from URL or path
            old_storage_type = "firebase" if current_user.profile_picture.startswith("http") else "local"
            if old_storage_type == "firebase":
                # Extract Firebase path from URL
                old_path = current_user.profile_picture.split("/")[-1]
                storage_manager.delete_file(f"{settings.firebase_static_path}/profile_pictures/{old_path}", "firebase")
            else:
                old_file_path = os.path.join(settings.upload_dir, current_user.profile_picture)
                storage_manager.delete_file(old_file_path, "local")
        
        # Upload processed image directly
        if settings.use_firebase_storage:
            # Upload to Firebase Storage
            from app.services.firebase_storage_service import firebase_storage_service
            firebase_path = f"profile_pictures/{unique_filename}"
            public_url = firebase_storage_service.upload_file(processed_image, firebase_path)
            result = {
                "url": public_url,
                "storage_type": "firebase"
            }
        else:
            # Save to local storage
            upload_path = os.path.join(settings.upload_dir, unique_filename)
            os.makedirs(os.path.dirname(upload_path), exist_ok=True)
            with open(upload_path, "wb") as f:
                processed_image.seek(0)
                f.write(processed_image.read())
            result = {
                "url": f"/uploads/{unique_filename}",
                "storage_type": "local"
            }
        
        # Update user profile picture in database
        current_user.profile_picture = result["url"]
        db.commit()
        db.refresh(current_user)
        
        return {
            "message": "Profile picture uploaded successfully",
            "profile_picture_url": result["url"],
            "storage_type": result["storage_type"]
        }
        
    except Exception as e:
        import traceback
        error_details = {
            "error_type": type(e).__name__,
            "error_message": str(e),
            "traceback": traceback.format_exc(),
            "firebase_enabled": settings.use_firebase_storage,
            "firebase_bucket": settings.firebase_storage_bucket,
            "firebase_credentials_path": settings.firebase_credentials_path
        }
        logger.error(f"Error en upload_profile_picture: {error_details}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error processing image: {str(e)}"
        )


@router.post("/course-material/{module_id}")
async def upload_course_material(
    module_id: int,
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
) -> Any:
    """
    Upload course material (PDF or Video) to a specific module
    """
    # Get the module and verify permissions
    module = db.query(CourseModule).filter(CourseModule.id == module_id).first()
    if not module:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Module not found"
        )
    
    # Get the course and check if user is the creator or admin
    course = db.query(Course).filter(Course.id == module.course_id).first()
    if not course:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Course not found"
        )
    
    if course.created_by != current_user.id and current_user.role.value not in ["admin", "capacitador"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough permissions to upload materials to this course"
        )
    
    # Determine material type based on file type
    material_type = None
    allowed_pdf_types = ["application/pdf"]
    allowed_video_types = ["video/mp4", "video/avi", "video/mov", "video/wmv", "video/webm"]
    
    if file.content_type in allowed_pdf_types:
        material_type = MaterialType.PDF
        max_size = 50 * 1024 * 1024  # 50MB for PDFs
    elif file.content_type in allowed_video_types:
        material_type = MaterialType.VIDEO
        max_size = 500 * 1024 * 1024  # 500MB for videos
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only PDF and video files are allowed"
        )
    
    # Validate file size
    file_content = await file.read()
    if len(file_content) > max_size:
        size_limit = "50MB" if material_type == MaterialType.PDF else "500MB"
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"File size must be less than {size_limit}"
        )
    
    # Reset file position
    await file.seek(0)
    
    try:
        # Determine folder for storage
        material_dir = "pdfs" if material_type == MaterialType.PDF else "videos"
        folder = f"uploads/course_materials/{material_dir}"
        
        # Upload using storage manager
        result = await storage_manager.upload_file(file, folder)
        
        # Create course material record
        course_material = CourseMaterial(
            module_id=module_id,
            title=os.path.splitext(file.filename)[0],  # Use original filename without extension as title
            description=f"Material uploaded: {file.filename}",
            material_type=material_type,
            file_url=result["url"],
            order_index=0  # Will be updated by frontend if needed
        )
        
        db.add(course_material)
        db.commit()
        db.refresh(course_material)
        
        return {
            "message": "Course material uploaded successfully",
            "material_id": course_material.id,
            "material_type": material_type.value,
            "file_url": result["url"],
            "storage_type": result["storage_type"],
            "title": course_material.title
        }
        
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error uploading material: {str(e)}"
        )


@router.delete("/course-material/{material_id}", response_model=MessageResponse)
async def delete_course_material(
    material_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
) -> Any:
    """
    Delete course material
    """
    # Get the material
    material = db.query(CourseMaterial).filter(CourseMaterial.id == material_id).first()
    if not material:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Material not found"
        )
    
    # Get the module and course to check permissions
    module = db.query(CourseModule).filter(CourseModule.id == material.module_id).first()
    course = db.query(Course).filter(Course.id == module.course_id).first()
    
    if course.created_by != current_user.id and current_user.role.value not in ["admin", "capacitador"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough permissions to delete this material"
        )
    
    try:
        # Store module_id before deleting the material
        module_id = material.module_id
        user_ids = []
        
        # First delete all user progress records for this material
        from app.models.user_progress import UserMaterialProgress, UserModuleProgress, MaterialProgressStatus
        progress_records = db.query(UserMaterialProgress).filter(
            UserMaterialProgress.material_id == material_id
        ).all()
        
        for progress in progress_records:
            user_ids.append(progress.user_id)
            db.delete(progress)
        
        # Delete the file from storage
        if material.file_url:
            try:
                await storage_manager.delete_file(material.file_url)
            except Exception as e:
                logger.warning(f"Failed to delete file {material.file_url}: {str(e)}")
        
        # Delete database record
        db.delete(material)
        db.commit()
        
        # Update module progress for all affected users
        if module_id and user_ids:
            user_ids = list(set(user_ids))  # Remove duplicates
            for user_id in user_ids:
                # Get all materials in the module
                module_materials = db.query(CourseMaterial).filter(CourseMaterial.module_id == module_id).all()
                
                # Count completed materials for this user
                completed_materials = db.query(UserMaterialProgress).filter(
                    UserMaterialProgress.user_id == user_id,
                    UserMaterialProgress.material_id.in_([m.id for m in module_materials]),
                    UserMaterialProgress.status == MaterialProgressStatus.COMPLETED
                ).count()
                
                # Update module progress
                module_progress = db.query(UserModuleProgress).filter(
                    UserModuleProgress.user_id == user_id,
                    UserModuleProgress.module_id == module_id
                ).first()
                
                if module_progress:
                    module_progress.materials_completed = completed_materials
                    module_progress.total_materials = len(module_materials)
                    module_progress.calculate_progress()
                    db.commit()
        
        return MessageResponse(message="Course material deleted successfully")
        
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error deleting material: {str(e)}"
        )


@router.get("/course-material/{material_id}/view")
async def view_course_material(
    material_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
) -> Any:
    """
    Get course material for viewing (no download)
    """
    # Get the material
    material = db.query(CourseMaterial).filter(CourseMaterial.id == material_id).first()
    if not material:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Material not found"
        )
    
    # Check if user has access to this material (enrolled in course)
    module = db.query(CourseModule).filter(CourseModule.id == material.module_id).first()
    course = db.query(Course).filter(Course.id == module.course_id).first()
    
    # Check enrollment or if user is creator/admin
    from app.models.enrollment import Enrollment
    enrollment = db.query(Enrollment).filter(
        Enrollment.user_id == current_user.id,
        Enrollment.course_id == course.id
    ).first()
    
    if not enrollment and course.created_by != current_user.id and current_user.role.value not in ["admin", "capacitador"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enrolled in this course"
        )
    
    # For LINK type materials, return the URL as-is (external links like YouTube)
    # For other types (PDF, VIDEO), use the stored URL directly
    file_url = material.file_url
    
    # Agregar un campo para indicar si el usuario puede descargar el material
    # Solo los administradores, capacitadores y creadores del curso pueden descargar
    can_download = (current_user.role.value in ["admin", "trainer", "supervisor"] or 
                   course.created_by == current_user.id)
    
    return {
        "id": material.id,
        "title": material.title,
        "description": material.description,
        "material_type": material.material_type.value,
        "file_url": file_url,
        "can_download": can_download
    }


@router.get("/course-material/{material_id}/download")
async def download_course_material(
    material_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
) -> Any:
    """
    Download course material - only available for admin, trainer, supervisor and course creator
    """
    # Get the material
    material = db.query(CourseMaterial).filter(CourseMaterial.id == material_id).first()
    if not material:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Material not found"
        )
    
    # Check if user has access to this material (enrolled in course)
    module = db.query(CourseModule).filter(CourseModule.id == material.module_id).first()
    course = db.query(Course).filter(Course.id == module.course_id).first()
    
    # Verificar si el usuario tiene permisos para descargar
    # Solo los administradores, capacitadores, supervisores y creadores del curso pueden descargar
    if current_user.role.value not in ["admin", "trainer", "supervisor"] and course.created_by != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No tienes permisos para descargar este material"
        )
    
    # Para enlaces externos, redirigir al enlace
    if material.material_type.value == "link":
        return RedirectResponse(url=material.file_url)
    
    # Para archivos, usar el storage manager para obtener el archivo
    try:
        file_data = await storage_manager.download_file(material.file_url)
        if file_data is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="File not found"
            )
        
        # Determinar el nombre del archivo
        filename = os.path.basename(material.file_url) or f"{material.title}.pdf"
        
        # Determinar el tipo de contenido
        content_type = "application/pdf" if material.material_type.value == "pdf" else "video/mp4"
        
        return Response(
            content=file_data,
            media_type=content_type,
            headers={"Content-Disposition": f"attachment; filename={filename}"}
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error downloading file: {str(e)}"
        )