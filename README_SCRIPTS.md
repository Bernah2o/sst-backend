# Scripts Unificados - SST Backend

Este documento describe los 4 scripts principales que simplifican la gestión del proyecto SST Backend.

## Resumen de Scripts

| Script | Propósito | Comandos Principales |
|--------|-----------|---------------------|
| `admin.py` | Gestión de administradores y roles | `setup`, `create`, `roles`, `default` |
| `migrate.py` | Migraciones y desarrollo | `setup`, `upgrade`, `server`, `status` |
| `backup.py` | Respaldos de base de datos | `create`, `list`, `verify`, `clean` |
| `database.py` | Verificación y mantenimiento | `health`, `tables`, `stats`, `check` |

## 1. admin.py - Gestión de Administradores

### Comandos Disponibles

```bash
# Configuración completa (recomendado para inicio)
python admin.py setup

# Crear roles del sistema por defecto
python admin.py roles

# Crear administrador por defecto
python admin.py default

# Crear administrador personalizado (interactivo)
python admin.py create
```

### Funcionalidades
- ✅ Creación de roles del sistema (admin, instructor, employee)
- ✅ Administrador por defecto con credenciales predefinidas
- ✅ Creación interactiva de administradores personalizados
- ✅ Validación de contraseñas seguras
- ✅ Verificación de usuarios existentes

## 2. migrate.py - Migraciones y Desarrollo

### Comandos Disponibles

```bash
# Configuración inicial de base de datos
python migrate.py setup

# Migraciones
python migrate.py upgrade [--env production]
python migrate.py downgrade [--env production]
python migrate.py current [--env production]
python migrate.py history [--env production]
python migrate.py revision -m "descripción" [--env production]

# Servidor de desarrollo
python migrate.py server [--env local|production]

# Estado del proyecto
python migrate.py status
```

### Funcionalidades
- ✅ Configuración automática de base de datos local
- ✅ Gestión completa de migraciones Alembic
- ✅ Servidor de desarrollo con recarga automática
- ✅ Soporte para múltiples entornos (local/producción)
- ✅ Verificación de estado del proyecto
- ✅ Detección automática de Poetry

## 3. backup.py - Respaldos de Base de Datos

### Comandos Disponibles

```bash
# Crear respaldos
python backup.py create [--env local|production]
python backup.py create --table nombre_tabla

# Gestión de respaldos
python backup.py list
python backup.py clean [--keep 7]
python backup.py verify [archivo.sql.gz]
```

### Funcionalidades
- ✅ Respaldos completos de base de datos
- ✅ Respaldos de tablas específicas
- ✅ Compresión automática con gzip
- ✅ Rotación automática de respaldos antiguos
- ✅ Verificación de integridad
- ✅ Soporte para entornos local y producción
- ✅ Logs detallados de operaciones

## 4. database.py - Verificación y Mantenimiento

### Comandos Disponibles

```bash
# Verificación
python database.py check [--env local|production]
python database.py health [--env local|production]

# Información
python database.py tables [--env local|production]
python database.py structure --table nombre_tabla [--env local|production]
python database.py stats [--env local|production]

# Mantenimiento (solo local)
python database.py optimize --env local
```

### Funcionalidades
- ✅ Verificación de conexión a base de datos
- ✅ Listado de todas las tablas
- ✅ Estructura detallada de tablas específicas
- ✅ Estadísticas de la base de datos
- ✅ Verificación completa de salud
- ✅ Optimización y limpieza (solo entorno local)
- ✅ Soporte para múltiples entornos

## Flujo de Trabajo Recomendado

### Configuración Inicial (Primera vez)

```bash
# 1. Configurar administradores y roles
python admin.py setup

# 2. Configurar base de datos local
python migrate.py setup

# 3. Verificar que todo esté funcionando
python database.py health
python migrate.py status
```

### Desarrollo Diario

```bash
# 1. Iniciar servidor de desarrollo
python migrate.py server

# 2. Cuando hagas cambios en modelos, crear migración
python migrate.py revision -m "descripción del cambio"

# 3. Aplicar migración localmente
python migrate.py upgrade

# 4. Verificar estado
python database.py health
```

### Despliegue a Producción

```bash
# 1. Crear respaldo de seguridad
python backup.py create --env production

# 2. Verificar estado actual
python migrate.py current --env production

# 3. Aplicar migraciones
python migrate.py upgrade --env production

# 4. Verificar que todo funcione
python database.py health --env production
```

### Mantenimiento Regular

```bash
# Verificar estado general
python migrate.py status
python database.py stats

# Limpiar respaldos antiguos
python backup.py clean

# Verificar integridad de respaldos
python backup.py verify

# Optimizar base de datos local
python database.py optimize --env local
```

## Variables de Entorno

Los scripts utilizan automáticamente los archivos de configuración:

- **Local**: `.env.local` (PostgreSQL 14, puerto 8000)
- **Producción**: `.env.production` (PostgreSQL 17, servidor remoto)

## Características Técnicas

### Seguridad
- ✅ Validación de contraseñas seguras
- ✅ Verificación de conexiones antes de operaciones
- ✅ Confirmación para operaciones críticas en producción
- ✅ Logs detallados sin exponer credenciales

### Robustez
- ✅ Manejo de errores con mensajes claros
- ✅ Timeouts para operaciones de base de datos
- ✅ Verificación de dependencias (Poetry, PostgreSQL)
- ✅ Rollback automático en caso de errores

### Usabilidad
- ✅ Interfaz de línea de comandos intuitiva
- ✅ Mensajes de ayuda detallados (`--help`)
- ✅ Colores y formato para mejor legibilidad
- ✅ Confirmaciones interactivas cuando es necesario

## Migración desde Scripts Antiguos

Si vienes de usar los scripts en `scripts/`, aquí está la equivalencia:

| Script Antiguo | Script Nuevo | Comando |
|----------------|--------------|----------|
| `scripts/admin/create_default_roles.py` | `admin.py` | `python admin.py roles` |
| `scripts/admin/create_default_admin.py` | `admin.py` | `python admin.py default` |
| `scripts/admin/create_admin.py` | `admin.py` | `python admin.py create` |
| `scripts/migrations/setup_local_db.py` | `migrate.py` | `python migrate.py setup` |
| `scripts/migrations/dev_commands.py` | `migrate.py` | `python migrate.py [comando]` |
| `scripts/backup/backup_database.py` | `backup.py` | `python backup.py create` |
| `scripts/database/check_production_db.py` | `database.py` | `python database.py health` |

## Soporte y Solución de Problemas

Para obtener ayuda con cualquier script:

```bash
python admin.py --help
python migrate.py --help
python backup.py --help
python database.py --help
```

Para problemas específicos, consulta `README_ENTORNOS.md` o ejecuta:

```bash
python migrate.py status
python database.py health
```