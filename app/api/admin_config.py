from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_

from app.database import get_db
from app.models.admin_config import AdminConfig, Programas
from app.models.cargo import Cargo
from app.models.seguridad_social import SeguridadSocial
from app.schemas.admin_config import (
    AdminConfigCreate,
    AdminConfigUpdate,
    AdminConfig as AdminConfigSchema,
    AdminConfigList,
    ProgramasCreate,
    ProgramasUpdate,
    Programas as ProgramasSchema
)
from app.schemas.cargo import CargoCreate, CargoUpdate, Cargo as CargoSchema
from app.schemas.seguridad_social import SeguridadSocialCreate, SeguridadSocialUpdate, SeguridadSocial as SeguridadSocialSchema
from app.dependencies import require_admin, get_current_active_user
from app.models.user import User
from app.models.worker_document import WorkerDocument
from app.models.contractor import ContractorDocument
from app.models.occupational_exam import OccupationalExam
from app.models.course import CourseMaterial, CourseModule
from app.models.certificate import Certificate
from app.models.committee import CommitteeDocument, Committee, CommitteeMember, CommitteeMeeting, CommitteeActivity
from app.utils.storage import storage_manager
from app.services.s3_storage import s3_service
import httpx
from app.config import settings
import logging
from datetime import datetime

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("/categories{trailing_slash:path}", response_model=List[str])
async def get_categories(
    trailing_slash: str = "",
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """Get all available configuration categories"""
    categories = db.query(AdminConfig.category).distinct().all()
    return [cat[0] for cat in categories]


@router.get("/category/{category}", response_model=AdminConfigList)
async def get_configs_by_category(
    category: str,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """Get all configurations for a specific category"""
    if category == "position":
        # Redirigir a cargos para mantener compatibilidad
        cargos = db.query(Cargo).all()
        # Convertir cargos a formato AdminConfig para compatibilidad
        configs = [
            AdminConfigSchema(
                id=cargo.id,
                category="position",
                display_name=cargo.nombre_cargo,
                emo_periodicity=cargo.periodicidad_emo,
                is_active=cargo.activo,
                created_at=cargo.created_at,
                updated_at=cargo.updated_at
            )
            for cargo in cargos
        ]
        return AdminConfigList(
            category=category,
            configs=configs
        )
    
    configs = db.query(AdminConfig).filter(
        AdminConfig.category == category
    ).order_by(AdminConfig.display_name).all()
    
    return AdminConfigList(
        category=category,
        configs=configs
    )


@router.get("/category/{category}/active", response_model=List[AdminConfigSchema])
async def get_active_configs_by_category(
    category: str,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """Get all active configurations for a specific category (admin endpoint)"""
    configs = db.query(AdminConfig).filter(
        and_(
            AdminConfig.category == category,
            AdminConfig.is_active == True
        )
    ).order_by(AdminConfig.display_name).all()
    
    return configs


@router.get("/active/{category}", response_model=List[AdminConfigSchema])
async def get_public_active_configs(
    category: str,
    db: Session = Depends(get_db)
):
    """Public endpoint to get all active configurations for a specific category"""
    configs = db.query(AdminConfig).filter(
        and_(
            AdminConfig.category == category,
            AdminConfig.is_active == True
        )
    ).order_by(AdminConfig.display_name).all()
    
    return configs


@router.post("/migrate-storage/firebase-to-contabo")
async def migrate_firebase_to_contabo(
    dry_run: bool = Query(False, description="Simular sin realizar cambios"),
    limit: int = Query(500, ge=1, le=5000, description="Máximo de registros a procesar por tipo"),
    start_after_id: int = Query(0, ge=0, description="Procesar registros con id > start_after_id"),
    types: List[str] = Query(
        [
            "worker_documents",
            "contractor_documents",
            "occupational_exams",
            "course_materials",
            "certificates",
            "committee_documents",
            "committee_urls",
        ],
        description="Tipos a migrar"
    ),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin)
):
    """Migrar archivos existentes desde Firebase a Contabo y actualizar URLs en BD"""
    if not settings.use_contabo_storage:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Contabo no está habilitado en configuración")

    def is_firebase_url(url: str) -> bool:
        if not url:
            return False
        return ("firebasestorage.googleapis.com" in url) or ("storage.googleapis.com" in url)

    def firebase_url_clause(column):
        return or_(
            column.ilike("%firebasestorage.googleapis.com%"),
            column.ilike("%storage.googleapis.com%"),
        )

    def is_s3_url(url: str) -> bool:
        if not url:
            return False
        return "s3.amazonaws.com" in url

    def s3_url_clause(column):
        return column.ilike("%s3.amazonaws.com%")

    def safe_filename_from_url(url: str, fallback_name: str) -> str:
        try:
            key = storage_manager._extract_firebase_path(url)
            if key:
                return key.split("/")[-1]
        except Exception:
            pass
        return fallback_name

    summary = {
        "dry_run": dry_run,
        "start_after_id": start_after_id,
        "processed": {
            "worker_documents": 0,
            "contractor_documents": 0,
            "occupational_exams": 0,
            "course_materials": 0,
            "certificates": 0,
            "committee_documents": 0,
            "committee_urls": 0,
        },
        "migrated": {
            "worker_documents": 0,
            "contractor_documents": 0,
            "occupational_exams": 0,
            "course_materials": 0,
            "certificates": 0,
            "committee_documents": 0,
            "committee_urls": 0,
        },
        "skipped": {
            "worker_documents": 0,
            "contractor_documents": 0,
            "occupational_exams": 0,
            "course_materials": 0,
            "certificates": 0,
            "committee_documents": 0,
            "committee_urls": 0,
        },
        "last_ids": {},
        "errors": [],
    }

    # Worker documents
    if "worker_documents" in types:
        q = (
            db.query(WorkerDocument)
            .filter(
                WorkerDocument.is_active == True,
                WorkerDocument.id > start_after_id,
                firebase_url_clause(WorkerDocument.file_url),
            )
            .order_by(WorkerDocument.id.asc())
            .limit(limit)
            .all()
        )
        for doc in q:
            summary["processed"]["worker_documents"] += 1
            if not is_firebase_url(doc.file_url):
                summary["skipped"]["worker_documents"] += 1
                continue
            try:
                content = await storage_manager.download_file(doc.file_url, storage_type=None)
                if not content:
                    summary["errors"].append({"type": "worker_documents", "id": doc.id, "error": "No se pudo descargar"})
                    continue
                filename = safe_filename_from_url(doc.file_url, f"{doc.id}_{doc.file_name}")
                folder = f"workers/{doc.worker_id}/documents"
                if dry_run:
                    summary["migrated"]["worker_documents"] += 1
                    continue
                upload = await storage_manager.upload_bytes(content, filename, folder, doc.file_type or "application/octet-stream")
                if not upload or not upload.get("url"):
                    summary["errors"].append({"type": "worker_documents", "id": doc.id, "error": "Upload falló"})
                    continue
                doc.file_url = upload["url"]
                doc.file_size = upload.get("size")
                doc.updated_at = datetime.utcnow()
                db.add(doc)
                db.commit()
                summary["migrated"]["worker_documents"] += 1
            except Exception as e:
                db.rollback()
                logger.error(f"Error migrando WorkerDocument {doc.id}: {e}")
                summary["errors"].append({"type": "worker_documents", "id": doc.id, "error": str(e)})
        if q:
            summary["last_ids"]["worker_documents"] = q[-1].id

    # Contractor documents
    if "contractor_documents" in types:
        cq = (
            db.query(ContractorDocument)
            .filter(
                ContractorDocument.id > start_after_id,
                ContractorDocument.file_path != None,
                or_(
                    firebase_url_clause(ContractorDocument.file_path),
                    s3_url_clause(ContractorDocument.file_path),
                ),
            )
            .order_by(ContractorDocument.id.asc())
            .limit(limit)
            .all()
        )
        for cdoc in cq:
            summary["processed"]["contractor_documents"] += 1
            if not is_firebase_url(cdoc.file_path) and not is_s3_url(cdoc.file_path):
                summary["skipped"]["contractor_documents"] += 1
                continue
            try:
                if is_firebase_url(cdoc.file_path):
                    content = await storage_manager.download_file(cdoc.file_path, storage_type=None)
                else:
                    file_key = cdoc.file_path.split('.com/')[-1]
                    signed_url = s3_service.get_file_url(file_key, expiration=3600)
                    async with httpx.AsyncClient() as client:
                        resp = await client.get(signed_url)
                        resp.raise_for_status()
                        content = resp.content
                if not content:
                    summary["errors"].append({"type": "contractor_documents", "id": cdoc.id, "error": "No se pudo descargar"})
                    continue
                filename = safe_filename_from_url(cdoc.file_path, f"{cdoc.id}_{cdoc.document_name}")
                folder = f"contractors/{cdoc.contractor_id}/documents/{cdoc.document_type}"
                if dry_run:
                    summary["migrated"]["contractor_documents"] += 1
                    continue
                upload = await storage_manager.upload_bytes(content, filename, folder, cdoc.content_type or "application/octet-stream")
                if not upload or not upload.get("url"):
                    summary["errors"].append({"type": "contractor_documents", "id": cdoc.id, "error": "Upload falló"})
                    continue
                cdoc.file_path = upload["url"]
                cdoc.file_size = upload.get("size")
                cdoc.updated_at = datetime.utcnow()
                db.add(cdoc)
                db.commit()
                summary["migrated"]["contractor_documents"] += 1
            except Exception as e:
                db.rollback()
                logger.error(f"Error migrando ContractorDocument {cdoc.id}: {e}")
                summary["errors"].append({"type": "contractor_documents", "id": cdoc.id, "error": str(e)})
        if cq:
            summary["last_ids"]["contractor_documents"] = cq[-1].id

    # Occupational exams PDF
    if "occupational_exams" in types:
        oq = (
            db.query(OccupationalExam)
            .filter(
                OccupationalExam.id > start_after_id,
                OccupationalExam.pdf_file_path != None,
                firebase_url_clause(OccupationalExam.pdf_file_path),
            )
            .order_by(OccupationalExam.id.asc())
            .limit(limit)
            .all()
        )
        for exam in oq:
            summary["processed"]["occupational_exams"] += 1
            if not is_firebase_url(exam.pdf_file_path):
                summary["skipped"]["occupational_exams"] += 1
                continue
            try:
                content = await storage_manager.download_file(exam.pdf_file_path, storage_type=None)
                if not content:
                    summary["errors"].append({"type": "occupational_exams", "id": exam.id, "error": "No se pudo descargar"})
                    continue
                filename = safe_filename_from_url(exam.pdf_file_path, f"exam_{exam.id}.pdf")
                folder = f"workers/{exam.worker_id}/exams"
                if dry_run:
                    summary["migrated"]["occupational_exams"] += 1
                    continue
                upload = await storage_manager.upload_bytes(content, filename, folder, "application/pdf")
                if not upload or not upload.get("url"):
                    summary["errors"].append({"type": "occupational_exams", "id": exam.id, "error": "Upload falló"})
                    continue
                exam.pdf_file_path = upload["url"]
                exam.updated_at = datetime.utcnow()
                db.add(exam)
                db.commit()
                summary["migrated"]["occupational_exams"] += 1
            except Exception as e:
                db.rollback()
                logger.error(f"Error migrando OccupationalExam {exam.id}: {e}")
                summary["errors"].append({"type": "occupational_exams", "id": exam.id, "error": str(e)})
        if oq:
            summary["last_ids"]["occupational_exams"] = oq[-1].id

    if "course_materials" in types:
        mq = (
            db.query(CourseMaterial, CourseModule.course_id)
            .join(CourseModule, CourseMaterial.module_id == CourseModule.id)
            .filter(
                CourseMaterial.id > start_after_id,
                CourseMaterial.file_url != None,
                or_(
                    firebase_url_clause(CourseMaterial.file_url),
                    s3_url_clause(CourseMaterial.file_url),
                ),
            )
            .order_by(CourseMaterial.id.asc())
            .limit(limit)
            .all()
        )
        for material, course_id in mq:
            summary["processed"]["course_materials"] += 1
            if not is_firebase_url(material.file_url) and not is_s3_url(material.file_url):
                summary["skipped"]["course_materials"] += 1
                continue
            try:
                if is_firebase_url(material.file_url):
                    content = await storage_manager.download_file(material.file_url, storage_type=None)
                else:
                    file_key = material.file_url.split('.com/')[-1]
                    signed_url = s3_service.get_file_url(file_key, expiration=3600)
                    async with httpx.AsyncClient() as client:
                        resp = await client.get(signed_url)
                        resp.raise_for_status()
                        content = resp.content
                if not content:
                    summary["errors"].append({"type": "course_materials", "id": material.id, "error": "No se pudo descargar"})
                    continue
                filename = safe_filename_from_url(material.file_url, f"material_{material.id}")
                folder = f"courses/{course_id}/materials"
                if dry_run:
                    summary["migrated"]["course_materials"] += 1
                    continue
                upload = await storage_manager.upload_bytes(content, filename, folder, "application/octet-stream")
                if not upload or not upload.get("url"):
                    summary["errors"].append({"type": "course_materials", "id": material.id, "error": "Upload falló"})
                    continue
                material.file_url = upload["url"]
                material.updated_at = datetime.utcnow()
                db.add(material)
                db.commit()
                summary["migrated"]["course_materials"] += 1
            except Exception as e:
                db.rollback()
                logger.error(f"Error migrando CourseMaterial {material.id}: {e}")
                summary["errors"].append({"type": "course_materials", "id": material.id, "error": str(e)})
        if mq:
            summary["last_ids"]["course_materials"] = mq[-1][0].id

    if "certificates" in types:
        certs = (
            db.query(Certificate)
            .filter(
                Certificate.id > start_after_id,
                Certificate.file_path != None,
                or_(
                    firebase_url_clause(Certificate.file_path),
                    s3_url_clause(Certificate.file_path),
                ),
            )
            .order_by(Certificate.id.asc())
            .limit(limit)
            .all()
        )
        for cert in certs:
            summary["processed"]["certificates"] += 1
            if not is_firebase_url(cert.file_path) and not is_s3_url(cert.file_path):
                summary["skipped"]["certificates"] += 1
                continue
            try:
                if is_firebase_url(cert.file_path):
                    content = await storage_manager.download_file(cert.file_path, storage_type=None)
                else:
                    file_key = cert.file_path.split('.com/')[-1]
                    signed_url = s3_service.get_file_url(file_key, expiration=3600)
                    async with httpx.AsyncClient() as client:
                        resp = await client.get(signed_url)
                        resp.raise_for_status()
                        content = resp.content
                if not content:
                    summary["errors"].append({"type": "certificates", "id": cert.id, "error": "No se pudo descargar"})
                    continue
                filename = safe_filename_from_url(cert.file_path, f"{cert.certificate_number}.pdf")
                folder = f"certificates/{cert.user_id}"
                if dry_run:
                    summary["migrated"]["certificates"] += 1
                    continue
                upload = await storage_manager.upload_bytes(content, filename, folder, "application/pdf")
                if not upload or not upload.get("url"):
                    summary["errors"].append({"type": "certificates", "id": cert.id, "error": "Upload falló"})
                    continue
                cert.file_path = upload["url"]
                cert.updated_at = datetime.utcnow()
                db.add(cert)
                db.commit()
                summary["migrated"]["certificates"] += 1
            except Exception as e:
                db.rollback()
                logger.error(f"Error migrando Certificate {cert.id}: {e}")
                summary["errors"].append({"type": "certificates", "id": cert.id, "error": str(e)})
        if certs:
            summary["last_ids"]["certificates"] = certs[-1].id

    if "committee_documents" in types:
        docs = (
            db.query(CommitteeDocument)
            .filter(
                CommitteeDocument.id > start_after_id,
                or_(
                    firebase_url_clause(CommitteeDocument.file_path),
                    s3_url_clause(CommitteeDocument.file_path),
                ),
            )
            .order_by(CommitteeDocument.id.asc())
            .limit(limit)
            .all()
        )
        for doc in docs:
            summary["processed"]["committee_documents"] += 1
            if not is_firebase_url(doc.file_path) and not is_s3_url(doc.file_path):
                summary["skipped"]["committee_documents"] += 1
                continue
            try:
                if is_firebase_url(doc.file_path):
                    content = await storage_manager.download_file(doc.file_path, storage_type=None)
                else:
                    file_key = doc.file_path.split('.com/')[-1]
                    signed_url = s3_service.get_file_url(file_key, expiration=3600)
                    async with httpx.AsyncClient() as client:
                        resp = await client.get(signed_url)
                        resp.raise_for_status()
                        content = resp.content
                if not content:
                    summary["errors"].append({"type": "committee_documents", "id": doc.id, "error": "No se pudo descargar"})
                    continue
                filename = safe_filename_from_url(doc.file_path, f"{doc.id}_{doc.file_name}")
                folder = f"committees/{doc.committee_id}/documents/{doc.document_type}"
                if dry_run:
                    summary["migrated"]["committee_documents"] += 1
                    continue
                upload = await storage_manager.upload_bytes(content, filename, folder, doc.mime_type or "application/octet-stream")
                if not upload or not upload.get("url"):
                    summary["errors"].append({"type": "committee_documents", "id": doc.id, "error": "Upload falló"})
                    continue
                doc.file_path = upload["url"]
                doc.file_size = upload.get("size")
                doc.updated_at = datetime.utcnow()
                db.add(doc)
                db.commit()
                summary["migrated"]["committee_documents"] += 1
            except Exception as e:
                db.rollback()
                logger.error(f"Error migrando CommitteeDocument {doc.id}: {e}")
                summary["errors"].append({"type": "committee_documents", "id": doc.id, "error": str(e)})
        if docs:
            summary["last_ids"]["committee_documents"] = docs[-1].id

    if "committee_urls" in types:
        async def migrate_url_field(model_name: str, record_id: int, url: str, folder: str, content_type: str = "application/octet-stream") -> Optional[str]:
            try:
                if is_firebase_url(url):
                    content = await storage_manager.download_file(url, storage_type=None)
                elif is_s3_url(url):
                    file_key = url.split('.com/')[-1]
                    signed_url = s3_service.get_file_url(file_key, expiration=3600)
                    async with httpx.AsyncClient() as client:
                        resp = await client.get(signed_url)
                        resp.raise_for_status()
                        content = resp.content
                else:
                    content = None
                if not content:
                    summary["errors"].append({"type": "committee_urls", "id": record_id, "model": model_name, "error": "No se pudo descargar"})
                    return None
                filename = safe_filename_from_url(url, f"{model_name}_{record_id}")
                if dry_run:
                    summary["migrated"]["committee_urls"] += 1
                    return url
                upload = await storage_manager.upload_bytes(content, filename, folder, content_type)
                if not upload or not upload.get("url"):
                    summary["errors"].append({"type": "committee_urls", "id": record_id, "model": model_name, "error": "Upload falló"})
                    return None
                summary["migrated"]["committee_urls"] += 1
                return upload["url"]
            except Exception as e:
                summary["errors"].append({"type": "committee_urls", "id": record_id, "model": model_name, "error": str(e)})
                return None

        committees = (
            db.query(Committee)
            .filter(
                Committee.id > start_after_id,
                Committee.regulations_document_url != None,
                or_(
                    firebase_url_clause(Committee.regulations_document_url),
                    s3_url_clause(Committee.regulations_document_url),
                ),
            )
            .order_by(Committee.id.asc())
            .limit(limit)
            .all()
        )
        for c in committees:
            summary["processed"]["committee_urls"] += 1
            new_url = await migrate_url_field("committee", c.id, c.regulations_document_url, f"committees/{c.id}/regulations")
            if not dry_run and new_url:
                c.regulations_document_url = new_url
                c.updated_at = datetime.utcnow()
                db.add(c)
                db.commit()

        members = (
            db.query(CommitteeMember)
            .filter(
                CommitteeMember.id > start_after_id,
                CommitteeMember.appointment_document_url != None,
                or_(
                    firebase_url_clause(CommitteeMember.appointment_document_url),
                    s3_url_clause(CommitteeMember.appointment_document_url),
                ),
            )
            .order_by(CommitteeMember.id.asc())
            .limit(limit)
            .all()
        )
        for m in members:
            summary["processed"]["committee_urls"] += 1
            new_url = await migrate_url_field(
                "committee_member",
                m.id,
                m.appointment_document_url,
                f"committees/{m.committee_id}/members/{m.id}/appointment",
            )
            if not dry_run and new_url:
                m.appointment_document_url = new_url
                m.updated_at = datetime.utcnow()
                db.add(m)
                db.commit()

        meetings = (
            db.query(CommitteeMeeting)
            .filter(
                CommitteeMeeting.id > start_after_id,
                CommitteeMeeting.minutes_document_url != None,
                or_(
                    firebase_url_clause(CommitteeMeeting.minutes_document_url),
                    s3_url_clause(CommitteeMeeting.minutes_document_url),
                ),
            )
            .order_by(CommitteeMeeting.id.asc())
            .limit(limit)
            .all()
        )
        for mtg in meetings:
            summary["processed"]["committee_urls"] += 1
            new_url = await migrate_url_field(
                "committee_meeting",
                mtg.id,
                mtg.minutes_document_url,
                f"committees/{mtg.committee_id}/meetings/{mtg.id}/minutes",
            )
            if not dry_run and new_url:
                mtg.minutes_document_url = new_url
                mtg.updated_at = datetime.utcnow()
                db.add(mtg)
                db.commit()

        activities = (
            db.query(CommitteeActivity)
            .filter(
                CommitteeActivity.id > start_after_id,
                CommitteeActivity.supporting_document_url != None,
                firebase_url_clause(CommitteeActivity.supporting_document_url),
            )
            .order_by(CommitteeActivity.id.asc())
            .limit(limit)
            .all()
        )
        for act in activities:
            summary["processed"]["committee_urls"] += 1
            new_url = await migrate_url_field(
                "committee_activity",
                act.id,
                act.supporting_document_url,
                f"committees/{act.committee_id}/activities/{act.id}/support",
            )
            if not dry_run and new_url:
                act.supporting_document_url = new_url
                act.updated_at = datetime.utcnow()
                db.add(act)
                db.commit()

        last_id_candidates = []
        if committees:
            last_id_candidates.append(committees[-1].id)
        if members:
            last_id_candidates.append(members[-1].id)
        if meetings:
            last_id_candidates.append(meetings[-1].id)
        if activities:
            last_id_candidates.append(activities[-1].id)
        if last_id_candidates:
            summary["last_ids"]["committee_urls"] = max(last_id_candidates)

    return summary


@router.get("/migrate-storage/firebase-to-contabo/diagnostics")
async def migrate_storage_diagnostics(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin)
):
    counts = {
        "worker_documents": db.query(WorkerDocument).filter(firebase_url_clause(WorkerDocument.file_url)).count(),
        "contractor_documents": db.query(ContractorDocument).filter(
            ContractorDocument.file_path != None,
            firebase_url_clause(ContractorDocument.file_path)
        ).count(),
        "occupational_exams": db.query(OccupationalExam).filter(
            OccupationalExam.pdf_file_path != None,
            firebase_url_clause(OccupationalExam.pdf_file_path)
        ).count(),
        "course_materials": db.query(CourseMaterial).filter(
            CourseMaterial.file_url != None,
            firebase_url_clause(CourseMaterial.file_url)
        ).count(),
        "certificates": db.query(Certificate).filter(
            Certificate.file_path != None,
            firebase_url_clause(Certificate.file_path)
        ).count(),
        "committee_documents": db.query(CommitteeDocument).filter(
            firebase_url_clause(CommitteeDocument.file_path)
        ).count(),
        "committee_urls": (
            db.query(Committee).filter(
                Committee.regulations_document_url != None,
                firebase_url_clause(Committee.regulations_document_url)
            ).count()
            + db.query(CommitteeMember).filter(
                CommitteeMember.appointment_document_url != None,
                firebase_url_clause(CommitteeMember.appointment_document_url)
            ).count()
            + db.query(CommitteeMeeting).filter(
                CommitteeMeeting.minutes_document_url != None,
                firebase_url_clause(CommitteeMeeting.minutes_document_url)
            ).count()
            + db.query(CommitteeActivity).filter(
                CommitteeActivity.supporting_document_url != None,
                firebase_url_clause(CommitteeActivity.supporting_document_url)
            ).count()
        ),
    }
    return {"firebase_candidates": counts, "use_contabo_storage": settings.use_contabo_storage}


@router.post("/", response_model=AdminConfigSchema, status_code=status.HTTP_201_CREATED)
async def create_config(
    config: AdminConfigCreate,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """Create a new configuration"""
    # Check if configuration with same category and display_name already exists
    existing = db.query(AdminConfig).filter(
        and_(
            AdminConfig.category == config.category,
            AdminConfig.display_name == config.display_name
        )
    ).first()
    
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Configuration with category '{config.category}' and display name '{config.display_name}' already exists"
        )
    
    db_config = AdminConfig(**config.dict())
    db.add(db_config)
    db.commit()
    db.refresh(db_config)
    
    return db_config


@router.put("/{config_id}", response_model=AdminConfigSchema)
async def update_config(
    config_id: int,
    config_update: AdminConfigUpdate,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """Update an existing configuration"""
    db_config = db.query(AdminConfig).filter(AdminConfig.id == config_id).first()
    
    if not db_config:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Configuration not found"
        )
    
    # Check for duplicate display_name in same category if display_name is being updated
    if config_update.display_name and config_update.display_name != db_config.display_name:
        existing = db.query(AdminConfig).filter(
            and_(
                AdminConfig.category == db_config.category,
                AdminConfig.display_name == config_update.display_name,
                AdminConfig.id != config_id
            )
        ).first()
        
        if existing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Configuration with category '{db_config.category}' and display name '{config_update.display_name}' already exists"
            )
    
    # Update fields
    update_data = config_update.dict(exclude_unset=True)
    for field, value in update_data.items():
        setattr(db_config, field, value)
    
    db.commit()
    db.refresh(db_config)
    
    return db_config


