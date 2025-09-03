# Configuración de Entornos de Desarrollo

Este documento explica cómo trabajar con múltiples entornos (local y producción) en el proyecto SST Backend.

## Archivos de Configuración

### `.env.local` - Entorno de Desarrollo Local
- Base de datos: PostgreSQL 14 local (`bd_sst_local`)
- Puerto: 8000
- Configuración para desarrollo y pruebas

### `.env.production` - Entorno de Producción
- Base de datos: PostgreSQL 17 en servidor remoto
- Configuración para producción

## Scripts Unificados

**Nota**: Los scripts han sido simplificados en 4 archivos principales en la raíz del proyecto para mayor facilidad de uso.

### 1. `admin.py` - Gestión de Administradores y Roles
```bash
# Crear roles del sistema por defecto
python admin.py roles

# Crear administrador por defecto
python admin.py default

# Crear administrador personalizado (interactivo)
python admin.py create

# Configuración completa (roles + admin por defecto)
python admin.py setup
```

### 2. `migrate.py` - Migraciones y Base de Datos
```bash
# Configurar base de datos local
python migrate.py setup

# Aplicar migraciones
python migrate.py upgrade
python migrate.py upgrade --env production

# Crear nueva migración
python migrate.py revision -m "descripcion"

# Ver estado de migraciones
python migrate.py current
python migrate.py history

# Ejecutar servidor de desarrollo
python migrate.py server --env local
python migrate.py server --env production

# Ver estado del proyecto
python migrate.py status
```

### 3. `backup.py` - Respaldos de Base de Datos
```bash
# Crear respaldo completo
python backup.py create
python backup.py create --env production

# Respaldar tabla específica
python backup.py create --table usuarios

# Listar respaldos disponibles
python backup.py list

# Limpiar respaldos antiguos
python backup.py clean

# Verificar integridad de respaldos
python backup.py verify
```

### 4. `database.py` - Verificación y Mantenimiento
```bash
# Verificar conexión a la base de datos
python database.py check

# Listar todas las tablas
python database.py tables

# Ver estructura de una tabla específica
python database.py structure --table usuarios

# Obtener estadísticas de la base de datos
python database.py stats

# Verificación completa de salud
python database.py health

# Limpiar y optimizar (solo local)
python database.py optimize --env local
```

## Comandos de Alembic por Entorno

### Entorno Local
```bash
# Configurar variable de entorno
set ENV_FILE=.env.local

# Ver estado actual
alembic current

# Aplicar migraciones
alembic upgrade head

# Crear nueva migración
alembic revision --autogenerate -m "descripcion"

# Ver historial
alembic history
```

### Entorno de Producción
```bash
# Configurar variable de entorno
set ENV_FILE=.env.production

# Ver estado actual
alembic current

# Aplicar migraciones (¡CUIDADO!)
alembic upgrade head
```

## Flujo de Trabajo Recomendado

### 1. Configuración Inicial
```bash
# 1. Configuración completa (roles + admin por defecto)
python admin.py setup

# 2. Configurar base de datos local
python migrate.py setup

# 3. Verificar configuración
python migrate.py status
python database.py health
```

### 2. Desarrollo Local
```bash
# 1. Ejecutar servidor local
python migrate.py server --env local
# O manualmente:
uvicorn app.main:app --reload --env-file .env.local

# 2. Crear migraciones cuando sea necesario
python migrate.py revision -m "descripcion del cambio"

# 3. Aplicar migraciones localmente
python migrate.py upgrade
```

### 3. Despliegue a Producción
```bash
# 1. Crear respaldo antes de cambios
python backup.py create --env production

# 2. Verificar estado de producción
python migrate.py current --env production

# 3. Aplicar migraciones a producción (¡CUIDADO!)
python migrate.py upgrade --env production

# 4. Verificar que todo funcione
python database.py health --env production
```

## Estructura de Base de Datos

### Base de Datos Local (`bd_sst_local`)
- PostgreSQL 14
- 37 tablas (incluyendo `programas` y `admin_config`)
- Datos de prueba y desarrollo

### Base de Datos de Producción
- PostgreSQL 17
- 37 tablas (incluyendo `programas` y `admin_config`)
- Datos reales de producción

## Verificación de Tablas

```bash
# Verificar tablas locales y de producción
python database.py health
python database.py health --env production

# Listar todas las tablas
python database.py tables

# Ver estadísticas de la base de datos
python database.py stats
```

## Notas Importantes

1. **Siempre desarrollar en local primero**: Nunca hacer cambios directamente en producción
2. **Usar migraciones**: Todos los cambios de esquema deben hacerse a través de migraciones de Alembic
3. **Verificar antes de aplicar**: Siempre revisar las migraciones antes de aplicarlas a producción
4. **Backup**: Hacer backup de la base de datos de producción antes de aplicar migraciones importantes

## Solución de Problemas

### Error de codificación en Windows
Si aparecen errores de codificación con emojis, los scripts ya están configurados para usar texto simple.

### Tabla faltante
Si falta alguna tabla, verificar con:
```bash
python database.py health
python database.py tables
```

Para crear tablas manualmente, aplicar migraciones:
```bash
python migrate.py upgrade
```

### Migración no aplicada
Verificar el estado de Alembic y aplicar migraciones específicas:
```bash
python migrate.py current
python migrate.py history
python migrate.py upgrade
```