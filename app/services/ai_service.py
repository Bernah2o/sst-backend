"""
Servicio de Inteligencia Artificial para la plataforma SST.

Integración con Perplexity AI para generar sugerencias contextuales
en la Matriz Legal y otros módulos.
"""

import logging
from typing import Optional
import httpx

from app.config import settings

logger = logging.getLogger(__name__)

PERPLEXITY_API_URL = "https://api.perplexity.ai/chat/completions"


class AIService:
    """Servicio para interactuar con APIs de IA."""

    def __init__(self):
        self.api_key = settings.perplexity_api_key
        self.model = settings.perplexity_model

    def is_configured(self) -> bool:
        """Verifica si el servicio de IA está configurado."""
        return bool(self.api_key)

    async def generate_compliance_suggestions(
        self,
        tipo_norma: str,
        numero_norma: str,
        anio: Optional[int],
        descripcion_norma: Optional[str],
        articulo: Optional[str],
        exigencias: Optional[str],
        tema_general: Optional[str],
        clasificacion: Optional[str],
    ) -> dict:
        """
        Genera sugerencias de cumplimiento para una norma legal.

        Returns:
            dict con keys: evidencia, observaciones, plan_accion
        """
        if not self.is_configured():
            raise ValueError("Perplexity API key no configurada")

        # Construir el contexto de la norma
        norma_info = f"{tipo_norma} {numero_norma}"
        if anio:
            norma_info += f" de {anio}"

        context_parts = [f"Norma: {norma_info}"]

        if clasificacion:
            context_parts.append(f"Clasificación: {clasificacion}")
        if tema_general:
            context_parts.append(f"Tema: {tema_general}")
        if descripcion_norma:
            context_parts.append(f"Descripción: {descripcion_norma}")
        if articulo:
            context_parts.append(f"Artículo: {articulo}")
        if exigencias:
            context_parts.append(f"Exigencias: {exigencias}")

        context = "\n".join(context_parts)

        prompt = f"""Eres un experto en Seguridad y Salud en el Trabajo (SST) en Colombia.
Basándote en la siguiente norma legal colombiana, genera sugerencias específicas y prácticas para documentar su cumplimiento.

{context}

Proporciona EXACTAMENTE el siguiente formato JSON (sin texto adicional):
{{
    "evidencia": "Texto con evidencias específicas que demuestran el cumplimiento de esta norma. Lista los documentos, registros, actas o procedimientos concretos que se deben tener.",
    "observaciones": "Observaciones relevantes sobre el estado de cumplimiento, aspectos a considerar o puntos de atención para esta norma específica.",
    "plan_accion": "Acciones concretas y específicas a implementar para lograr o mantener el cumplimiento de esta norma. Incluye actividades, responsables sugeridos y frecuencias cuando aplique."
}}

Importante:
- Las sugerencias deben ser específicas para esta norma, no genéricas
- Usa terminología técnica de SST en Colombia
- Los textos deben ser concisos pero completos (máximo 300 caracteres cada uno)
- Responde SOLO con el JSON, sin explicaciones adicionales"""

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    PERPLEXITY_API_URL,
                    headers={
                        "Authorization": f"Bearer {self.api_key}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "model": self.model,
                        "messages": [
                            {
                                "role": "system",
                                "content": "Eres un experto en Seguridad y Salud en el Trabajo (SST) en Colombia. Respondes siempre en formato JSON válido."
                            },
                            {
                                "role": "user",
                                "content": prompt
                            }
                        ],
                        "temperature": 0.3,
                        "max_tokens": 1000,
                    }
                )

                if response.status_code != 200:
                    error_detail = response.text
                    try:
                        error_json = response.json()
                        error_detail = error_json.get("error", {}).get("message", response.text)
                    except:
                        pass
                    logger.error(f"Error de Perplexity API: {response.status_code} - {error_detail}")
                    logger.error(f"Modelo usado: {self.model}")
                    raise Exception(f"Error de API ({response.status_code}): {error_detail}")

                data = response.json()
                content = data["choices"][0]["message"]["content"]

                # Intentar parsear el JSON de la respuesta
                import json

                # Limpiar el contenido (puede venir con markdown)
                content = content.strip()
                if content.startswith("```json"):
                    content = content[7:]
                if content.startswith("```"):
                    content = content[3:]
                if content.endswith("```"):
                    content = content[:-3]
                content = content.strip()

                try:
                    result = json.loads(content)
                    return {
                        "evidencia": result.get("evidencia", ""),
                        "observaciones": result.get("observaciones", ""),
                        "plan_accion": result.get("plan_accion", ""),
                    }
                except json.JSONDecodeError:
                    logger.warning(f"No se pudo parsear JSON de Perplexity: {content}")
                    # Intentar extraer información del texto
                    return {
                        "evidencia": content[:300] if len(content) > 300 else content,
                        "observaciones": "",
                        "plan_accion": "",
                    }

        except httpx.TimeoutException:
            logger.error("Timeout al conectar con Perplexity API")
            raise Exception("Tiempo de espera agotado al conectar con el servicio de IA")
        except Exception as e:
            logger.error(f"Error al generar sugerencias: {str(e)}")
            raise


# Instancia global del servicio
ai_service = AIService()
