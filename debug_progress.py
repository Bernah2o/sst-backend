#!/usr/bin/env python3
"""
Script de depuración para verificar el progreso del usuario y condiciones de encuestas/evaluaciones
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Disable SQLAlchemy logging
import logging
logging.getLogger('sqlalchemy.engine').setLevel(logging.WARNING)

from sqlalchemy.orm import Session
from app.database import SessionLocal
from app.models.user import User
from app.models.enrollment import Enrollment
from app.models.course import Course, CourseModule, CourseMaterial
from app.models.user_progress import UserMaterialProgress, UserModuleProgress, MaterialProgressStatus
from app.models.survey import Survey, UserSurvey, SurveyStatus, UserSurveyStatus
from app.models.evaluation import Evaluation, UserEvaluation, UserEvaluationStatus
from app.schemas.evaluation import EvaluationStatus
from sqlalchemy import and_

def debug_user_progress(email: str):
    """Debug user progress for specific email"""
    db = SessionLocal()
    
    try:
        # Find user
        user = db.query(User).filter(User.email == email).first()
        if not user:
            print(f"❌ Usuario no encontrado: {email}")
            return
        
        print(f"✅ Usuario encontrado: {user.first_name} {user.last_name} ({user.email})")
        print(f"   Rol: {user.role}")
        
        # Get enrollments
        enrollments = db.query(Enrollment).filter(Enrollment.user_id == user.id).all()
        print(f"\n📚 Inscripciones encontradas: {len(enrollments)}")
        
        for enrollment in enrollments:
            course = db.query(Course).filter(Course.id == enrollment.course_id).first()
            print(f"\n{'='*50}")
            print(f"🎓 CURSO: {course.title}")
            print(f"{'='*50}")
            print(f"📊 Progreso de inscripción: {enrollment.progress}%")
            print(f"📋 Estado: {enrollment.status}")
            
            # Get modules
            modules = db.query(CourseModule).filter(CourseModule.course_id == course.id).all()
            print(f"\n📖 Módulos en el curso: {len(modules)}")
            
            total_module_progress = 0
            modules_with_progress = 0
            
            for i, module in enumerate(modules, 1):
                module_progress = db.query(UserModuleProgress).filter(
                    and_(
                        UserModuleProgress.user_id == user.id,
                        UserModuleProgress.module_id == module.id
                    )
                ).first()
                
                if module_progress:
                    print(f"  📝 Módulo {i}: '{module.title}' - {module_progress.progress_percentage}%")
                    total_module_progress += module_progress.progress_percentage
                    modules_with_progress += 1
                    
                    # Get materials in this module
                    materials = db.query(CourseMaterial).filter(CourseMaterial.module_id == module.id).all()
                    completed_materials = 0
                    
                    for material in materials:
                        material_progress = db.query(UserMaterialProgress).filter(
                            and_(
                                UserMaterialProgress.user_id == user.id,
                                UserMaterialProgress.material_id == material.id
                            )
                        ).first()
                        
                        if material_progress:
                            status_icon = "✅" if material_progress.status == MaterialProgressStatus.COMPLETED else "🔄" if material_progress.status == MaterialProgressStatus.IN_PROGRESS else "⭕"
                            print(f"     {status_icon} '{material.title}': {material_progress.status} ({material_progress.progress_percentage}%)")
                            if material_progress.status == MaterialProgressStatus.COMPLETED:
                                completed_materials += 1
                        else:
                            print(f"     ⭕ '{material.title}': NO INICIADO")
                    
                    print(f"     📊 Materiales completados: {completed_materials}/{len(materials)}")
                else:
                    print(f"  ⭕ Módulo {i}: '{module.title}' - SIN PROGRESO")
            
            # Calculate actual course progress
            if modules_with_progress > 0:
                calculated_progress = total_module_progress / len(modules)
                print(f"\n🧮 Progreso calculado: {calculated_progress:.2f}%")
                print(f"💾 Progreso en BD: {enrollment.progress}%")
                
                if abs(calculated_progress - enrollment.progress) > 0.01:
                    print("⚠️  DISCREPANCIA EN PROGRESO DETECTADA")
            
            # Check surveys
            print(f"\n📋 ENCUESTAS")
            print(f"{'-'*30}")
            required_surveys = db.query(Survey).filter(
                and_(
                    Survey.course_id == course.id,
                    Survey.required_for_completion == True,
                    Survey.status == SurveyStatus.PUBLISHED
                )
            ).all()
            
            print(f"📝 Encuestas requeridas: {len(required_surveys)}")
            
            pending_surveys = []
            for survey in required_surveys:
                user_submission = db.query(UserSurvey).filter(
                    and_(
                        UserSurvey.user_id == user.id,
                        UserSurvey.survey_id == survey.id,
                        UserSurvey.status == UserSurveyStatus.COMPLETED
                    )
                ).first()
                
                if user_submission:
                    print(f"  ✅ '{survey.title}': COMPLETADA")
                else:
                    print(f"  ❌ '{survey.title}': PENDIENTE")
                    pending_surveys.append(survey)
            
            print(f"⏳ Encuestas pendientes: {len(pending_surveys)}")
            
            # Check evaluations
            print(f"\n🎯 EVALUACIONES")
            print(f"{'-'*30}")
            course_evaluations = db.query(Evaluation).filter(
                and_(
                    Evaluation.course_id == course.id,
                    Evaluation.status == EvaluationStatus.PUBLISHED
                )
            ).all()
            
            print(f"📊 Evaluaciones disponibles: {len(course_evaluations)}")
            
            evaluation_completed = False
            for evaluation in course_evaluations:
                completed_evaluation = db.query(UserEvaluation).filter(
                    and_(
                        UserEvaluation.user_id == user.id,
                        UserEvaluation.evaluation_id == evaluation.id,
                        UserEvaluation.status == UserEvaluationStatus.COMPLETED
                    )
                ).first()
                
                if completed_evaluation:
                    print(f"  ✅ '{evaluation.title}': COMPLETADA ({completed_evaluation.percentage}%)")
                    evaluation_completed = True
                else:
                    print(f"  ❌ '{evaluation.title}': PENDIENTE")
            
            # Show conditions
            print(f"\n🔍 CONDICIONES PARA ACCESO")
            print(f"{'-'*40}")
            print(f"✅ Progreso >= 95%: {enrollment.progress >= 95}")
            print(f"📝 Encuestas pendientes: {len(pending_surveys)}")
            print(f"🔓 Puede tomar encuesta: {enrollment.progress >= 95}")
            print(f"🔓 Puede tomar evaluación: {enrollment.progress >= 95 and len(pending_surveys) == 0 and not evaluation_completed}")
            
            if enrollment.progress >= 95 and len(pending_surveys) > 0:
                print(f"\n⚠️  PROBLEMA IDENTIFICADO:")
                print(f"   El usuario completó el curso pero tiene {len(pending_surveys)} encuesta(s) pendiente(s).")
                print(f"   Esto impide que pueda acceder a la evaluación.")
                
    finally:
        db.close()

if __name__ == "__main__":
    email = "asesoriaspymeg@gmail.com"
    debug_user_progress(email)