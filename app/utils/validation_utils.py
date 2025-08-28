#!/usr/bin/env python3
"""
Utilidades para validación robusta de parámetros
"""

from typing import Optional, Union, Any
from fastapi import HTTPException, status

def safe_int_conversion(value: Any, field_name: str, allow_none: bool = True) -> Optional[int]:
    """
    Convierte de manera segura un valor a entero con manejo de errores mejorado.
    
    Args:
        value: El valor a convertir
        field_name: Nombre del campo para mensajes de error
        allow_none: Si se permite None como valor válido
    
    Returns:
        El valor convertido a entero o None si allow_none=True
    
    Raises:
        HTTPException: Si la conversión falla
    """
    if value is None:
        if allow_none:
            return None
        else:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={
                    "success": False,
                    "message": f"El parámetro '{field_name}' es requerido",
                    "detail": f"El campo '{field_name}' no puede ser nulo",
                    "error_code": 422,
                    "field": field_name
                }
            )
    
    # Si ya es un entero, devolverlo directamente
    if isinstance(value, int):
        return value
    
    # Si es un string, intentar convertir
    if isinstance(value, str):
        # Eliminar espacios en blanco
        value = value.strip()
        
        # Si está vacío después de eliminar espacios
        if not value:
            if allow_none:
                return None
            else:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail={
                        "success": False,
                        "message": f"El parámetro '{field_name}' no puede estar vacío",
                        "detail": f"El campo '{field_name}' requiere un valor válido",
                        "error_code": 422,
                        "field": field_name
                    }
                )
        
        # Intentar conversión a entero
        try:
            return int(value)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={
                    "success": False,
                    "message": f"El parámetro '{field_name}' debe ser un número entero válido. Valor recibido: '{value}'",
                    "detail": f"No se puede convertir '{value}' a entero en el campo '{field_name}'",
                    "error_code": 422,
                    "field": field_name,
                    "received_value": value
                }
            )
    
    # Si es un float, verificar que sea un entero
    if isinstance(value, float):
        if value.is_integer():
            return int(value)
        else:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={
                    "success": False,
                    "message": f"El parámetro '{field_name}' debe ser un número entero, no decimal. Valor recibido: {value}",
                    "detail": f"El campo '{field_name}' no acepta valores decimales",
                    "error_code": 422,
                    "field": field_name,
                    "received_value": value
                }
            )
    
    # Tipo no soportado
    raise HTTPException(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        detail={
            "success": False,
            "message": f"El parámetro '{field_name}' tiene un tipo no válido. Tipo recibido: {type(value).__name__}",
            "detail": f"El campo '{field_name}' debe ser un número entero",
            "error_code": 422,
            "field": field_name,
            "received_type": type(value).__name__
        }
    )


def validate_pagination_params(skip: Union[int, str, None] = 0, limit: Union[int, str, None] = 100) -> tuple[int, int]:
    """
    Valida y convierte parámetros de paginación.
    
    Args:
        skip: Número de elementos a omitir
        limit: Número máximo de elementos a devolver
    
    Returns:
        Tupla con (skip, limit) validados
    """
    validated_skip = safe_int_conversion(skip, 'skip', allow_none=False)
    validated_limit = safe_int_conversion(limit, 'limit', allow_none=False)
    
    # Validar rangos
    if validated_skip < 0:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "success": False,
                "message": "El parámetro 'skip' debe ser mayor o igual a 0",
                "detail": f"Valor recibido para 'skip': {validated_skip}",
                "error_code": 422,
                "field": "skip"
            }
        )
    
    if validated_limit <= 0:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "success": False,
                "message": "El parámetro 'limit' debe ser mayor a 0",
                "detail": f"Valor recibido para 'limit': {validated_limit}",
                "error_code": 422,
                "field": "limit"
            }
        )
    
    if validated_limit > 1000:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "success": False,
                "message": "El parámetro 'limit' no puede ser mayor a 1000",
                "detail": f"Valor recibido para 'limit': {validated_limit}",
                "error_code": 422,
                "field": "limit"
            }
        )
    
    return validated_skip, validated_limit


def validate_id_param(value: Union[int, str, None], field_name: str, required: bool = True) -> Optional[int]:
    """
    Valida un parámetro ID (evaluation_id, user_id, course_id, etc.)
    
    Args:
        value: El valor del ID a validar
        field_name: Nombre del campo para mensajes de error
        required: Si el parámetro es requerido
    
    Returns:
        El ID validado o None si no es requerido
    """
    validated_id = safe_int_conversion(value, field_name, allow_none=not required)
    
    if validated_id is not None and validated_id <= 0:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "success": False,
                "message": f"El parámetro '{field_name}' debe ser un número entero positivo",
                "detail": f"Valor recibido para '{field_name}': {validated_id}",
                "error_code": 422,
                "field": field_name
            }
        )
    
    return validated_id