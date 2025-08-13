import os
import uuid
from typing import Any, List
from PIL import Image

from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File
from fastapi.responses import FileResponse, RedirectResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_active_user
from app.models.user import User
from app.models.course import Course, CourseModule, CourseMaterial, MaterialType
from app.schemas.common import MessageResponse
from app.config import settings

router = APIRouter()


@router.post("/upload")
async def upload_file(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
) -> Any:
    """
    Upload a file
    """
    return {"message": "File upload endpoint - not implemented yet", "filename": file.filename}


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
    Upload profile picture
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
    
    # Create uploads directory if it doesn't exist
    upload_dir = os.path.join(settings.upload_dir, "profile_pictures")
    os.makedirs(upload_dir, exist_ok=True)
    
    # Generate unique filename
    file_extension = os.path.splitext(file.filename)[1]
    unique_filename = f"{current_user.id}_{uuid.uuid4().hex}{file_extension}"
    file_path = os.path.join(upload_dir, unique_filename)
    
    try:
        # Save and resize image
        with open(file_path, "wb") as buffer:
            buffer.write(file_content)
        
        # Resize image to 300x300 pixels
        with Image.open(file_path) as img:
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
            
            # Save the processed image
            square_img.save(file_path, "JPEG", quality=85)
        
        # Delete old profile picture if exists
        if current_user.profile_picture:
            old_file_path = os.path.join(settings.upload_dir, current_user.profile_picture)
            if os.path.exists(old_file_path):
                os.remove(old_file_path)
        
        # Update user profile picture in database
        profile_picture_url = f"profile_pictures/{unique_filename}"
        current_user.profile_picture = profile_picture_url
        db.commit()
        db.refresh(current_user)
        
        return {
            "message": "Profile picture uploaded successfully",
            "profile_picture_url": f"/uploads/{profile_picture_url}"
        }
        
    except Exception as e:
        # Clean up file if something went wrong
        if os.path.exists(file_path):
            os.remove(file_path)
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
    
    # Create uploads directory
    material_dir = "pdfs" if material_type == MaterialType.PDF else "videos"
    upload_dir = os.path.join(settings.upload_dir, "course_materials", material_dir)
    os.makedirs(upload_dir, exist_ok=True)
    
    # Generate unique filename
    file_extension = os.path.splitext(file.filename)[1]
    unique_filename = f"{module_id}_{uuid.uuid4().hex}{file_extension}"
    file_path = os.path.join(upload_dir, unique_filename)
    
    try:
        # Save file
        with open(file_path, "wb") as buffer:
            buffer.write(file_content)
        
        # Create course material record
        file_url = f"course_materials/{material_dir}/{unique_filename}"
        course_material = CourseMaterial(
            module_id=module_id,
            title=os.path.splitext(file.filename)[0],  # Use original filename without extension as title
            description=f"Material uploaded: {file.filename}",
            material_type=material_type,
            file_path=file_path,
            file_url=file_url,
            file_size=len(file_content),
            mime_type=file.content_type,
            order_index=0  # Will be updated by frontend if needed
        )
        
        db.add(course_material)
        db.commit()
        db.refresh(course_material)
        
        return {
            "message": "Course material uploaded successfully",
            "material_id": course_material.id,
            "material_type": material_type.value,
            "file_url": f"/uploads/{file_url}",
            "title": course_material.title
        }
        
    except Exception as e:
        # Clean up file if something went wrong
        if os.path.exists(file_path):
            os.remove(file_path)
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
        
        # Delete physical file
        if material.file_path and os.path.exists(material.file_path):
            os.remove(material.file_path)
        
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
    # For other types (PDF, VIDEO), add the /uploads/ prefix for local files
    if material.material_type.value == "link":
        file_url = material.file_url
    else:
        file_url = f"/uploads/{material.file_url}"
    
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
        "mime_type": material.mime_type,
        "file_size": material.file_size,
        "duration_seconds": material.duration_seconds,
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
    
    # Para archivos locales, devolver el archivo para descarga
    file_path = os.path.join(settings.upload_dir, material.file_url)
    if not os.path.exists(file_path):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="File not found"
        )
    
    return FileResponse(
        path=file_path,
        filename=os.path.basename(file_path),
        media_type=material.mime_type
    )