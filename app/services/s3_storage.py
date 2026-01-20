"""
Servicio de almacenamiento S3 para documentos de empleados y exámenes médicos.
"""

import os
import boto3
import logging
from typing import Optional, Dict, Any, BinaryIO
from datetime import datetime
from botocore.exceptions import ClientError, NoCredentialsError
from fastapi import UploadFile
import uuid
from pathlib import Path
from app.config import settings

# Configurar logging
logger = logging.getLogger(__name__)

class S3StorageService:
    """Servicio para manejar el almacenamiento de archivos en S3."""
    
    def __init__(self):
        """Inicializar el servicio S3 con las credenciales del entorno."""
        self.aws_access_key_id = os.getenv("AWS_ACCESS_KEY_ID")
        self.aws_secret_access_key = os.getenv("AWS_SECRET_ACCESS_KEY")
        self.bucket_name = os.getenv("S3_BUCKET_NAME")
        self.region = os.getenv("AWS_REGION")
        
        # Validar que todas las credenciales estén presentes
        if not all([self.aws_access_key_id, self.aws_secret_access_key, self.bucket_name, self.region]):
            missing_vars = []
            if not self.aws_access_key_id:
                missing_vars.append("AWS_ACCESS_KEY_ID")
            if not self.aws_secret_access_key:
                missing_vars.append("AWS_SECRET_ACCESS_KEY")
            if not self.bucket_name:
                missing_vars.append("S3_BUCKET_NAME")
            if not self.region:
                missing_vars.append("AWS_REGION")
            
            error_msg = f"Variables de entorno faltantes para S3: {', '.join(missing_vars)}"
            logger.error(error_msg)
            raise ValueError(error_msg)
        
        # Inicializar cliente S3
        try:
            self.s3_client = boto3.client(
                's3',
                aws_access_key_id=self.aws_access_key_id,
                aws_secret_access_key=self.aws_secret_access_key,
                region_name=self.region
            )
            logger.info("Cliente S3 inicializado correctamente")
        except Exception as e:
            logger.error(f"Error al inicializar cliente S3: {e}")
            raise
    
    def _generate_file_key(self, folder: str, worker_id: int, filename: str) -> str:
        """
        Generar una clave única para el archivo en S3.
        
        Args:
            folder: Carpeta donde se almacenará (documentos/examenes)
            worker_id: ID del trabajador
            filename: Nombre original del archivo
            
        Returns:
            Clave única para S3
        """
        # Obtener extensión del archivo
        file_extension = Path(filename).suffix
        
        # Generar nombre único
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        unique_id = str(uuid.uuid4())[:8]
        
        # Crear clave del archivo
        safe_filename = f"{timestamp}_{unique_id}{file_extension}"
        return f"{folder}/worker_{worker_id}/{safe_filename}"
    
    def _validate_file(self, file: UploadFile) -> bool:
        """
        Validar el archivo antes de subirlo.
        
        Args:
            file: Archivo a validar
            
        Returns:
            True si el archivo es válido
        """
        # Extensiones permitidas
        allowed_extensions = {'.pdf', '.doc', '.docx', '.jpg', '.jpeg', '.png', '.tiff', '.tif'}
        
        # Tamaño máximo (10MB)
        max_size = 10 * 1024 * 1024
        
        # Validar extensión
        file_extension = Path(file.filename).suffix.lower()
        if file_extension not in allowed_extensions:
            logger.warning(f"Extensión no permitida: {file_extension}")
            return False
        
        # Validar tamaño
        if file.size and file.size > max_size:
            logger.warning(f"Archivo demasiado grande: {file.size} bytes")
            return False
        
        return True
    
    async def upload_employee_document(
        self, 
        worker_id: int, 
        file: UploadFile, 
        document_type: str = "general"
    ) -> Dict[str, Any]:
        """
        Subir documento de empleado a S3.
        
        Args:
            worker_id: ID del trabajador
            file: Archivo a subir
            document_type: Tipo de documento (cedula, contrato, etc.)
            
        Returns:
            Diccionario con información del archivo subido
        """
        try:
            # Validar archivo
            if not self._validate_file(file):
                raise ValueError("Archivo no válido")
            
            # Generar clave del archivo
            folder = f"documentos/{document_type}"
            file_key = self._generate_file_key(folder, worker_id, file.filename)
            
            # Leer contenido del archivo
            file_content = await file.read()
            
            # Metadatos del archivo
            metadata = {
                'worker_id': str(worker_id),
                'document_type': document_type,
                'original_filename': file.filename,
                'upload_date': datetime.now().isoformat(),
                'content_type': file.content_type or 'application/octet-stream'
            }
            
            # Subir archivo a S3
            self.s3_client.put_object(
                Bucket=self.bucket_name,
                Key=file_key,
                Body=file_content,
                ContentType=file.content_type or 'application/octet-stream',
                Metadata=metadata
            )
            
            # Generar URL del archivo
            file_url = f"https://{self.bucket_name}.s3.amazonaws.com/{file_key}"
            
            logger.info(f"Documento subido exitosamente: {file_key}")
            
            return {
                "success": True,
                "file_key": file_key,
                "file_url": file_url,
                "original_filename": file.filename,
                "size": len(file_content),
                "content_type": file.content_type,
                "upload_date": datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error al subir documento de empleado: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    async def upload_medical_exam(
        self, 
        worker_id: int, 
        file: UploadFile, 
        exam_type: str = "ocupacional"
    ) -> Dict[str, Any]:
        """
        Subir examen médico a S3.
        
        Args:
            worker_id: ID del trabajador
            file: Archivo del examen médico
            exam_type: Tipo de examen (ocupacional, ingreso, egreso, etc.)
            
        Returns:
            Diccionario con información del archivo subido
        """
        try:
            # Validar archivo
            if not self._validate_file(file):
                raise ValueError("Archivo no válido")
            
            # Generar clave del archivo
            folder = f"examenes_medicos/{exam_type}"
            file_key = self._generate_file_key(folder, worker_id, file.filename)
            
            # Leer contenido del archivo
            file_content = await file.read()
            
            # Metadatos del archivo
            metadata = {
                'worker_id': str(worker_id),
                'exam_type': exam_type,
                'original_filename': file.filename,
                'upload_date': datetime.now().isoformat(),
                'content_type': file.content_type or 'application/octet-stream'
            }
            
            # Subir archivo a S3
            self.s3_client.put_object(
                Bucket=self.bucket_name,
                Key=file_key,
                Body=file_content,
                ContentType=file.content_type or 'application/octet-stream',
                Metadata=metadata
            )
            
            # Generar URL del archivo
            file_url = f"https://{self.bucket_name}.s3.amazonaws.com/{file_key}"
            
            logger.info(f"Examen médico subido exitosamente: {file_key}")
            
            return {
                "success": True,
                "file_key": file_key,
                "file_url": file_url,
                "original_filename": file.filename,
                "size": len(file_content),
                "content_type": file.content_type,
                "upload_date": datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error al subir examen médico: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    async def upload_bytes(self, file_content: bytes, file_key: str, content_type: str = "application/octet-stream", metadata: Dict[str, str] = None) -> Dict[str, Any]:
        """
        Subir contenido de bytes directamente a S3.
        
        Args:
            file_content: Contenido del archivo en bytes
            file_key: Clave del archivo en S3
            content_type: Tipo de contenido MIME
            metadata: Metadatos adicionales del archivo
            
        Returns:
            Dict con información del archivo subido
        """
        try:
            if not self._validate_s3_config():
                return {
                    "success": False,
                    "error": "Configuración de S3 incompleta"
                }
            
            # Metadatos por defecto
            if metadata is None:
                metadata = {}
            
            metadata.update({
                'upload_date': datetime.now().isoformat(),
                'content_type': content_type,
                'size': str(len(file_content))
            })
            
            # Subir archivo a S3
            self.s3_client.put_object(
                Bucket=self.bucket_name,
                Key=file_key,
                Body=file_content,
                ContentType=content_type,
                Metadata=metadata
            )
            
            # Generar URL del archivo
            file_url = f"https://{self.bucket_name}.s3.amazonaws.com/{file_key}"
            
            logger.info(f"Archivo subido exitosamente: {file_key}")
            
            return {
                "success": True,
                "file_key": file_key,
                "file_url": file_url,
                "size": len(file_content),
                "content_type": content_type,
                "upload_date": datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error al subir archivo: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    def _generate_generic_file_key(self, folder: str, filename: str, user_id: int = None) -> str:
        """
        Generar clave única para archivos genéricos.
        
        Args:
            folder: Carpeta donde guardar el archivo
            filename: Nombre del archivo
            user_id: ID del usuario (opcional)
            
        Returns:
            Clave única del archivo
        """
        # Limpiar nombre del archivo
        clean_filename = re.sub(r'[^a-zA-Z0-9._-]', '_', filename)
        
        # Generar timestamp único
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # Generar ID único corto
        unique_id = str(uuid.uuid4())[:8]
        
        # Construir clave del archivo
        if user_id:
            file_key = f"{folder}/user_{user_id}/{timestamp}_{unique_id}_{clean_filename}"
        else:
            file_key = f"{folder}/{timestamp}_{unique_id}_{clean_filename}"
        
        return file_key
    
    def delete_file(self, file_key: str) -> Dict[str, Any]:
        """
        Eliminar archivo de S3.
        
        Args:
            file_key: Clave del archivo en S3
            
        Returns:
            Diccionario con el resultado de la operación
        """
        try:
            self.s3_client.delete_object(
                Bucket=self.bucket_name,
                Key=file_key
            )
            
            logger.info(f"Archivo eliminado exitosamente: {file_key}")
            
            return {
                "success": True,
                "message": f"Archivo {file_key} eliminado exitosamente"
            }
            
        except Exception as e:
            logger.error(f"Error al eliminar archivo: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    def get_file_url(self, file_key: str, expiration: int = 3600) -> Optional[str]:
        """
        Generar URL firmada para acceder al archivo.
        
        Args:
            file_key: Clave del archivo en S3
            expiration: Tiempo de expiración en segundos (default: 1 hora)
            
        Returns:
            URL firmada o None si hay error
        """
        try:
            # Verificar si el archivo existe antes de generar la URL
            try:
                self.s3_client.head_object(Bucket=self.bucket_name, Key=file_key)
                logger.info(f"Archivo encontrado en S3: {file_key}")
            except Exception as head_error:
                logger.error(f"Archivo no encontrado en S3: {file_key}, Error: {head_error}")
                return None
            
            # Generar URL firmada con permisos específicos
            url = self.s3_client.generate_presigned_url(
                'get_object',
                Params={
                    'Bucket': self.bucket_name, 
                    'Key': file_key,
                    'ResponseContentDisposition': 'inline'
                },
                ExpiresIn=expiration
            )
            logger.info(f"URL firmada generada exitosamente para: {file_key}")
            return url
        except Exception as e:
            logger.error(f"Error al generar URL firmada para {file_key}: {e}")
            return None
    
    def list_worker_files(self, worker_id: int, folder_type: str = None) -> Dict[str, Any]:
        """
        Listar archivos de un trabajador.
        
        Args:
            worker_id: ID del trabajador
            folder_type: Tipo de carpeta (documentos/examenes_medicos)
            
        Returns:
            Lista de archivos del trabajador
        """
        try:
            # Definir prefijo de búsqueda
            if folder_type:
                prefix = f"{folder_type}/worker_{worker_id}/"
            else:
                prefix = f"worker_{worker_id}/"
            
            # Listar objetos
            response = self.s3_client.list_objects_v2(
                Bucket=self.bucket_name,
                Prefix=prefix
            )
            
            files = []
            if 'Contents' in response:
                for obj in response['Contents']:
                    # Obtener metadatos del objeto
                    metadata_response = self.s3_client.head_object(
                        Bucket=self.bucket_name,
                        Key=obj['Key']
                    )
                    
                    files.append({
                        'file_key': obj['Key'],
                        'size': obj['Size'],
                        'last_modified': obj['LastModified'].isoformat(),
                        'metadata': metadata_response.get('Metadata', {}),
                        'content_type': metadata_response.get('ContentType', 'unknown')
                    })
            
            return {
                "success": True,
                "files": files,
                "count": len(files)
            }
            
        except Exception as e:
            logger.error(f"Error al listar archivos del trabajador: {e}")
            return {
                "success": False,
                "error": str(e),
                "files": [],
                "count": 0
            }
    
    def check_connection(self) -> bool:
        """
        Verificar la conexión con S3.
        
        Returns:
            True si la conexión es exitosa
        """
        try:
            self.s3_client.head_bucket(Bucket=self.bucket_name)
            return True
        except Exception as e:
            logger.error(f"Error de conexión con S3: {e}")
            return False
    
    def test_s3_permissions(self) -> Dict[str, Any]:
        """
        Probar permisos específicos de S3.
        
        Returns:
            Diccionario con el estado de cada permiso
        """
        permissions = {
            "bucket_access": False,
            "list_objects": False,
            "get_object": False,
            "put_object": False,
            "delete_object": False,
            "generate_presigned_url": False,
            "error_details": []
        }
        
        try:
            # Probar acceso al bucket
            self.s3_client.head_bucket(Bucket=self.bucket_name)
            permissions["bucket_access"] = True
            logger.info("✓ Acceso al bucket exitoso")
        except Exception as e:
            permissions["error_details"].append(f"Bucket access error: {e}")
            logger.error(f"✗ Error de acceso al bucket: {e}")
        
        try:
            # Probar listado de objetos
            self.s3_client.list_objects_v2(Bucket=self.bucket_name, MaxKeys=1)
            permissions["list_objects"] = True
            logger.info("✓ Permiso de listado exitoso")
        except Exception as e:
            permissions["error_details"].append(f"List objects error: {e}")
            logger.error(f"✗ Error de listado: {e}")
        
        try:
            # Probar generación de URL firmada para un archivo de prueba
            test_key = "test/test_file.txt"
            url = self.s3_client.generate_presigned_url(
                'get_object',
                Params={'Bucket': self.bucket_name, 'Key': test_key},
                ExpiresIn=300
            )
            permissions["generate_presigned_url"] = True
            logger.info("✓ Generación de URL firmada exitosa")
        except Exception as e:
            permissions["error_details"].append(f"Presigned URL error: {e}")
            logger.error(f"✗ Error generando URL firmada: {e}")
        
        return permissions
    
    def get_config_status(self) -> Dict[str, Any]:
        """
        Obtener el estado de la configuración de S3 sin exponer credenciales.
        
        Returns:
            Diccionario con el estado de la configuración
        """
        config_status = {
            "aws_access_key_configured": bool(self.aws_access_key_id),
            "aws_secret_key_configured": bool(self.aws_secret_access_key),
            "bucket_name_configured": bool(self.bucket_name),
            "region_configured": bool(self.region),
            "bucket_name": self.bucket_name if self.bucket_name else "No configurado",
            "region": self.region if self.region else "No configurado"
        }
        
        # Verificar si todas las credenciales están configuradas
        config_status["fully_configured"] = all([
            config_status["aws_access_key_configured"],
            config_status["aws_secret_key_configured"],
            config_status["bucket_name_configured"],
            config_status["region_configured"]
        ])
        
        return config_status


class ContaboStorageService:
    def __init__(self):
        self.endpoint_url = settings.contabo_endpoint_url
        self.access_key_id = settings.contabo_access_key_id
        self.secret_access_key = settings.contabo_secret_access_key
        self.region = settings.contabo_region
        self.bucket_name = settings.contabo_bucket_name
        self.public_base_url = settings.contabo_public_base_url
        self.make_public = settings.contabo_make_public

        if not all([self.endpoint_url, self.access_key_id, self.secret_access_key, self.bucket_name]):
            missing_vars = []
            if not self.endpoint_url:
                missing_vars.append("CONTABO_ENDPOINT_URL")
            if not self.access_key_id:
                missing_vars.append("CONTABO_ACCESS_KEY_ID")
            if not self.secret_access_key:
                missing_vars.append("CONTABO_SECRET_ACCESS_KEY")
            if not self.bucket_name:
                missing_vars.append("CONTABO_BUCKET_NAME")
            error_msg = f"Variables de entorno faltantes para Contabo: {', '.join(missing_vars)}"
            logger.error(error_msg)
            raise ValueError(error_msg)

        self.s3_client = boto3.client(
            "s3",
            aws_access_key_id=self.access_key_id,
            aws_secret_access_key=self.secret_access_key,
            region_name=self.region,
            endpoint_url=self.endpoint_url
        )

    def _build_public_url(self, file_key: str) -> str:
        if self.public_base_url:
            return f"{self.public_base_url.rstrip('/')}/{file_key}"
        if self.endpoint_url:
            return f"{self.endpoint_url.rstrip('/')}/{self.bucket_name}/{file_key}"
        return file_key

    def get_public_url(self, file_key: str) -> str:
        return self._build_public_url(file_key)

    def upload_bytes(self, file_content: bytes, file_key: str, content_type: str = "application/octet-stream") -> str:
        params = {
            "Bucket": self.bucket_name,
            "Key": file_key,
            "Body": file_content,
            "ContentType": content_type or "application/octet-stream"
        }
        if self.make_public:
            params["ACL"] = "public-read"
        self.s3_client.put_object(**params)
        return self._build_public_url(file_key)

    def delete_file(self, file_key: str) -> bool:
        try:
            self.s3_client.delete_object(Bucket=self.bucket_name, Key=file_key)
            return True
        except Exception as e:
            logger.error(f"Error al eliminar archivo en Contabo: {e}")
            return False

    def download_file_as_bytes(self, file_key: str) -> Optional[bytes]:
        try:
            response = self.s3_client.get_object(Bucket=self.bucket_name, Key=file_key)
            return response["Body"].read()
        except Exception as e:
            logger.error(f"Error al descargar archivo en Contabo: {e}")
            return None

    def file_exists(self, file_key: str) -> bool:
        try:
            self.s3_client.head_object(Bucket=self.bucket_name, Key=file_key)
            return True
        except Exception:
            return False

    def list_files(self, prefix: str = None) -> list:
        try:
            response = self.s3_client.list_objects_v2(Bucket=self.bucket_name, Prefix=prefix or "")
            return [obj["Key"] for obj in response.get("Contents", [])]
        except Exception as e:
            logger.error(f"Error al listar archivos en Contabo: {e}")
            return []


# Instancia global del servicio
s3_service = S3StorageService()

try:
    contabo_service = ContaboStorageService()
except Exception as e:
    contabo_service = None
    logger.error(f"Error inicializando ContaboStorageService: {e}")


# Funciones de conveniencia
async def upload_employee_document(worker_id: int, file: UploadFile, document_type: str = "general"):
    """Función de conveniencia para subir documento de empleado."""
    return await s3_service.upload_employee_document(worker_id, file, document_type)


async def upload_medical_exam(worker_id: int, file: UploadFile, exam_type: str = "ocupacional"):
    """Función de conveniencia para subir examen médico."""
    return await s3_service.upload_medical_exam(worker_id, file, exam_type)


def delete_file(file_key: str):
    """Función de conveniencia para eliminar archivo."""
    return s3_service.delete_file(file_key)


def get_file_url(file_key: str, expiration: int = 3600):
    """Función de conveniencia para obtener URL firmada."""
    return s3_service.get_file_url(file_key, expiration)


def list_worker_files(worker_id: int, folder_type: str = None):
    """Función de conveniencia para listar archivos de trabajador."""
    return s3_service.list_worker_files(worker_id, folder_type)
