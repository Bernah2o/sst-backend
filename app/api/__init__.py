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
from .seguimiento_actividades import router as seguimiento_actividades_router
from .permissions import router as permissions_router
from .absenteeism import router as absenteeism_router
from .audit import router as audit_router
from .occupational_exams import router as occupational_exams_router
from .occupational_exam_notifications import router as occupational_exam_notifications_router
from .admin_notifications import router as admin_notifications_router
from .suppliers import router as suppliers_router
from .supervisor_dashboard import router as supervisor_dashboard_router
from .committees import router as committees_router
from .committee_members import router as committee_members_router
from .committee_meetings import router as committee_meetings_router
from .committee_votings import router as committee_votings_router
from .committee_activities import router as committee_activities_router
from .committee_permissions import router as committee_permissions_router
from .candidate_voting import router as candidate_voting_router
from .areas import router as areas_router
from .contractors import router as contractors_router
from .profesiogramas import router as profesiogramas_router
from .restricciones_medicas import router as restricciones_medicas_router
from .assessments import router as assessments_router
from .sectores_economicos import router as sectores_economicos_router
from .empresas import router as empresas_router
from .matriz_legal import router as matriz_legal_router
from .interactive_lessons import router as interactive_lessons_router
from .plan_trabajo_anual import router as plan_trabajo_anual_router



api_router = APIRouter()

# Include available routers
api_router.include_router(assessments_router, prefix="/assessments", tags=["assessments"])
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
api_router.include_router(seguimiento_actividades_router, prefix="/seguimiento-actividades", tags=["seguimiento-actividades"])
api_router.include_router(permissions_router, prefix="/permissions", tags=["permissions"])
api_router.include_router(absenteeism_router, prefix="/absenteeism", tags=["absenteeism"])
api_router.include_router(audit_router, prefix="/audit", tags=["audit"])
api_router.include_router(occupational_exams_router, prefix="/occupational-exams", tags=["occupational-exams"])
api_router.include_router(occupational_exam_notifications_router, prefix="/occupational-exam-notifications", tags=["occupational-exam-notifications"])
api_router.include_router(occupational_exam_notifications_router, prefix="/exam-scheduler", tags=["exam-scheduler"])
api_router.include_router(admin_notifications_router, tags=["admin-notifications"])
api_router.include_router(suppliers_router, prefix="/suppliers", tags=["suppliers"])
api_router.include_router(supervisor_dashboard_router, prefix="/supervisor", tags=["supervisor"])
api_router.include_router(committees_router, prefix="/committees", tags=["committees"])
api_router.include_router(committee_members_router, prefix="/committee-members", tags=["committee-members"])
api_router.include_router(committee_meetings_router, prefix="/committee-meetings", tags=["committee-meetings"])
api_router.include_router(committee_votings_router, prefix="/committee-votings", tags=["committee-votings"])
api_router.include_router(committee_activities_router, prefix="/committee-activities", tags=["committee-activities"])
api_router.include_router(committee_permissions_router, prefix="/committee-permissions", tags=["committee-permissions"])
api_router.include_router(candidate_voting_router, prefix="/candidate-voting", tags=["candidate-voting"])
api_router.include_router(areas_router, prefix="/areas", tags=["areas"])
api_router.include_router(contractors_router, prefix="/contractors", tags=["contractors"])
api_router.include_router(profesiogramas_router, prefix="/profesiogramas", tags=["profesiogramas"])
api_router.include_router(restricciones_medicas_router, prefix="/restricciones-medicas", tags=["restricciones-medicas"])
api_router.include_router(sectores_economicos_router, prefix="/sectores-economicos", tags=["sectores-economicos"])
api_router.include_router(empresas_router, prefix="/empresas", tags=["empresas"])
api_router.include_router(matriz_legal_router, prefix="/matriz-legal", tags=["matriz-legal"])
api_router.include_router(interactive_lessons_router, prefix="/interactive-lessons", tags=["interactive-lessons"])
api_router.include_router(plan_trabajo_anual_router, prefix="/plan-trabajo-anual", tags=["plan-trabajo-anual"])
