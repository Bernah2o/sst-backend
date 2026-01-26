## Enfoque
- Usar el generador existente [HTMLToPDFConverter](file:///e:/DH2OCOL/python/sst-app/sst-backend/app/services/html_to_pdf.py) (WeasyPrint) porque ya está en dependencias y ya soporta logo en base64 desde `app/templates/reports/logo_3.png`.
- Crear una plantilla HTML/CSS nueva para el PDF del profesiograma por cargo y exponer un endpoint de descarga.

## 1) Plantilla del reporte (HTML + CSS)
- Crear `app/templates/reports/profesiograma_report.html`.
  - Encabezado con logo usando `data:image/png;base64,{{ logo_base64 }}`.
  - Secciones mínimas:
    - Datos del cargo y versión del profesiograma.
    - Cabecera (empresa/departamento/código cargo/nº expuestos/fechas/firmas si existen).
    - Periodicidad EMO y `justificacion_periodicidad_emo`.
    - Tabla de peligros (factores) con columnas clave (proceso/actividad/tarea, nivel exposición, ND/NE/NP/Interpretación, NC/NR/Nivel/Color/Acción/Aceptabilidad, controles existentes, peor consecuencia, requisito legal).
    - (Opcional) Subtablas por factor para ESIAE e Intervenciones si existen.
- Crear `app/templates/reports/css/profesiograma_report.css` siguiendo el estilo de [occupational_exam_report.css](file:///e:/DH2OCOL/python/sst-app/sst-backend/app/templates/reports/css/occupational_exam_report.css).

## 2) Servicio/función de generación PDF
- Agregar una función en `app/services` (p.ej. `app/services/profesiograma_pdf.py`) que:
  - Reciba el `Profesiograma` y el `Cargo` (y opcionalmente el `converter`).
  - Construya el `context` para la plantilla (incluye `logo_base64` desde `HTMLToPDFConverter._load_logo_base64()` y `generated_at`).
  - Genere bytes PDF vía `generate_pdf_from_template("profesiograma_report.html", context)`.

## 3) Endpoint de descarga por cargo
- En [profesiogramas.py](file:///e:/DH2OCOL/python/sst-app/sst-backend/app/api/profesiogramas.py) agregar endpoint:
  - `GET /api/v1/profesiogramas/cargos/{cargo_id}/export/profesiograma.pdf`
  - Lógica de selección del profesiograma:
    - Preferir el `estado=ACTIVO` del cargo.
    - Si no existe, tomar el último por `fecha_creacion DESC`.
  - Responder como `StreamingResponse` (`application/pdf`) con `Content-Disposition` para descarga.
  - Nombre sugerido: `Profesiograma_{cargo_nombre}_{version}_{YYYYMMDD}.pdf`.

## 4) Pruebas
- Añadir test unitario nuevo (sin render real de WeasyPrint para evitar lentitud):
  - Mock de `HTMLToPDFConverter.generate_pdf_from_template` retornando bytes que inician con `%PDF`.
  - Validar:
    - Selección de profesiograma (activo vs último).
    - Que el endpoint retorna `application/pdf` y header `Content-Disposition`.

## 5) (Opcional) Botón en frontend
- Si quieres el botón en UI, se agregaría un botón “Descargar PDF” en la pantalla de profesiogramas por cargo que llame a este endpoint.

## Resultado
- Un botón/URL que descarga el PDF del profesiograma del cargo con el logo `app/templates/reports/logo_3.png` embebido y el contenido en formato legible para auditoría.