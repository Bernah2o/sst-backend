# Administración de Notificaciones de Exámenes Ocupacionales

## Descripción

Esta funcionalidad permite a los administradores controlar y gestionar las notificaciones automáticas de exámenes ocupacionales, especialmente útil cuando se cargan trabajadores con fechas de ingreso anteriores que generarían notificaciones masivas.

## Problema Resuelto

Cuando se cargan trabajadores con fechas de ingreso de años anteriores, el sistema automáticamente les envía notificaciones de exámenes ocupacionales basándose en la periodicidad del cargo. Esto puede resultar en:

- Envío masivo de notificaciones a trabajadores que ya tienen exámenes al día
- Spam de correos electrónicos
- Confusión en los trabajadores
- Sobrecarga del sistema de notificaciones

## Funcionalidades Implementadas

### 1. Consulta de Estado de Notificaciones

**Endpoint:** `GET /admin/notifications/exam-notifications`

**Descripción:** Obtiene una lista completa de trabajadores con el estado de sus exámenes ocupacionales y notificaciones.

**Parámetros de consulta:**
- `skip`: Número de registros a omitir (paginación)
- `limit`: Número máximo de registros a retornar
- `exam_status`: Filtrar por estado del examen (`sin_examenes`, `vencido`, `proximo_a_vencer`, `al_dia`)
- `notification_status`: Filtrar por estado de notificación
- `position`: Filtrar por cargo
- `has_email`: Filtrar trabajadores con/sin email
- `acknowledged`: Filtrar por confirmación de notificaciones

**Ejemplo de respuesta:**
```json
[
  {
    "worker_id": 123,
    "worker_name": "Juan Pérez",
    "worker_document": "12345678",
    "worker_position": "Operario",
    "worker_email": "juan.perez@empresa.com",
    "last_exam_date": "2022-01-15",
    "next_exam_date": "2023-01-15",
    "days_until_exam": -30,
    "exam_status": "vencido",
    "periodicidad": "anual",
    "notification_status": "pending",
    "acknowledgment_count": 0,
    "can_send_notification": true,
    "notification_types_sent": [],
    "last_acknowledgment_date": null
  }
]
```

### 2. Envío Manual de Notificaciones

**Endpoint:** `POST /admin/notifications/send-notifications`

**Descripción:** Permite enviar notificaciones manuales a trabajadores específicos.

**Cuerpo de la petición:**
```json
{
  "worker_ids": [123, 456, 789],
  "notification_type": "reminder",
  "force_send": false
}
```

**Tipos de notificación:**
- `first_notification`: Primera notificación
- `reminder`: Recordatorio
- `overdue`: Examen vencido

**Parámetros:**
- `worker_ids`: Lista de IDs de trabajadores
- `notification_type`: Tipo de notificación a enviar
- `force_send`: Si es `true`, envía aunque ya haya confirmación

### 3. Supresión de Notificaciones

**Endpoint:** `POST /admin/notifications/suppress-notifications`

**Descripción:** Suprime notificaciones futuras para trabajadores específicos creando registros de confirmación automática.

**Cuerpo de la petición:**
```json
{
  "worker_ids": [123, 456],
  "notification_type": "reminder",
  "reason": "Trabajador ya tiene examen programado"
}
```

**Parámetros:**
- `worker_ids`: Lista de IDs de trabajadores
- `notification_type`: Tipo específico a suprimir (opcional, si no se especifica suprime todos)
- `reason`: Razón de la supresión (para auditoría)

### 4. Estadísticas de Notificaciones

**Endpoint:** `GET /admin/notifications/statistics`

**Descripción:** Proporciona estadísticas generales del sistema de notificaciones.

**Respuesta:**
```json
{
  "total_workers": 150,
  "workers_without_exams": 25,
  "workers_with_overdue_exams": 10,
  "workers_with_upcoming_exams": 30,
  "total_notifications_sent_today": 5,
  "total_acknowledgments_today": 3,
  "suppressed_notifications": 15
}
```

### 5. Consulta de Confirmaciones

**Endpoint:** `GET /admin/notifications/acknowledgments`

**Descripción:** Obtiene el historial de confirmaciones de notificaciones.

**Parámetros:**
- `worker_id`: Filtrar por trabajador específico
- `notification_type`: Filtrar por tipo de notificación
- `skip` y `limit`: Para paginación

### 6. Eliminación de Confirmaciones

**Endpoint:** `DELETE /admin/notifications/acknowledgments/{acknowledgment_id}`

**Descripción:** Elimina una confirmación específica, permitiendo que se envíen notificaciones nuevamente.

### 7. Acciones en Lote

**Endpoint:** `POST /admin/notifications/bulk-action`

**Descripción:** Ejecuta acciones en lote sobre múltiples trabajadores.

**Cuerpo de la petición:**
```json
{
  "action": "send",
  "worker_ids": [123, 456, 789],
  "notification_type": "reminder",
  "force": false,
  "reason": "Envío masivo programado"
}
```

