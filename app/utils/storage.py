import os
import shutil
from typing import Optional, BinaryIO
from fastapi import UploadFile
from app.config import settings
from app.services.firebase_storage_service import firebase_storage_service
from app.services.s3_storage import contabo_service
import logging
import uuid
from pathlib import Path
from urllib.parse import urlparse, unquote

logger = logging.getLogger(__name__)

class StorageManager:
    """Gestor de almacenamiento que maneja tanto Firebase Storage como almacenamiento local"""
    
    def __init__(self):
        self.use_contabo = settings.use_contabo_storage
        self.use_firebase = settings.use_firebase_storage and not self.use_contabo
        
        # Crear directorios locales si no existen
        if not self.use_firebase and not self.use_contabo:
            self._ensure_local_directories()
    
    def _ensure_local_directories(self):
        """Asegura que los directorios locales existan"""
        static_dir = Path("static")
        uploads_dir = Path(settings.upload_dir)
        
        static_dir.mkdir(exist_ok=True)
        uploads_dir.mkdir(exist_ok=True)
        
        logger.info("Directorios locales creados/verificados")
    
    def _get_file_extension(self, filename: str) -> str:
        """Obtiene la extensión del archivo"""
        return Path(filename).suffix.lower()
    
    def _generate_unique_filename(self, original_filename: str) -> str:
        """Genera un nombre único para el archivo"""
        file_extension = self._get_file_extension(original_filename)
        unique_id = str(uuid.uuid4())
        return f"{unique_id}{file_extension}"
    
    async def upload_file(self, file: UploadFile, folder: str = "uploads", keep_original_name: bool = False) -> dict:
        """Sube un archivo usando Firebase Storage o almacenamiento local"""
        try:
            # Generar nombre del archivo
            if keep_original_name:
                filename = file.filename
            else:
                filename = self._generate_unique_filename(file.filename)
            
            # Leer contenido del archivo
            file_content = await file.read()
            
            if self.use_contabo:
                return await self._upload_to_contabo(file_content, filename, folder, file.content_type)
            if self.use_firebase:
                return await self._upload_to_firebase(file_content, filename, folder, file.content_type)
            else:
                return await self._upload_to_local(file_content, filename, folder)
                
        except Exception as e:
            logger.error(f"Error al subir archivo: {str(e)}")
            raise
    
    async def _upload_to_firebase(self, file_content: bytes, filename: str, folder: str, content_type: str) -> dict:
        """Sube archivo a Firebase Storage"""
        try:
            # Determinar la ruta en Firebase
            if folder == "static":
                firebase_path = f"{settings.firebase_static_path}/{filename}"
            else:
                firebase_path = f"{settings.firebase_uploads_path}/{filename}"
            
            # Subir archivo
            from io import BytesIO
            file_stream = BytesIO(file_content)
            public_url = firebase_storage_service.upload_file(file_stream, firebase_path, content_type)
            
            return {
                "filename": filename,
                "url": public_url,
                "path": firebase_path,
                "storage_type": "firebase",
                "size": len(file_content)
            }
            
        except Exception as e:
            logger.error(f"Error al subir a Firebase Storage: {str(e)}")
            raise

    async def _upload_to_contabo(self, file_content: bytes, filename: str, folder: str, content_type: str) -> dict:
        if not contabo_service:
            raise ValueError("Contabo Storage no está configurado")
        storage_path = f"{folder.strip('/')}/{filename}" if folder else filename
        public_url = contabo_service.upload_bytes(file_content, storage_path, content_type or "application/octet-stream")
        return {
            "filename": filename,
            "url": public_url,
            "path": storage_path,
            "storage_type": "contabo",
            "size": len(file_content)
        }
    
    async def _upload_to_local(self, file_content: bytes, filename: str, folder: str) -> dict:
        """Sube archivo al almacenamiento local"""
        try:
            # Determinar directorio local
            if folder == "static":
                local_dir = Path("static")
            else:
                local_dir = Path(settings.upload_dir)
            
            # Crear directorio si no existe
            local_dir.mkdir(exist_ok=True)
            
            # Ruta completa del archivo
            file_path = local_dir / filename
            
            # Escribir archivo
            with open(file_path, "wb") as f:
                f.write(file_content)
            
            # URL local (relativa)
            if folder == "static":
                url = f"/static/{filename}"
            else:
                url = f"/uploads/{filename}"
            
            return {
                "filename": filename,
                "url": url,
                "path": str(file_path),
                "storage_type": "local",
                "size": len(file_content)
            }
            
        except Exception as e:
            logger.error(f"Error al subir a almacenamiento local: {str(e)}")
            raise

    async def upload_bytes(self, file_content: bytes, filename: str, folder: str = "uploads", content_type: str = "application/octet-stream") -> dict:
        try:
            if self.use_contabo:
                return await self._upload_to_contabo(file_content, filename, folder, content_type)
            if self.use_firebase:
                return await self._upload_to_firebase(file_content, filename, folder, content_type)
            return await self._upload_to_local(file_content, filename, folder)
        except Exception as e:
            logger.error(f"Error al subir bytes: {str(e)}")
            raise

    def _extract_firebase_path(self, file_url: str) -> Optional[str]:
        try:
            parsed = urlparse(file_url)
            if "firebasestorage.googleapis.com" in parsed.netloc:
                if "/o/" in parsed.path:
                    return unquote(parsed.path.split("/o/")[1])
            if "storage.googleapis.com" in parsed.netloc and settings.firebase_storage_bucket:
                path = parsed.path.lstrip("/")
                if path.startswith(f"{settings.firebase_storage_bucket}/"):
                    return path.split("/", 1)[1]
            if settings.firebase_storage_bucket and settings.firebase_storage_bucket in parsed.path:
                path = parsed.path.lstrip("/")
                if path.startswith(f"{settings.firebase_storage_bucket}/"):
                    return path.split("/", 1)[1]
            return None
        except Exception:
            return None

    def _extract_contabo_key(self, file_url: str) -> Optional[str]:
        try:
            if settings.contabo_public_base_url and file_url.startswith(settings.contabo_public_base_url.rstrip("/")):
                return file_url.replace(settings.contabo_public_base_url.rstrip("/") + "/", "", 1)
            if settings.contabo_endpoint_url and settings.contabo_bucket_name:
                prefix = f"{settings.contabo_endpoint_url.rstrip('/')}/{settings.contabo_bucket_name}/"
                if file_url.startswith(prefix):
                    return file_url.replace(prefix, "", 1)
            return None
        except Exception:
            return None

    def _resolve_storage_target(self, file_path: str, storage_type: Optional[str]) -> tuple[Optional[str], Optional[str]]:
        if not file_path:
            return storage_type, file_path
        if storage_type:
            return storage_type, file_path
        if file_path.startswith("http"):
            contabo_key = self._extract_contabo_key(file_path)
            if contabo_key:
                return "contabo", contabo_key
            firebase_key = self._extract_firebase_path(file_path)
            if firebase_key:
                return "firebase", firebase_key
        if file_path.startswith("/uploads") or file_path.startswith("/static"):
            return "local", file_path
        if self.use_contabo:
            return "contabo", file_path
        if self.use_firebase:
            return "firebase", file_path
        return "local", file_path
    
    async def delete_file(self, file_path: str, storage_type: str = None) -> bool:
        """Elimina un archivo"""
        try:
            resolved_type, resolved_path = self._resolve_storage_target(file_path, storage_type)
            if resolved_type == "contabo":
                return contabo_service.delete_file(resolved_path) if contabo_service else False
            if resolved_type == "firebase":
                return firebase_storage_service.delete_file(resolved_path)
            else:
                local_path = resolved_path
                if local_path.startswith("/uploads/"):
                    local_path = os.path.join(settings.upload_dir, local_path.replace("/uploads/", "", 1))
                if local_path.startswith("/static/"):
                    local_path = os.path.join("static", local_path.replace("/static/", "", 1))
                if os.path.exists(local_path):
                    os.remove(local_path)
                    logger.info(f"Archivo local eliminado: {local_path}")
                    return True
                return False
                
        except Exception as e:
            logger.error(f"Error al eliminar archivo: {str(e)}")
            return False
    
    async def file_exists(self, file_path: str, storage_type: str = None) -> bool:
        """Verifica si un archivo existe"""
        try:
            resolved_type, resolved_path = self._resolve_storage_target(file_path, storage_type)
            if resolved_type == "contabo":
                return contabo_service.file_exists(resolved_path) if contabo_service else False
            if resolved_type == "firebase":
                return firebase_storage_service.file_exists(resolved_path)
            else:
                local_path = resolved_path
                if local_path.startswith("/uploads/"):
                    local_path = os.path.join(settings.upload_dir, local_path.replace("/uploads/", "", 1))
                if local_path.startswith("/static/"):
                    local_path = os.path.join("static", local_path.replace("/static/", "", 1))
                return os.path.exists(local_path)
                
        except Exception as e:
            logger.error(f"Error al verificar existencia de archivo: {str(e)}")
            return False
    
    async def download_file(self, file_path: str, storage_type: str = None) -> Optional[bytes]:
        """Descarga un archivo y devuelve su contenido como bytes"""
        try:
            resolved_type, resolved_path = self._resolve_storage_target(file_path, storage_type)
            if resolved_type == "contabo":
                return contabo_service.download_file_as_bytes(resolved_path) if contabo_service else None
            if resolved_type == "firebase":
                return firebase_storage_service.download_file_as_bytes(resolved_path)
            else:
                local_path = resolved_path
                if local_path.startswith("/uploads/"):
                    local_path = os.path.join(settings.upload_dir, local_path.replace("/uploads/", "", 1))
                if local_path.startswith("/static/"):
                    local_path = os.path.join("static", local_path.replace("/static/", "", 1))
                if os.path.exists(local_path):
                    with open(local_path, 'rb') as f:
                        return f.read()
                return None
                
        except Exception as e:
            logger.error(f"Error al descargar archivo: {str(e)}")
            return None
    
    async def get_public_url(self, file_path: str, storage_type: str = None) -> Optional[str]:
        """Obtiene la URL pública de un archivo"""
        try:
            resolved_type, resolved_path = self._resolve_storage_target(file_path, storage_type)
            if resolved_type == "contabo":
                return contabo_service.get_public_url(resolved_path) if contabo_service else None
            if resolved_type == "firebase":
                return firebase_storage_service.get_public_url(resolved_path)
            else:
                # Para almacenamiento local, devolver una URL relativa
                return f"/static/{os.path.basename(resolved_path)}"
                
        except Exception as e:
            logger.error(f"Error al obtener URL pública: {str(e)}")
            return None
    
    def get_file_url(self, file_path: str, storage_type: str = None) -> Optional[str]:
        """Obtiene la URL de un archivo"""
        try:
            resolved_type, resolved_path = self._resolve_storage_target(file_path, storage_type)
            if resolved_type == "contabo":
                return contabo_service.get_public_url(resolved_path) if contabo_service else None
            if resolved_type == "firebase":
                return firebase_storage_service.get_public_url(resolved_path)
            else:
                # Para archivos locales, retornar URL relativa
                local_path = resolved_path
                if local_path.startswith(settings.upload_dir):
                    filename = os.path.basename(local_path)
                    return f"/uploads/{filename}"
                elif local_path.startswith("static"):
                    filename = os.path.basename(local_path)
                    return f"/static/{filename}"
                return local_path
                
        except Exception as e:
            logger.error(f"Error al obtener URL de archivo: {str(e)}")
            return None
    
    async def list_files(self, folder: str = "uploads", storage_type: str = None) -> list:
        """Lista archivos en una carpeta"""
        try:
            resolved_type, _ = self._resolve_storage_target("", storage_type)
            if resolved_type == "contabo":
                if not contabo_service:
                    return []
                prefix = f"{folder.strip('/')}/" if folder else ""
                return contabo_service.list_files(prefix)
            if resolved_type == "firebase":
                # Listar archivos de Firebase
                if folder == "static":
                    prefix = settings.firebase_static_path
                else:
                    prefix = settings.firebase_uploads_path
                return firebase_storage_service.list_files(prefix)
            else:
                # Listar archivos locales
                if folder == "static":
                    local_dir = Path("static")
                else:
                    local_dir = Path(settings.upload_dir)
                
                if local_dir.exists():
                    return [f.name for f in local_dir.iterdir() if f.is_file()]
                return []
                
        except Exception as e:
            logger.error(f"Error al listar archivos: {str(e)}")
            return []
    
    async def copy_local_to_firebase(self, local_path: str, firebase_path: str) -> bool:
        """Copia un archivo local a Firebase Storage"""
        try:
            if not os.path.exists(local_path):
                logger.error(f"Archivo local no existe: {local_path}")
                return False
            
            # Determinar content type
            import mimetypes
            content_type, _ = mimetypes.guess_type(local_path)
            
            # Subir a Firebase
            public_url = firebase_storage_service.upload_file_from_path(
                local_path, firebase_path, content_type
            )
            
            logger.info(f"Archivo copiado a Firebase: {local_path} -> {firebase_path}")
            return True
            
        except Exception as e:
            logger.error(f"Error al copiar archivo a Firebase: {str(e)}")
            return False

# Instancia global del gestor de almacenamiento
storage_manager = StorageManager()
