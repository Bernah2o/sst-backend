import os
import shutil
from typing import Optional, BinaryIO
from fastapi import UploadFile
from app.config import settings
from app.services.firebase_storage_service import firebase_storage_service
import logging
import uuid
from pathlib import Path

logger = logging.getLogger(__name__)

class StorageManager:
    """Gestor de almacenamiento que maneja tanto Firebase Storage como almacenamiento local"""
    
    def __init__(self):
        self.use_firebase = settings.use_firebase_storage
        
        # Crear directorios locales si no existen
        if not self.use_firebase:
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
    
    async def delete_file(self, file_path: str, storage_type: str = None) -> bool:
        """Elimina un archivo"""
        try:
            if storage_type == "firebase" or (storage_type is None and self.use_firebase):
                return firebase_storage_service.delete_file(file_path)
            else:
                if os.path.exists(file_path):
                    os.remove(file_path)
                    logger.info(f"Archivo local eliminado: {file_path}")
                    return True
                return False
                
        except Exception as e:
            logger.error(f"Error al eliminar archivo: {str(e)}")
            return False
    
    async def file_exists(self, file_path: str, storage_type: str = None) -> bool:
        """Verifica si un archivo existe"""
        try:
            if storage_type == "firebase" or (storage_type is None and self.use_firebase):
                return firebase_storage_service.file_exists(file_path)
            else:
                return os.path.exists(file_path)
                
        except Exception as e:
            logger.error(f"Error al verificar existencia de archivo: {str(e)}")
            return False
    
    async def download_file(self, file_path: str, storage_type: str = None) -> Optional[bytes]:
        """Descarga un archivo y devuelve su contenido como bytes"""
        try:
            if storage_type == "firebase" or (storage_type is None and self.use_firebase):
                return firebase_storage_service.download_file_as_bytes(file_path)
            else:
                if os.path.exists(file_path):
                    with open(file_path, 'rb') as f:
                        return f.read()
                return None
                
        except Exception as e:
            logger.error(f"Error al descargar archivo: {str(e)}")
            return None
    
    async def get_public_url(self, file_path: str, storage_type: str = None) -> Optional[str]:
        """Obtiene la URL pública de un archivo"""
        try:
            if storage_type == "firebase" or (storage_type is None and self.use_firebase):
                return firebase_storage_service.get_public_url(file_path)
            else:
                # Para almacenamiento local, devolver una URL relativa
                return f"/static/{os.path.basename(file_path)}"
                
        except Exception as e:
            logger.error(f"Error al obtener URL pública: {str(e)}")
            return None
    
    def get_file_url(self, file_path: str, storage_type: str = None) -> Optional[str]:
        """Obtiene la URL de un archivo"""
        try:
            if storage_type == "firebase" or (storage_type is None and self.use_firebase):
                return firebase_storage_service.get_public_url(file_path)
            else:
                # Para archivos locales, retornar URL relativa
                if file_path.startswith(settings.upload_dir):
                    filename = os.path.basename(file_path)
                    return f"/uploads/{filename}"
                elif file_path.startswith("static"):
                    filename = os.path.basename(file_path)
                    return f"/static/{filename}"
                return file_path
                
        except Exception as e:
            logger.error(f"Error al obtener URL de archivo: {str(e)}")
            return None
    
    async def list_files(self, folder: str = "uploads", storage_type: str = None) -> list:
        """Lista archivos en una carpeta"""
        try:
            if storage_type == "firebase" or (storage_type is None and self.use_firebase):
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