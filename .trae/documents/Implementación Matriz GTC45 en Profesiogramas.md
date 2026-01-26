## Objetivo
- Integrar la matriz de peligros (GTC 45) dentro del módulo existente de **Profesiogramas**, para que cada factor/peligro por cargo tenga valoración (ND/NE/NC → NP/NR), aceptabilidad e intervención, y se visualice en la app.

## Alcance exacto (Opción recomendada)
- Extender `ProfesiogramaFactor` (tabla `profesiograma_factores`) para capturar campos GTC45 y jerarquía de controles.
- Actualizar API (schemas y endpoints) para guardar/retornar esos campos y devolver cálculos.
- Actualizar UI de “Profesiogramas por Cargo” para editar valoración y controles por factor.
- Actualizar vista “Matriz por Trabajador” para mostrar ND/NE/NC/NP/NR + aceptabilidad/intervención.
- Agregar exportación de la matriz (Excel) como evidencia (opcional en este mismo sprint; lo implemento al final).

## Backend (FastAPI/SQLAlchemy/Alembic)
### 1) Migración Alembic
- Crear migración que agregue columnas a `profesiograma_factores`:
  - Identificación/contexto (opcionales): `proceso`, `actividad`, `tarea`, `rutinario`.
  - Peligro/efectos (opcionales): `descripcion_peligro`, `efectos_posibles`.
  - Valoración GTC45 (inputs): `nd`, `ne`, `nc` (enteros).
  - Controles/medidas (jerarquía): `eliminacion`, `sustitucion`, `senalizacion` (Text) además de los existentes.
- Agregar índices básicos si aplica (por ejemplo por `proceso`).

### 2) Modelo y schemas
- Actualizar [profesiograma.py](file:///e:/DH2OCOL/python/sst-app/sst-backend/app/models/profesiograma.py) para incluir las nuevas columnas en `ProfesiogramaFactor`.
- Actualizar [schemas/profesiograma.py](file:///e:/DH2OCOL/python/sst-app/sst-backend/app/schemas/profesiograma.py) para:
  - Aceptar en create/update: `nd`, `ne`, `nc`, contexto y controles.
  - Retornar en read: además de lo guardado, retornar **campos calculados** `np`, `nr`, `aceptabilidad`, `nivel_intervencion`.

### 3) Lógica de cálculo GTC45
- Implementar utilidades (p. ej. `app/services/gtc45.py`) que:
  - Validen ND/NE/NC contra valores permitidos.
  - Calculen `np = nd * ne` y `nr = np * nc`.
  - Clasifiquen `nivel_intervencion` y `aceptabilidad` según rangos GTC45.
- Asegurar que el backend siempre recalcula y no confía en cálculos del frontend.

### 4) Endpoints
- Ajustar `POST /profesiogramas/cargos/{cargo_id}` y `PUT /profesiogramas/{id}` para persistir nuevos campos.
- Ajustar el serializer `_serialize_profesiograma` para incluir factores con el resultado calculado.

### 5) Pruebas backend
- Agregar tests unitarios para:
  - Validaciones de valores.
  - Cálculo NP/NR.
  - Clasificación intervención/aceptabilidad.

## Frontend (React/MUI)
### 6) UI “Profesiogramas por Cargo”
- En [ProfesiogramasCargo.tsx](file:///e:/DH2OCOL/python/sst-app/sst-frontend/src/pages/ProfesiogramasCargo.tsx):
  - Reemplazar el “default medio/8h” por edición por-factor.
  - Renderizar una tabla/accordion de factores seleccionados con:
    - ND/NE/NC (select), horas/día, valores medidos y límites (si aplica).
    - Controles (eliminación/sustitución/ingeniería/administrativos/señalización/EPP).
    - Vista en vivo de NP/NR (solo UX; el backend valida).
  - Al guardar, construir `payload.factores[]` con los campos completos.

### 7) UI “Matriz por Trabajador”
- En [WorkerProfesiograma.tsx](file:///e:/DH2OCOL/python/sst-app/sst-frontend/src/pages/WorkerProfesiograma.tsx):
  - Mostrar ND/NE/NC/NP/NR.
  - Mostrar `aceptabilidad` y `nivel_intervencion`.
  - Mostrar controles por jerarquía.

## Export (evidencia)
### 8) Exportar matriz a Excel
- Endpoint backend: `GET /profesiogramas/{id}/export/matriz.xlsx`.
- Botón en UI (por cargo) para descargar.

## Validación end-to-end
- Levantar backend+frontend, crear/editar un profesiograma con 2–3 factores, verificar:
  - Persistencia en DB.
  - Cálculos y clasificación correctos.
  - Render en vista por trabajador.
  - Export funcional.

## Notas de compatibilidad
- Migración mantiene datos existentes (valores nuevos quedan null). La UI pedirá completar ND/NE/NC cuando se edite un profesiograma.