@router.delete("/{config_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_config(
    config_id: int,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """Delete a configuration"""
    db_config = db.query(AdminConfig).filter(AdminConfig.id == config_id).first()
    
    if not db_config:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Configuration not found"
        )
    
    db.delete(db_config)
    db.commit()
    
    return None


# Endpoints para Seguridad Social
@router.get("/seguridad-social{trailing_slash:path}", response_model=List[SeguridadSocialSchema])
def get_seguridad_social(
    trailing_slash: str = "",
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    is_active: Optional[bool] = Query(None, description="Filtrar por estado activo"),
    tipo: Optional[str] = Query(None, description="Filtrar por tipo (eps, afp, arl)"),
    search: Optional[str] = Query(None, description="Buscar por nombre"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Obtener lista de entidades de seguridad social"""
    query = db.query(SeguridadSocial)
    
    if is_active is not None:
        query = query.filter(SeguridadSocial.is_active == is_active)
    
    if tipo:
        query = query.filter(SeguridadSocial.tipo == tipo)
    
    if search:
        query = query.filter(SeguridadSocial.nombre.ilike(f"%{search}%"))
    
    return query.offset(skip).limit(limit).all()


@router.get("/seguridad-social/active{trailing_slash:path}", response_model=List[SeguridadSocialSchema])
def get_active_seguridad_social(
    trailing_slash: str = "",
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Obtener entidades de seguridad social activas"""
    return db.query(SeguridadSocial).filter(SeguridadSocial.is_active == True).all()


@router.get("/seguridad-social/tipo/{tipo}{trailing_slash:path}", response_model=List[SeguridadSocialSchema])
def get_seguridad_social_by_tipo(
    tipo: str,
    trailing_slash: str = "",
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Obtener entidades de seguridad social activas por tipo (eps, afp, arl)"""
    return db.query(SeguridadSocial).filter(
        and_(
            SeguridadSocial.tipo == tipo,
            SeguridadSocial.is_active == True
        )
    ).all()


@router.get("/seguridad-social/{seguridad_social_id}{trailing_slash:path}", response_model=SeguridadSocialSchema)
def get_seguridad_social_by_id(
    seguridad_social_id: int,
    trailing_slash: str = "",
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Obtener una entidad de seguridad social por ID"""
    seguridad_social = db.query(SeguridadSocial).filter(SeguridadSocial.id == seguridad_social_id).first()
    if not seguridad_social:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Entidad de seguridad social no encontrada"
        )
    return seguridad_social


@router.post("/seguridad-social{trailing_slash:path}", response_model=SeguridadSocialSchema, status_code=status.HTTP_201_CREATED)
def create_seguridad_social(
    seguridad_social_data: SeguridadSocialCreate,
    trailing_slash: str = "",
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin)
):
    """Crear nueva entidad de seguridad social"""
    # Verificar si ya existe una entidad con el mismo nombre y tipo
    existing = db.query(SeguridadSocial).filter(
        and_(
            SeguridadSocial.nombre == seguridad_social_data.nombre,
            SeguridadSocial.tipo == seguridad_social_data.tipo
        )
    ).first()
    
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Ya existe una entidad {seguridad_social_data.tipo.upper()} con el nombre '{seguridad_social_data.nombre}'"
        )
    
    seguridad_social = SeguridadSocial(**seguridad_social_data.dict())
    db.add(seguridad_social)
    db.commit()
    db.refresh(seguridad_social)
    return seguridad_social


