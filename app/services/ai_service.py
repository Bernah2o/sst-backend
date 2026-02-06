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

        context_parts = [f"NORMA LEGAL: {norma_info}"]

        if clasificacion:
            context_parts.append(f"Clasificación: {clasificacion}")
        if tema_general:
            context_parts.append(f"Tema General: {tema_general}")
        if articulo:
            context_parts.append(f"Artículo específico: {articulo}")

        # La descripción y exigencias son los campos MÁS IMPORTANTES para generar sugerencias
        if descripcion_norma:
            context_parts.append(f"\n📋 DESCRIPCIÓN DE LA NORMA:\n{descripcion_norma}")
        if exigencias:
            context_parts.append(f"\n⚠️ EXIGENCIAS Y REQUISITOS ESPECÍFICOS:\n{exigencias}")

        context = "\n".join(context_parts)

        prompt = f"""Eres un experto en Seguridad y Salud en el Trabajo (SST) en Colombia.

CONTEXTO DE LA NORMA:
{context}

INSTRUCCIONES:
Basándote ESPECÍFICAMENTE en la DESCRIPCIÓN y las EXIGENCIAS de esta norma, genera sugerencias prácticas y concretas para documentar su cumplimiento.

Proporciona EXACTAMENTE el siguiente formato JSON (sin texto adicional):
{{
    "evidencia": "Documentos, registros o procedimientos específicos que demuestren el cumplimiento de las exigencias descritas. Sé específico según lo que pide la norma.",
    "observaciones": "Aspectos críticos a considerar, frecuencia de actualización, o puntos de atención basados en las exigencias específicas de esta norma.",
    "plan_accion": "Acciones concretas para cumplir con las exigencias específicas de esta norma. Incluye qué hacer, quién lo debe hacer y con qué frecuencia."
}}

IMPORTANTE:
- Basa tus sugerencias en las EXIGENCIAS ESPECÍFICAS de la norma, no en generalidades
- Si la norma habla de documentación específica, menciona esos documentos
- Si la norma establece periodicidades, inclúyelas en el plan de acción
- Los textos deben ser concisos (máximo 500 caracteres cada uno)
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


    async def generate_interactive_lesson_content(
        self,
        titulo: str,
        tema: str,
        descripcion: Optional[str] = None,
        num_slides: int = 5,
        incluir_quiz: bool = True,
        incluir_actividad: bool = True,
    ) -> dict:
        """
        Genera contenido para una lección interactiva sobre SST.

        Args:
            titulo: Título de la lección
            tema: Tema principal (ej: "Uso de EPP", "Trabajo en alturas")
            descripcion: Descripción adicional del contenido deseado
            num_slides: Número de slides a generar (3-10)
            incluir_quiz: Si debe incluir preguntas de quiz
            incluir_actividad: Si debe incluir actividad interactiva

        Returns:
            dict con slides, quizzes y actividades generadas
        """
        if not self.is_configured():
            raise ValueError("Perplexity API key no configurada")

        num_slides = max(3, min(10, num_slides))  # Limitar entre 3 y 10

        context = f"""TÍTULO DE LA LECCIÓN: {titulo}
TEMA PRINCIPAL: {tema}"""
        if descripcion:
            context += f"\nDESCRIPCIÓN ADICIONAL: {descripcion}"

        quiz_instruction = ""
        if incluir_quiz:
            quiz_instruction = """
- Incluye 2-3 preguntas de quiz (tipo multiple_choice o true_false) distribuidas en slides tipo "quiz"
- Cada quiz debe tener: question_text, question_type, points (1-3), options con is_correct"""

        activity_instruction = ""
        if incluir_actividad:
            activity_instruction = """
- Incluye 1 actividad interactiva al final (tipo: "matching" o "ordering")
- Para "matching": pares de conceptos relacionados (izquierda-derecha)
- Para "ordering": pasos de un procedimiento en orden correcto"""

        prompt = f"""Eres un experto en Seguridad y Salud en el Trabajo (SST) y diseño instruccional.

{context}

INSTRUCCIONES:
Genera contenido educativo para una lección interactiva con {num_slides} slides sobre este tema de SST.

REQUISITOS:
- Contenido práctico y aplicable al contexto laboral colombiano
- Lenguaje claro y profesional
- Incluir datos, estadísticas o normatividad relevante cuando sea apropiado
{quiz_instruction}
{activity_instruction}

Responde EXACTAMENTE con este formato JSON:
{{
    "slides": [
        {{
            "order_index": 0,
            "slide_type": "text",
            "title": "Título del slide",
            "content": {{
                "html": "<h2>Título</h2><p>Contenido educativo aquí...</p><ul><li>Punto 1</li><li>Punto 2</li></ul>"
            }}
        }},
        {{
            "order_index": 1,
            "slide_type": "text_image",
            "title": "Título con imagen",
            "content": {{
                "text": "Descripción del contenido",
                "image_url": "",
                "image_description": "Descripción de la imagen sugerida",
                "layout": "left"
            }}
        }},
        {{
            "order_index": 2,
            "slide_type": "quiz",
            "title": "Pregunta de verificación",
            "content": {{}},
            "quiz": {{
                "question_text": "¿Cuál es la respuesta correcta?",
                "question_type": "multiple_choice",
                "points": 1,
                "explanation": "Explicación de la respuesta correcta",
                "options": [
                    {{"text": "Opción A", "is_correct": false}},
                    {{"text": "Opción B", "is_correct": true}},
                    {{"text": "Opción C", "is_correct": false}}
                ]
            }}
        }}
    ],
    "activity": {{
        "title": "Actividad práctica",
        "activity_type": "matching",
        "instructions": "Une cada concepto con su definición",
        "config": {{
            "pairs": [
                {{"left": "Concepto 1", "right": "Definición 1"}},
                {{"left": "Concepto 2", "right": "Definición 2"}}
            ]
        }},
        "points": 5
    }}
}}

IMPORTANTE:
- Genera exactamente {num_slides} slides
- El contenido HTML debe ser válido y bien formateado
- Los quizzes deben tener exactamente una respuesta correcta
- Responde SOLO con el JSON, sin texto adicional"""

        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
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
                                "content": "Eres un experto en Seguridad y Salud en el Trabajo (SST) y diseño instruccional. Generas contenido educativo de alta calidad en formato JSON válido."
                            },
                            {
                                "role": "user",
                                "content": prompt
                            }
                        ],
                        "temperature": 0.7,
                        "max_tokens": 4000,
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
                    raise Exception(f"Error de API ({response.status_code}): {error_detail}")

                data = response.json()
                content = data["choices"][0]["message"]["content"]

                # Limpiar el contenido
                import json
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
                        "slides": result.get("slides", []),
                        "activity": result.get("activity"),
                        "success": True
                    }
                except json.JSONDecodeError as e:
                    logger.warning(f"No se pudo parsear JSON de Perplexity: {content[:500]}")
                    raise Exception(f"Error al procesar respuesta de IA: {str(e)}")

        except httpx.TimeoutException:
            logger.error("Timeout al conectar con Perplexity API")
            raise Exception("Tiempo de espera agotado al conectar con el servicio de IA")
        except Exception as e:
            logger.error(f"Error al generar contenido de lección: {str(e)}")
            raise


# Instancia global del servicio
ai_service = AIService()