**Acciones disponibles:**
- `send`: Enviar notificaciones
- `suppress`: Suprimir notificaciones

## Casos de Uso Comunes

### 1. Carga Masiva de Trabajadores Históricos

**Problema:** Se cargan 100 trabajadores con fechas de ingreso de 2020-2022.

**Solución:**
1. Consultar trabajadores con exámenes vencidos:
   ```bash
   GET /admin/notifications/exam-notifications?exam_status=vencido&limit=100
   ```

2. Revisar cuáles realmente necesitan notificaciones

3. Suprimir notificaciones para trabajadores que ya tienen exámenes programados:
   ```bash
   POST /admin/notifications/suppress-notifications
   {
     "worker_ids": [1, 2, 3, ...],
     "reason": "Trabajadores históricos con exámenes al día"
   }
   ```

### 2. Envío Controlado de Recordatorios

**Escenario:** Enviar recordatorios solo a trabajadores específicos.

**Proceso:**
1. Filtrar trabajadores próximos a vencer:
   ```bash
   GET /admin/notifications/exam-notifications?exam_status=proximo_a_vencer
   ```

2. Enviar notificaciones selectivas:
   ```bash
   POST /admin/notifications/send-notifications
   {
     "worker_ids": [10, 20, 30],
     "notification_type": "reminder"
   }
   ```

### 3. Gestión de Excepciones

**Escenario:** Un trabajador reporta que no debe recibir más notificaciones.

**Proceso:**
1. Suprimir todas las notificaciones:
   ```bash
   POST /admin/notifications/suppress-notifications
   {
     "worker_ids": [123],
     "reason": "Solicitud del trabajador - examen programado externamente"
   }
   ```

2. Si después necesita reactivar notificaciones:
   ```bash
   DELETE /admin/notifications/acknowledgments/{acknowledgment_id}
   ```

## Seguridad y Permisos

- **Acceso:** Solo usuarios con rol `admin` pueden acceder a estos endpoints
- **Auditoría:** Todas las acciones se registran con:
  - Usuario que ejecutó la acción
  - Timestamp
  - IP de origen
  - Razón de la acción

## Integración con el Sistema Existente

### Tabla `notification_acknowledgments`

La funcionalidad utiliza la tabla existente `notification_acknowledgments` para:
- Registrar confirmaciones manuales de administradores
- Controlar el envío de notificaciones automáticas
- Mantener auditoría de acciones

### Compatibilidad

- **Notificaciones automáticas:** El scheduler diario respeta las confirmaciones creadas por esta funcionalidad
- **Confirmaciones de trabajadores:** Las confirmaciones manuales de trabajadores (vía email) coexisten con las administrativas
- **Tipos de notificación:** Se mantiene la diferenciación entre `first_notification`, `reminder` y `overdue`

## Monitoreo y Mantenimiento

### Estadísticas Recomendadas

1. **Diarias:**
   - Número de notificaciones enviadas
   - Número de confirmaciones recibidas
   - Trabajadores con exámenes vencidos

2. **Semanales:**
   - Tendencia de exámenes próximos a vencer
   - Efectividad de las notificaciones (confirmaciones vs envíos)

3. **Mensuales:**
   - Trabajadores sin exámenes
   - Análisis de supresiones administrativas

### Limpieza de Datos

**Recomendación:** Revisar periódicamente las confirmaciones administrativas para:
- Eliminar supresiones temporales que ya no son necesarias
- Reactivar notificaciones para trabajadores que requieren seguimiento

## Script de Prueba

Se incluye el archivo `test_admin_notifications.py` que demuestra:
- Autenticación como administrador
- Consulta de notificaciones
- Envío manual de notificaciones
- Supresión de notificaciones
- Consulta de estadísticas

**Uso:**
```bash
python test_admin_notifications.py
```

## Credenciales de Administrador

**Email:** admin@sst.com  
**Contraseña:** Admin123!

## Consideraciones Técnicas

### Performance

- Las consultas están optimizadas con índices en las tablas relacionadas
- La paginación está implementada para manejar grandes volúmenes de datos
- Los filtros permiten consultas específicas para reducir la carga

### Escalabilidad

- Los endpoints soportan procesamiento en lote
- Las acciones masivas están limitadas para evitar timeouts
- Se recomienda procesar en lotes de máximo 100 trabajadores

### Logging

- Todas las acciones se registran en los logs de la aplicación
- Los errores incluyen contexto suficiente para debugging
- Las confirmaciones administrativas se marcan claramente en la auditoría

## Próximas Mejoras

1. **Dashboard Web:** Interfaz gráfica para administradores
2. **Programación de Envíos:** Capacidad de programar notificaciones para fechas específicas
3. **Plantillas Personalizadas:** Diferentes plantillas según el tipo de trabajador
4. **Integración con Calendario:** Sincronización con sistemas de calendario corporativo
5. **Reportes Avanzados:** Análisis de tendencias y efectividad de notificaciones