@router.put("/seguridad-social/{seguridad_social_id}{trailing_slash:path}", response_model=SeguridadSocialSchema)
def update_seguridad_social(
    seguridad_social_id: int,
    seguridad_social_data: SeguridadSocialUpdate,
    trailing_slash: str = "",
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin)
):
    """Actualizar entidad de seguridad social"""
    seguridad_social = db.query(SeguridadSocial).filter(SeguridadSocial.id == seguridad_social_id).first()
    if not seguridad_social:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Entidad de seguridad social no encontrada"
        )
    
    # Verificar duplicados si se está actualizando el nombre
    if seguridad_social_data.nombre and seguridad_social_data.nombre != seguridad_social.nombre:
        existing = db.query(SeguridadSocial).filter(
            and_(
                SeguridadSocial.nombre == seguridad_social_data.nombre,
                SeguridadSocial.tipo == seguridad_social.tipo,
                SeguridadSocial.id != seguridad_social_id
            )
        ).first()
        
        if existing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Ya existe una entidad {seguridad_social.tipo.upper()} con el nombre '{seguridad_social_data.nombre}'"
            )
    
    # Actualizar campos
    update_data = seguridad_social_data.dict(exclude_unset=True)
    for field, value in update_data.items():
        setattr(seguridad_social, field, value)
    
    db.commit()
    db.refresh(seguridad_social)
    return seguridad_social


