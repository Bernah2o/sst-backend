## Objetivo
- Ajustar la matriz para que produzca el mismo resultado/estructura del ejemplo “# MATRIZ GTC 45 - SECRETARIA EJECUT.txt”, incluyendo escalas, interpretaciones (NP/NR), aceptabilidad, jerarquía ESIAE y secciones de resumen.

## Alineación de Metodología (cálculos y etiquetas)
- **Actualizar escalas permitidas** en el backend y frontend para que coincidan con el TXT:
  - ND: permitir **-10, 2, 6, 10** (incluyendo “Bajo = -10” como en el documento).
  - NE: 1,2,3,4.
  - NC: 10,25,60,100.
- **Agregar interpretaciones calculadas** (además de NP/NR):
  - Interpretación NP: MUY ALTO / ALTO / MEDIO / BAJO según rangos del TXT.
  - Nivel Riesgo (NR) para mostrar exactamente como el ejemplo usa “ALTO / MEDIO-ALTO / MEDIO / BAJO”.
  - Aceptabilidad: NO ACEPTABLE / CONDICIONALMENTE ACEPTABLE / ACEPTABLE según el ejemplo.
  - Color y acción (texto) para exportes.

## Modelo de datos para que el reporte quede “igual”
- **Extender Profesiograma** con campos de cabecera del documento:
  - Empresa, departamento, código del cargo, fecha de elaboración, validado por, próxima revisión, versión (ya existe), nro trabajadores expuestos.
- **Extender ProfesiogramaFactor** con campos que el ejemplo usa por peligro:
  - zona/lugar, tipo, clasificación, “controles existentes”, fuente/medio/individuo (texto), peor consecuencia, requisito legal específico.
- **Crear tablas hijas (listas) para que el reporte tenga tablas como el ejemplo**:
  - Jerarquía ESIAE por peligro (E/S/I/A/EPP): medida, descripción, estado actual, meta.
  - Medidas de intervención por peligro: tipo (Fuente/Medio/Individuo/Vigilancia), descripción, responsable, plazo.

## Backend: endpoints y exportes
- Actualizar schemas y endpoints de profesiogramas para crear/editar/leer:
  - Cabecera del documento.
  - Detalle por peligro (incluyendo listas ESIAE e intervención).
  - Campos calculados (NP/NR + interpretaciones + aceptabilidad).
- **Agregar exportación en Markdown (.md/.txt)** que renderice el documento con el mismo layout (títulos, tablas y secciones) del ejemplo.
- Ajustar exportación Excel existente para incluir las nuevas columnas y, si aplica, hojas extra (Resumen Ejecutivo).

## Frontend: UI para capturar lo que pide el formato
- En “Profesiogramas por Cargo”:
  - Formulario de cabecera (empresa/departamento/código/validación/próxima revisión/nro expuestos).
  - Por cada factor/peligro:
    - Campos del peligro + selects ND/NE/NC con los valores exactos del ejemplo.
    - Editor de tabla ESIAE (filas por nivel) y tabla de intervención (filas con responsable/plazo).
  - Botón exportar a **Markdown** y a Excel.
- En “Vista Trabajador”:
  - Mostrar Nivel de riesgo (ALTO/MEDIO-ALTO/…) + aceptabilidad + intervención, como en el ejemplo.

## Pruebas y verificación
- Unit tests backend:
  - Validación de ND con -10.
  - Clasificación NP/NR y aceptabilidad conforme a los rangos del TXT.
- Verificación de export:
  - Generar un Markdown de prueba y comparar estructura/encabezados/columnas contra el ejemplo.

## Notas de compatibilidad
- Mantendré los campos actuales y agregaré los nuevos de forma **retrocompatible** (nullable) para no romper profesiogramas existentes.
- Donde el TXT tiene inconsistencias internas, priorizaré que las **etiquetas mostradas** coincidan con el ejemplo (p.ej., “NR 1.440 → ALTO” y “NR 200 → MEDIO-ALTO”) para que el reporte quede igual.
