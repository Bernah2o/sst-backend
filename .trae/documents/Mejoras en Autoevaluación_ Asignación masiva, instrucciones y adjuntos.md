Voy a implementar las funcionalidades solicitadas para el módulo de Autoevaluación de Trabajo en Casa.

### Plan de Implementación

#### 1. Backend (Asignación Masiva)
*   **Investigación:** Analizaré `app/api/enrollments.py` para entender cómo funciona la asignación masiva actual.
*   **Nuevo Endpoint (`app/api/assessments.py`):** Implementaré un endpoint `POST /assessments/homework/assign-bulk` que permita asignar la autoevaluación a múltiples trabajadores.
    *   Este endpoint creará registros "pendientes" en la tabla `homework_assessments` (o utilizará una lógica de "disponibilidad" si no se crean registros previos, pero la asignación sugiere crear registros vacíos o notificaciones).
    *   *Mejor enfoque:* Dado que el modelo actual `HomeworkAssessment` representa una evaluación *realizada*, crearé un mecanismo para "solicitar" la evaluación. Podría ser simplemente una notificación o un registro de "estado" de cumplimiento. Sin embargo, para mantenerlo simple y alineado con la solicitud, **crearé registros en estado "pendiente"** (necesitaré agregar un campo de estado al modelo o usar la fecha de evaluación como nula/futura).
    *   *Alternativa:* Agregar un campo `status` (PENDING, COMPLETED) al modelo `HomeworkAssessment`.

#### 2. Backend (Actualización de Modelo y Template)
*   **Modelo (`HomeworkAssessment`):**
    *   Agregaré campo `home_address` (Dirección de trabajo remoto).
    *   Agregaré campo `status` (Enum: PENDING, COMPLETED) para soportar la asignación previa.
    *   Agregaré campos para adjuntar documentos (URLs a Contabo Storage).
*   **Template HTML (`homework_assessment.html`):**
    *   Incorporaré las **Instrucciones** solicitadas en la parte superior.
    *   Incorporaré la **Declaración del Trabajador** completa solicitada.
    *   Mostraré la `home_address` en la sección de información.
    *   Añadiré la sección de **Adjuntos** para listar los documentos/fotos subidos.

#### 3. Frontend (`HomeworkAssessment.tsx`)
*   **Campo Dirección:** Agregaré un campo de texto editable para `home_address` (prellenado con la dirección del trabajador, pero modificable).
*   **Instrucciones:** Mostraré el texto de instrucciones al inicio del formulario.
*   **Declaración:** Actualizaré el texto de la declaración al final antes de la firma.
*   **Subida de Archivos:**
    *   Implementaré la subida de archivos para las 4 fotos requeridas.
    *   Usaré un servicio de subida (necesitaré verificar si existe un endpoint de upload genérico o crear uno específico para esto que conecte con Contabo/S3).

#### 4. Frontend (Asignación - Nueva Página o Modal)
*   Crearé una interfaz para que el admin/supervisor pueda seleccionar múltiples trabajadores y "Asignar Autoevaluación".
*   Esto podría ser una acción en la lista de trabajadores (`Worker.tsx`) o una página dedicada en `HomeworkAssessment.tsx` (vista admin).

### Confirmación del Plan
El plan implica modificar la base de datos (nuevos campos), la API, el frontend y la plantilla PDF. ¿Estás de acuerdo con proceder con estos cambios?