@router.delete("/seguridad-social/{seguridad_social_id}{trailing_slash:path}", status_code=status.HTTP_204_NO_CONTENT)
def delete_seguridad_social(
    seguridad_social_id: int,
    trailing_slash: str = "",
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin)
):
    """Eliminar entidad de seguridad social"""
    seguridad_social = db.query(SeguridadSocial).filter(SeguridadSocial.id == seguridad_social_id).first()
    if not seguridad_social:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Entidad de seguridad social no encontrada"
        )
    
    db.delete(seguridad_social)
    db.commit()
    return None


# Endpoints específicos para cargos bajo /admin/config/cargos
@router.get("/cargos{trailing_slash:path}", response_model=List[CargoSchema])
def get_cargos(
    trailing_slash: str = "",
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    activo: Optional[bool] = Query(None, description="Filtrar por estado activo"),
    search: Optional[str] = Query(None, description="Buscar por nombre de cargo"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Obtener lista de cargos"""
    query = db.query(Cargo)
    
    # Filtros
    if activo is not None:
        query = query.filter(Cargo.activo == activo)
    
    if search:
        query = query.filter(Cargo.nombre_cargo.ilike(f"%{search}%"))
    
    # Ordenar por nombre
    query = query.order_by(Cargo.nombre_cargo)
    
    # Paginación
    cargos = query.offset(skip).limit(limit).all()
    
    return cargos


@router.get("/cargos/active", response_model=List[CargoSchema])
def get_active_cargos(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Obtener solo cargos activos"""
    cargos = db.query(Cargo).filter(Cargo.activo == True).order_by(Cargo.nombre_cargo).all()
    return cargos


@router.get("/cargos/{cargo_id}", response_model=CargoSchema)
def get_cargo(
    cargo_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Obtener un cargo específico"""
    cargo = db.query(Cargo).filter(Cargo.id == cargo_id).first()
    if not cargo:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Cargo no encontrado"
        )
    return cargo


@router.post("/cargos{trailing_slash:path}", response_model=CargoSchema, status_code=status.HTTP_201_CREATED)
def create_cargo(
    cargo_data: CargoCreate,
    trailing_slash: str = "",
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin)
):
    """Crear un nuevo cargo"""
    # Verificar que no exista un cargo con el mismo nombre
    existing_cargo = db.query(Cargo).filter(Cargo.nombre_cargo == cargo_data.nombre_cargo).first()
    if existing_cargo:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Ya existe un cargo con este nombre"
        )
    
    # Crear el cargo
    cargo = Cargo(**cargo_data.model_dump())
    db.add(cargo)
    db.commit()
    db.refresh(cargo)
    
    return cargo


@router.put("/cargos/{cargo_id}{trailing_slash:path}", response_model=CargoSchema)
def update_cargo(
    cargo_id: int,
    cargo_data: CargoUpdate,
    trailing_slash: str = "",
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin)
):
    """Actualizar un cargo existente"""
    cargo = db.query(Cargo).filter(Cargo.id == cargo_id).first()
    if not cargo:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Cargo no encontrado"
        )
    
    # Verificar nombre único si se está actualizando
    if cargo_data.nombre_cargo and cargo_data.nombre_cargo != cargo.nombre_cargo:
        existing_cargo = db.query(Cargo).filter(
            and_(
                Cargo.nombre_cargo == cargo_data.nombre_cargo,
                Cargo.id != cargo_id
            )
        ).first()
        if existing_cargo:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Ya existe un cargo con este nombre"
            )
    
    # Actualizar campos
    update_data = cargo_data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(cargo, field, value)
    
    db.commit()
    db.refresh(cargo)
    
    return cargo


@router.delete("/cargos/{cargo_id}{trailing_slash:path}", status_code=status.HTTP_204_NO_CONTENT)
def delete_cargo(
    cargo_id: int,
    trailing_slash: str = "",
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin)
):
    """Eliminar un cargo"""
    cargo = db.query(Cargo).filter(Cargo.id == cargo_id).first()
    if not cargo:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Cargo no encontrado"
        )
    
    # TODO: Verificar si el cargo está siendo usado por trabajadores
    # antes de permitir la eliminación
    
    db.delete(cargo)
    db.commit()
    
    return None


@router.post("/seed", status_code=status.HTTP_201_CREATED)
async def seed_initial_data(
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """Seed initial configuration data"""
    
    # Initial EPS data
    eps_data = [
        {"category": "eps", "display_name": "EPS SURA"},
        {"category": "eps", "display_name": "EPS Sanitas"},
        {"category": "eps", "display_name": "Nueva EPS"},
        {"category": "eps", "display_name": "Compensar EPS"},
        {"category": "eps", "display_name": "Famisanar EPS"},
        {"category": "eps", "display_name": "Salud Total EPS"},
        {"category": "eps", "display_name": "Coomeva EPS"},
        {"category": "eps", "display_name": "Medimás EPS"},
    ]
    
    # Initial AFP data
    afp_data = [
        {"category": "afp", "display_name": "Porvenir"},
        {"category": "afp", "display_name": "Protección"},
        {"category": "afp", "display_name": "Old Mutual"},
        {"category": "afp", "display_name": "Colfondos"},
        {"category": "afp", "display_name": "Colpensiones"},
    ]
    
    # Initial ARL data
    arl_data = [
        {"category": "arl", "display_name": "ARL SURA"},
        {"category": "arl", "display_name": "Positiva Compañía de Seguros"},
        {"category": "arl", "display_name": "Colmena Seguros"},
        {"category": "arl", "display_name": "Liberty Seguros"},
        {"category": "arl", "display_name": "Mapfre Seguros"},
        {"category": "arl", "display_name": "Seguros Bolívar"},
        {"category": "arl", "display_name": "La Equidad Seguros"},
    ]
    
    all_data = eps_data + afp_data + arl_data
    created_count = 0
    
    for item in all_data:
        # Check if already exists
        existing = db.query(AdminConfig).filter(
            and_(
                AdminConfig.category == item["category"],
                AdminConfig.display_name == item["display_name"]
            )
        ).first()
        
        if not existing:
            db_config = AdminConfig(**item)
            db.add(db_config)
            created_count += 1
    
    db.commit()
    
    return {"message": f"Seeded {created_count} configuration items"}


# Programas endpoints
@router.get("/programas{trailing_slash:path}", response_model=List[ProgramasSchema])
async def get_all_programas(
    trailing_slash: str = "",
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """Get all programs"""
    programas = db.query(Programas).order_by(Programas.nombre_programa).all()
    return programas


@router.get("/programas/active", response_model=List[ProgramasSchema])
async def get_active_programas(
    db: Session = Depends(get_db)
):
    """Get all active programs (public endpoint)"""
    programas = db.query(Programas).filter(
        Programas.activo == True
    ).order_by(Programas.nombre_programa).all()
    return programas


@router.get("/programas/{programa_id}", response_model=ProgramasSchema)
async def get_programa(
    programa_id: int,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """Get a specific program by ID"""
    programa = db.query(Programas).filter(Programas.id == programa_id).first()
    if not programa:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Programa no encontrado"
        )
    return programa


@router.post("/programas{trailing_slash:path}", response_model=ProgramasSchema, status_code=status.HTTP_201_CREATED)
async def create_programa(
    programa: ProgramasCreate,
    trailing_slash: str = "",
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """Create a new program"""
    # Check if program name already exists
    existing = db.query(Programas).filter(
        Programas.nombre_programa == programa.nombre_programa
    ).first()
    
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Ya existe un programa con este nombre"
        )
    
    db_programa = Programas(**programa.dict())
    db.add(db_programa)
    db.commit()
    db.refresh(db_programa)
    
    return db_programa


@router.put("/programas/{programa_id}{trailing_slash:path}", response_model=ProgramasSchema)
async def update_programa(
    programa_id: int,
    programa_update: ProgramasUpdate,
    trailing_slash: str = "",
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """Update a program"""
    db_programa = db.query(Programas).filter(Programas.id == programa_id).first()
    
    if not db_programa:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Programa no encontrado"
        )
    
    # Check if new name already exists (if name is being updated)
    if programa_update.nombre_programa and programa_update.nombre_programa != db_programa.nombre_programa:
        existing = db.query(Programas).filter(
            and_(
                Programas.nombre_programa == programa_update.nombre_programa,
                Programas.id != programa_id
            )
        ).first()
        
        if existing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Ya existe un programa con este nombre"
            )
    
    # Update fields
    update_data = programa_update.dict(exclude_unset=True)
    for field, value in update_data.items():
        setattr(db_programa, field, value)
    
    db.commit()
    db.refresh(db_programa)
    
    return db_programa


@router.delete("/programas/{programa_id}{trailing_slash:path}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_programa(
    programa_id: int,
    trailing_slash: str = "",
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """Delete a program"""
    db_programa = db.query(Programas).filter(Programas.id == programa_id).first()
    
    if not db_programa:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Programa no encontrado"
        )
    
    db.delete(db_programa)
    db.commit()
    
    return None
