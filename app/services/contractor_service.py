"""
Servicio para gestión de contratistas y sus documentos.
"""

import json
import logging
from typing import Optional, Dict, Any, List
from fastapi import UploadFile, HTTPException
from sqlalchemy.orm import Session

from app.models.contractor import Contractor, ContractorDocument
from app.utils.storage import storage_manager

logger = logging.getLogger(__name__)


class ContractorService:
    """Servicio para manejar contratistas y sus documentos."""

    @staticmethod
    async def delete_document(
        document_id: int,
        db: Session
    ) -> Dict[str, str]:
        """
        Eliminar un documento de contratista de la base de datos y Storage.
        
        Args:
            document_id: ID del documento a eliminar
            db: Sesión de base de datos
            
        Returns:
            Diccionario con mensaje de confirmación
        """
        try:
            # Buscar el documento en la base de datos
            document = db.query(ContractorDocument).filter(
                ContractorDocument.id == document_id
            ).first()
            
            if not document:
                raise HTTPException(status_code=404, detail="Documento no encontrado")
            
            # Guardar información del archivo para eliminarlo de Storage
            file_path = document.file_path
            
            # Eliminar el documento de la base de datos
            db.delete(document)
            db.commit()
            
            # Eliminar el archivo de Storage
            if file_path:
                try:
                    await storage_manager.delete_file(file_path)
                    logger.info(f"Archivo eliminado de Storage: {file_path}")
                except Exception as e:
                    logger.warning(f"Error al eliminar archivo de Storage: {e}")
                    # No fallar la operación si no se puede eliminar de Storage
            
            logger.info(f"Documento eliminado exitosamente: ID {document_id}")
            return {"message": "Documento eliminado exitosamente"}
            
        except HTTPException:
            raise
        except Exception as e:
            db.rollback()
            logger.error(f"Error al eliminar documento: {e}")
            raise HTTPException(status_code=500, detail=f"Error interno del servidor: {str(e)}")


# Instancia global del servicio
contractor_service = ContractorService()