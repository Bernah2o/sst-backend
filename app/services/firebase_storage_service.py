import os
import json
from typing import Optional, BinaryIO
from firebase_admin import credentials, initialize_app, storage
import firebase_admin
from app.config import settings
import logging

logger = logging.getLogger(__name__)

class FirebaseStorageService:
    def __init__(self):
        self._bucket = None
        self._initialized = False
        
    def _initialize_firebase(self):
        """Inicializa Firebase Admin SDK si no está ya inicializado"""
        if self._initialized:
            return
            
        try:
            # Verificar si Firebase ya está inicializado
            if not firebase_admin._apps:
                # Configurar credenciales
                credentials_path = settings.firebase_credentials_path
                logger.info(f"Intentando usar archivo de credenciales: {credentials_path}")
                
                if credentials_path and os.path.exists(credentials_path):
                    # Usar archivo de credenciales para desarrollo local
                    logger.info(f"Usando archivo de credenciales: {credentials_path}")
                    cred = credentials.Certificate(credentials_path)
                    initialize_app(cred, {
                        'storageBucket': settings.firebase_storage_bucket
                    })
                else:
                    # Usar credenciales por defecto (para producción en Google Cloud)
                    logger.warning("Archivo de credenciales no encontrado, usando credenciales por defecto")
                    cred = credentials.ApplicationDefault()
                    initialize_app(cred, {
                        'storageBucket': settings.firebase_storage_bucket
                    })
            else:
                logger.info("Firebase ya está inicializado")
            
            # Obtener referencia al bucket
            self._bucket = storage.bucket()
            self._initialized = True
            logger.info(f"Firebase Storage inicializado correctamente con bucket: {settings.firebase_storage_bucket}")
            
        except Exception as e:
            logger.error(f"Error al inicializar Firebase Storage: {str(e)}")
            raise
    
    def upload_file(self, file_data: BinaryIO, destination_path: str, content_type: str = None) -> str:
        """Sube un archivo a Firebase Storage"""
        try:
            self._initialize_firebase()
            
            # Crear blob en el bucket
            blob = self._bucket.blob(destination_path)
            
            # Subir archivo
            if content_type:
                blob.upload_from_file(file_data, content_type=content_type)
            else:
                blob.upload_from_file(file_data)
            
            # Hacer el archivo público (opcional)
            blob.make_public()
            
            # Retornar URL pública
            public_url = blob.public_url
            logger.info(f"Archivo subido exitosamente: {destination_path}")
            return public_url
            
        except Exception as e:
            logger.error(f"Error al subir archivo a Firebase Storage: {str(e)}")
            raise
    
    def upload_file_from_path(self, local_path: str, destination_path: str, content_type: str = None) -> str:
        """Sube un archivo desde una ruta local a Firebase Storage"""
        try:
            with open(local_path, 'rb') as file_data:
                return self.upload_file(file_data, destination_path, content_type)
        except Exception as e:
            logger.error(f"Error al subir archivo desde ruta local: {str(e)}")
            raise
    
    def download_file(self, source_path: str, destination_path: str) -> bool:
        """Descarga un archivo desde Firebase Storage"""
        try:
            self._initialize_firebase()
            
            blob = self._bucket.blob(source_path)
            blob.download_to_filename(destination_path)
            
            logger.info(f"Archivo descargado exitosamente: {source_path} -> {destination_path}")
            return True
            
        except Exception as e:
            logger.error(f"Error al descargar archivo desde Firebase Storage: {str(e)}")
            return False
    
    def download_file_as_bytes(self, source_path: str) -> bytes:
        """Descarga un archivo desde Firebase Storage como bytes"""
        try:
            self._initialize_firebase()
            
            blob = self._bucket.blob(source_path)
            return blob.download_as_bytes()
            
        except Exception as e:
            logger.error(f"Error al descargar archivo como bytes desde Firebase Storage: {str(e)}")
            raise
    
    def delete_file(self, file_path: str) -> bool:
        """Elimina un archivo de Firebase Storage"""
        try:
            self._initialize_firebase()
            
            blob = self._bucket.blob(file_path)
            blob.delete()
            
            logger.info(f"Archivo eliminado exitosamente: {file_path}")
            return True
            
        except Exception as e:
            logger.error(f"Error al eliminar archivo de Firebase Storage: {str(e)}")
            return False
    
    def file_exists(self, file_path: str) -> bool:
        """Verifica si un archivo existe en Firebase Storage"""
        try:
            self._initialize_firebase()
            
            blob = self._bucket.blob(file_path)
            return blob.exists()
            
        except Exception as e:
            logger.error(f"Error al verificar existencia de archivo: {str(e)}")
            return False
    
    def get_public_url(self, file_path: str) -> Optional[str]:
        """Obtiene la URL pública de un archivo"""
        try:
            self._initialize_firebase()
            
            blob = self._bucket.blob(file_path)
            if blob.exists():
                return blob.public_url
            return None
            
        except Exception as e:
            logger.error(f"Error al obtener URL pública: {str(e)}")
            return None
    
    def list_files(self, prefix: str = None) -> list:
        """Lista archivos en Firebase Storage con un prefijo opcional"""
        try:
            self._initialize_firebase()
            
            blobs = self._bucket.list_blobs(prefix=prefix)
            return [blob.name for blob in blobs]
            
        except Exception as e:
            logger.error(f"Error al listar archivos: {str(e)}")
            return []

# Instancia global del servicio
firebase_storage_service = FirebaseStorageService()