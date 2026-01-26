## Estado Actual
- El modelo [worker.py](file:///e:/DH2OCOL/python/sst-app/sst-backend/app/models/worker.py) ya tiene `birth_date` y calcula `age` automáticamente con `@hybrid_property`.
- El schema [schemas/worker.py](file:///e:/DH2OCOL/python/sst-app/sst-backend/app/schemas/worker.py) ya expone `age` (no requiere columna en BD).
- En profesiogramas ya existe `periodicidad_emo_meses` (6/12/24/36) y `justificacion_periodicidad_emo`, con validación obligatoria si >12: [schemas/profesiograma.py](file:///e:/DH2OCOL/python/sst-app/sst-backend/app/schemas/profesiograma.py) y constraints en BD: [models/profesiograma.py](file:///e:/DH2OCOL/python/sst-app/sst-backend/app/models/profesiograma.py).

## Objetivo
- Adaptar la “Justificación Técnica” cuando `periodicidad_emo_meses` es 24 o 36 meses usando los criterios del archivo `Criterios Específicos para Definir.txt`.
- Usar la edad (calculada desde `birth_date`) y la antigüedad (desde `fecha_de_ingreso`) como criterios automáticos para sugerir 24 vs 36 y para construir parte de la justificación.

## Cambios de Backend (sin tocar frontend)
1) **Servicio de decisión de periodicidad y generación de justificación**
- Crear un módulo de servicio (ej. `app/services/emo_periodicidad.py`) con:
  - `compute_cargo_worker_stats(cargo_id)`: total trabajadores activos del cargo, lista/contadores por edad (<21 / >=21), y por antigüedad (<2 años / >=2 años) calculada desde `fecha_de_ingreso`.
  - `suggest_periodicidad_and_justificacion(stats, periodicidad_target)`:
    - Si hay al menos un trabajador <21 → sugiere 24 meses.
    - Si hay trabajadores con antigüedad <2 años → sugiere 24 meses.
    - Si todos >=21 y todos >=2 años → sugiere 36 meses.
    - Genera un texto de justificación que cite explícitamente los criterios activados (edad/antigüedad) y deje secciones “pendientes” para los criterios no evaluables automáticamente (p.ej. cambios recientes de ambiente, indicadores epidemiológicos, hallazgos previos), manteniendo el mínimo de caracteres requerido.

2) **Integración en creación/actualización de profesiogramas**
- En [api/profesiogramas.py](file:///e:/DH2OCOL/python/sst-app/sst-backend/app/api/profesiogramas.py):
  - Al crear/actualizar, si `periodicidad_emo_meses` es 24 o 36 y `justificacion_periodicidad_emo` viene vacía, autocompletar con el texto sugerido por el servicio.
  - Si `numero_trabajadores_expuestos` no viene, rellenarlo automáticamente con el conteo de trabajadores activos del cargo.
  - Mantener la validación actual (campo obligatorio y mínimo de longitud) para asegurar consistencia.

3) **Endpoint opcional de “preview/sugerencia” (para UI o auditoría)**
- Agregar un endpoint como `GET /profesiogramas/cargos/{cargo_id}/emo/sugerencia` que retorne:
  - periodicidad sugerida (24/36)
  - resumen de criterios activados
  - borrador de `justificacion_periodicidad_emo`
  - estadísticas básicas (nº expuestos, nº <21, nº con antigüedad <2 años)

## Cambios en Worker
- No agregaré columna `age` en BD: ya se calcula automáticamente con `birth_date` (esto es lo correcto para evitar datos duplicados).
- Solo haría ajustes si se requiere robustez adicional (p.ej. manejar `birth_date=None`, aunque hoy es `nullable=False`).

## Pruebas y Validación
- Agregar pruebas unitarias para:
  - cálculo de edad/antigüedad y reglas 24 vs 36
  - generación de texto de justificación (incluye criterios y cumple mínimo de longitud)
  - integración: creación de profesiograma sin `justificacion_periodicidad_emo` y periodicidad 24/36 autocompleta.

## Resultado Esperado
- Cuando el usuario seleccione 24 o 36 meses y no escriba justificación, el sistema generará una justificación técnica basada en edad/antigüedad (y deja marcadores para criterios que requieren evidencia del SG-SST).
- La edad se utiliza “para la elaboración del profesiograma” sin necesidad de guardar un campo nuevo en `workers`.