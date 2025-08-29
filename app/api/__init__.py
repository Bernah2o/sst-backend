from fastapi import APIRouter

from .auth import router as auth_router
from .users import router as users_router
from .workers import router as workers_router
from .courses import router as courses_router
from .evaluations import router as evaluations_router
from .surveys import router as surveys_router
from .notifications import router as notifications_router
from .certificates import router as certificates_router
from .attendance import router as attendance_router
from .reports import router as reports_router
from .files import router as files_router
from .progress import router as progress_router
from .enrollments import router as enrollments_router
from .user_progress import router as user_progress_router
from .admin_config import router as admin_config_router
from .admin_attendance import router as admin_attendance_router
from .reinduction import router as reinduction_router
from .seguimientos import router as seguimientos_router
from .permissions import router as permissions_router
from .absenteeism import router as absenteeism_router
from .audit import router as audit_router
from .occupational_exams import router as occupational_exams_router



api_router = APIRouter()

# Include available routers
api_router.include_router(auth_router, prefix="/auth", tags=["authentication"])
api_router.include_router(users_router, prefix="/users", tags=["users"])
api_router.include_router(workers_router, prefix="/workers", tags=["workers"])
api_router.include_router(courses_router, prefix="/courses", tags=["courses"])
api_router.include_router(evaluations_router, prefix="/evaluations", tags=["evaluations"])
api_router.include_router(surveys_router, prefix="/surveys", tags=["surveys"])
api_router.include_router(notifications_router, prefix="/notifications", tags=["notifications"])
api_router.include_router(certificates_router, prefix="/certificates", tags=["certificates"])
api_router.include_router(attendance_router, prefix="/attendance", tags=["attendance"])
api_router.include_router(reports_router, prefix="/reports", tags=["reports"])
api_router.include_router(files_router, prefix="/files", tags=["files"])
api_router.include_router(progress_router, prefix="/progress", tags=["progress"])
api_router.include_router(enrollments_router, prefix="/enrollments", tags=["enrollments"])
api_router.include_router(user_progress_router, prefix="/user-progress", tags=["user-progress"])
api_router.include_router(admin_config_router, prefix="/admin/config", tags=["admin"])
api_router.include_router(admin_attendance_router, prefix="/admin/attendance", tags=["admin", "attendance"])
api_router.include_router(reinduction_router, prefix="/reinduction", tags=["reinduction"])
api_router.include_router(seguimientos_router, prefix="/seguimientos", tags=["seguimientos"])
api_router.include_router(permissions_router, prefix="/permissions", tags=["permissions"])
api_router.include_router(absenteeism_router, prefix="/absenteeism", tags=["absenteeism"])
api_router.include_router(audit_router, prefix="/audit", tags=["audit"])
api_router.include_router(occupational_exams_router, prefix="/occupational-exams", tags=["occupational-exams"])