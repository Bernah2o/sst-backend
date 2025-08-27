#!/usr/bin/env python3
"""
Script para probar el flujo completo de la API:
1. Completar material via endpoint
2. Consultar dashboard via endpoint
3. Verificar consistencia
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

import asyncio
from sqlalchemy.orm import Session
from app.database import SessionLocal
from app.models.user import User
from app.models.course import Course, CourseModule, CourseMaterial
from app.models.enrollment import Enrollment
from app.models.user_progress import UserMaterialProgress, MaterialProgressStatus
from app.api.progress import complete_material, get_user_dashboard
from sqlalchemy import and_

async def test_api_flow():
    db: Session = SessionLocal()
    
    try:
        print("🔄 PRUEBA DE FLUJO COMPLETO DE API")
        print("="*50)
        
        # Buscar usuario con inscripción
        user_with_enrollment = db.query(User).join(Enrollment).first()
        if not user_with_enrollment:
            print("❌ No se encontró usuario con inscripción")
            return
        
        user = user_with_enrollment
        print(f"👤 Usuario: {user.first_name} {user.last_name} (ID: {user.id})")
        
        # Buscar inscripción
        enrollment = db.query(Enrollment).filter(
            Enrollment.user_id == user.id
        ).first()
        
        # Obtener curso y material
        course = db.query(Course).filter(Course.id == enrollment.course_id).first()
        module = db.query(CourseModule).filter(CourseModule.course_id == course.id).first()
        material = db.query(CourseMaterial).filter(CourseMaterial.module_id == module.id).first()
        
        print(f"📚 Curso: {course.title}")
        print(f"📝 Módulo: {module.title}")
        print(f"📄 Material: {material.title} (ID: {material.id})")
        
        # PASO 1: Verificar estado inicial
        print("\n📊 PASO 1: Estado inicial")
        initial_progress = db.query(UserMaterialProgress).filter(
            and_(
                UserMaterialProgress.user_id == user.id,
                UserMaterialProgress.material_id == material.id
            )
        ).first()
        
        if initial_progress:
            print(f"   Estado actual: {initial_progress.status}")
            print(f"   Progreso: {initial_progress.progress_percentage}%")
        else:
            print("   No hay progreso registrado")
        
        # PASO 2: Simular inicio del material si no existe
        if not initial_progress:
            print("\n🚀 PASO 2: Iniciando material")
            progress = UserMaterialProgress(
                user_id=user.id,
                material_id=material.id,
                enrollment_id=enrollment.id
            )
            progress.start_material()
            db.add(progress)
            db.commit()
            print(f"   ✅ Material iniciado: {progress.status}")
        
        # PASO 3: Completar material via endpoint
        print("\n✅ PASO 3: Completando material via API endpoint")
        
        # Crear un mock del current_user para el endpoint
        class MockUser:
            def __init__(self, user_obj):
                self.id = user_obj.id
                self.first_name = user_obj.first_name
                self.last_name = user_obj.last_name
                self.role = user_obj.role
        
        mock_user = MockUser(user)
        
        try:
            # Llamar al endpoint de completar material
            result = await complete_material(
                material_id=material.id,
                current_user=mock_user,
                db=db
            )
            print(f"   ✅ Respuesta del endpoint: {result}")
        except Exception as e:
            print(f"   ❌ Error en endpoint complete_material: {e}")
            return
        
        # PASO 4: Verificar estado después de completar
        print("\n🔍 PASO 4: Verificando estado después de completar")
        db.refresh(db.query(UserMaterialProgress).filter(
            and_(
                UserMaterialProgress.user_id == user.id,
                UserMaterialProgress.material_id == material.id
            )
        ).first())
        
        completed_progress = db.query(UserMaterialProgress).filter(
            and_(
                UserMaterialProgress.user_id == user.id,
                UserMaterialProgress.material_id == material.id
            )
        ).first()
        
        if completed_progress:
            print(f"   Estado: {completed_progress.status}")
            print(f"   Progreso: {completed_progress.progress_percentage}%")
            print(f"   Completado: {completed_progress.completed_at}")
        else:
            print("   ❌ No se encontró progreso después de completar")
            return
        
        # PASO 5: Consultar dashboard via endpoint
        print("\n📋 PASO 5: Consultando dashboard via API endpoint")
        
        try:
            dashboard_result = await get_user_dashboard(
                current_user=mock_user,
                db=db
            )
            
            print(f"   ✅ Dashboard obtenido exitosamente")
            print(f"   Total de cursos: {dashboard_result['total_courses']}")
            
            # Buscar nuestro material en el dashboard
            found_material = False
            for course_data in dashboard_result['courses']:
                if course_data['course_id'] == course.id:
                    print(f"\n   📚 Curso encontrado: {course_data['course_title']}")
                    print(f"   Progreso del curso: {course_data['progress_percentage']}%")
                    
                    for module_data in course_data['modules']:
                        if module_data['module_id'] == module.id:
                            print(f"\n   📝 Módulo encontrado: {module_data['title']}")
                            print(f"   Materiales completados: {module_data['completed_materials']}/{module_data['total_materials']}")
                            
                            # Verificar si nuestro material aparece como completado
                            if module_data['completed_materials'] > 0:
                                print(f"   ✅ Material aparece como completado en dashboard")
                                found_material = True
                            else:
                                print(f"   ❌ Material NO aparece como completado en dashboard")
                            break
                    break
            
            if not found_material:
                print("   ❌ No se encontró el material en el dashboard")
        
        except Exception as e:
            print(f"   ❌ Error en endpoint get_user_dashboard: {e}")
            return
        
        # PASO 6: Verificación final directa en BD
        print("\n🎯 PASO 6: Verificación final en base de datos")
        final_check = db.query(UserMaterialProgress).filter(
            and_(
                UserMaterialProgress.user_id == user.id,
                UserMaterialProgress.material_id == material.id
            )
        ).first()
        
        if final_check and final_check.status == MaterialProgressStatus.COMPLETED:
            print("   ✅ ÉXITO: Material confirmado como completado en BD")
            print(f"   Estado: {final_check.status}")
            print(f"   Progreso: {final_check.progress_percentage}%")
            print(f"   Completado: {final_check.completed_at}")
        else:
            print("   ❌ FALLO: Material no está completado en BD")
            if final_check:
                print(f"   Estado encontrado: {final_check.status}")
                print(f"   Progreso: {final_check.progress_percentage}%")
        
        print("\n🏁 RESUMEN DE LA PRUEBA")
        print("="*30)
        if found_material and final_check and final_check.status == MaterialProgressStatus.COMPLETED:
            print("✅ ÉXITO TOTAL: El flujo de API funciona correctamente")
            print("   - Material se completa correctamente")
            print("   - Dashboard muestra el estado correcto")
            print("   - Base de datos mantiene la persistencia")
        else:
            print("❌ PROBLEMA DETECTADO en el flujo de API")
            print("   - Revisar lógica de endpoints o consultas")
        
    except Exception as e:
        print(f"❌ Error durante la prueba: {e}")
        import traceback
        traceback.print_exc()
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    asyncio.run(test_api_flow())