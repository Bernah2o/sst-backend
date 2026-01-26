## Hallazgos en tu proyecto
- Ya existe una “Matriz de Riesgos y Peligros” en la app, pero está modelada como **Profesiograma por cargo**: `Profesiograma` + relación `ProfesiogramaFactor` (exposición + controles). [profesiograma.py](file:///e:/DH2OCOL/python/sst-app/sst-backend/app/models/profesiograma.py#L61-L94)
- El frontend hoy **no captura** la información de valoración por factor: al guardar, manda todos los factores con `nivel_exposicion='medio'` y `tiempo_exposicion_horas=8`. [ProfesiogramasCargo.tsx](file:///e:/DH2OCOL/python/sst-app/sst-frontend/src/pages/ProfesiogramasCargo.tsx#L320-L347)
- La vista del trabajador muestra “Matriz de Riesgos y Peligros”, pero solo enseña exposición y EPP, y usa `nivel_exposicion` como “riesgo”. [WorkerProfesiograma.tsx](file:///e:/DH2OCOL/python/sst-app/sst-frontend/src/pages/WorkerProfesiograma.tsx#L169-L207)

## Norma/Metodología recomendada (la que calza con tu matriz)
- Tu plantilla (imagen) corresponde al enfoque **GTC 45 (Identificación de peligros y valoración de riesgos)**: ND, NE, NP, NC, NR y aceptabilidad/intervención.
- Para “cumplir con norma” en el contexto típico de SST Colombia: mantener **trazabilidad y evidencia** de identificación/valoración/controles (alineado a Decreto 1072/2015 y estándares mínimos), usando GTC 45 como metodología de valoración.

## Opción que cumple norma y se integra mejor (recomendada)
**Extender el módulo existente de Profesiogramas** para que `ProfesiogramaFactor` almacene la valoración GTC 45 por cada peligro/factor del cargo, calcule NR y muestre aceptabilidad e intervención.
- Ventaja: usa tus pantallas y rutas actuales (por cargo y por trabajador) y requiere menos cambio arquitectónico.
- Resultado: tu “matriz de peligro” queda **auditable** y coherente con los datos ya existentes (cargos → profesiogramas → factores).

## Cambios de datos (Backend/DB)
- Agregar columnas a `profesiograma_factores` para capturar lo que exige GTC 45 y lo que aparece en tu formato:
  - Identificación/contexto (opcionales para reflejar la plantilla): `zona_lugar`, `proceso`, `actividad`, `tarea`, `rutinario`.
  - Peligro y efectos: `descripcion_peligro`, `efectos_posibles`, `fuente`, `medio`, `individuo`.
  - Valoración GTC45: `nd`, `ne`, `nc` (inputs), y campos calculados/derivados en respuesta `np`, `nr`, `nivel_intervencion`, `aceptabilidad`.
  - Controles/medidas: mantener lo existente (`controles_ingenieria`, `controles_administrativos`, `epp_requerido`) y sumar `senalizacion`, `eliminacion`, `sustitucion` (para jerarquía de controles).

## Lógica de cálculo (Backend + opcional Frontend)
- Implementar una función de cálculo GTC45 (con validación de valores permitidos) que, a partir de ND/NE/NC, calcule NP/NR y clasifique:
  - `aceptabilidad` (No aceptable / Aceptable con control / etc.)
  - `nivel_intervencion` (I–IV o el esquema que uses hoy en tu formato)
- Exponer estos resultados en los schemas de respuesta para que el frontend solo renderice y valide.

## Cambios de API
- Actualizar schemas Pydantic para `ProfesiogramaFactor` (create/update/read) incluyendo los nuevos campos.
- Ajustar endpoints `POST /profesiogramas/cargos/{cargo_id}` y `PUT /profesiogramas/{id}` para guardar los nuevos campos.
- Mantener compatibilidad: si no vienen ND/NE/NC, el backend puede marcar la fila como “pendiente de valoración” o usar defaults controlados (preferible: requerirlos cuando el factor esté seleccionado).

## Cambios en Frontend (React/MUI)
- En [ProfesiogramasCargo.tsx](file:///e:/DH2OCOL/python/sst-app/sst-frontend/src/pages/ProfesiogramasCargo.tsx) reemplazar el guardado “por defecto” por una UI de captura por factor:
  - Lista/tabla de factores seleccionados con selects ND/NE/NC (y campos opcionales: proceso/actividad/tarea).
  - Campos para controles (ingeniería, administrativos, EPP, etc.).
  - Cálculo en vivo (NP/NR + color) para UX; el backend valida y recalcula.
- En [WorkerProfesiograma.tsx](file:///e:/DH2OCOL/python/sst-app/sst-frontend/src/pages/WorkerProfesiograma.tsx) mostrar:
  - ND/NE/NC/NP/NR
  - Aceptabilidad + nivel de intervención
  - Controles por jerarquía

## Reportes/Export (opcional pero muy útil para evidencia)
- Agregar un endpoint para **exportar la matriz** del cargo/profesiograma a Excel o PDF (mínimo Excel), respetando la plantilla.

## Verificación
- Backend: tests unitarios para cálculo y validaciones (valores permitidos, rangos, clasificación).
- Frontend: pruebas manuales de flujo (crear profesiograma con factores, guardar, ver en trabajador).

## Alternativa (más “pura” pero más grande)
Crear un módulo nuevo “Matriz de Peligros” por **proceso/área** (no por cargo) y luego asociarlo a cargos/trabajadores. Es más fiel a algunas organizaciones, pero implica más pantallas, permisos y relaciones; la recomiendo solo si tu operación realmente gestiona SST por procesos (no por cargos).

Si confirmas este plan, implemento la opción recomendada (Profesiogramas + GTC45) de punta a punta: migración, backend, frontend y verificación.