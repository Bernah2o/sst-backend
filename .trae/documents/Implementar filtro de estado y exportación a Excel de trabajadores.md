Voy a implementar el filtro por estado y la exportación a Excel para los trabajadores.

### Plan de Implementación

#### 1. Backend (`app/api/workers.py`)
*   **Nuevo Endpoint de Exportación:** Crearé un endpoint `GET /workers/export/excel` que generará un archivo `.xlsx`.
    *   Este endpoint aceptará los mismos filtros que la lista (`search`, `is_active`).
    *   Utilizará `openpyxl` para generar el archivo con las columnas: Tipo Doc, Documento, Nombre Completo, Email, Cargo, Departamento, Ciudad, Fecha Ingreso, Estado, etc.

#### 2. Frontend (`src/pages/Worker.tsx`)
*   **Nuevo Filtro de Estado:**
    *   Agregaré un estado `filterStatus` ('all', 'active', 'inactive').
    *   Incorporaré un selector (Dropdown) en la barra de herramientas para filtrar por "Todos", "Activos" e "Inactivos".
    *   Actualizaré la función `fetchWorkers` para enviar el parámetro `is_active` al backend según la selección.
*   **Botón de Exportación:**
    *   Agregaré un botón "Exportar Excel" con el icono de descarga.
    *   Implementaré la función `handleExportExcel` que llamará al nuevo endpoint y descargará el archivo generado.

### Confirmación
Por favor, confirma si estás de acuerdo con este plan para proceder con los cambios.