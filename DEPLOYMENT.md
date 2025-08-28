# Guía de Despliegue con Migraciones

Esta guía describe el proceso robusto para desplegar la aplicación SST Platform con manejo controlado de migraciones de base de datos.

## 🔧 Cambios Implementados

### 1. Configuración de Base de Datos Optimizada

- **Echo SQL deshabilitado en producción**: Solo se activa con `SQL_ECHO=true` en desarrollo
- **Pool de conexiones optimizado**: Configuración específica para PostgreSQL
- **Verificación de conexiones**: `pool_pre_ping=True` para validar conexiones
- **Reciclaje de conexiones**: Cada hora para evitar conexiones obsoletas

### 2. Eliminación de Migraciones Automáticas

- **Removido `create_tables()`** del ciclo de vida de la aplicación
- **Sin migraciones automáticas** al iniciar la aplicación
- **Control manual** de cuándo y cómo ejecutar migraciones

### 3. Script de Migración Dedicado

- **`migrate.py`**: Script robusto para manejar migraciones
- **Validaciones de seguridad**: Verificación de conexión antes de migrar
- **Logging detallado**: Seguimiento completo del proceso
- **Manejo de errores**: Recuperación graceful ante fallos

## 🚀 Proceso de Despliegue

### Opción 1: Despliegue Local/Desarrollo

```bash
# 1. Verificar estado actual de la base de datos
python migrate.py check

# 2. Ejecutar migraciones (si es necesario)
python migrate.py upgrade

# 3. Iniciar la aplicación
uvicorn app.main:app --reload
```

### Opción 2: Despliegue con Docker Compose

```bash
# 1. Construir y levantar servicios base (sin migraciones)
docker-compose up -d db redis

# 2. Ejecutar migraciones de forma controlada
docker-compose --profile migration up migrate

# 3. Verificar que las migraciones se ejecutaron correctamente
docker-compose logs migrate

# 4. Levantar la aplicación principal
docker-compose up -d app

# 5. (Opcional) Levantar servicios adicionales
docker-compose --profile production up -d
```

### Opción 3: Despliegue en Producción (Recomendado)

```bash
# 1. Backup de la base de datos
pg_dump -h localhost -U sst_user sst_platform > backup_$(date +%Y%m%d_%H%M%S).sql

# 2. Verificar estado actual
docker-compose exec app python migrate.py check

# 3. Ejecutar migraciones en modo de mantenimiento
docker-compose --profile migration up migrate

# 4. Verificar logs de migración
docker-compose logs migrate

# 5. Si todo está bien, reiniciar la aplicación
docker-compose restart app
```

## 📋 Comandos del Script de Migración

### Comandos Básicos

```bash
# Verificar estado de la base de datos
python migrate.py check

# Mostrar revisión actual
python migrate.py current

# Mostrar historial de migraciones
python migrate.py history

# Ejecutar todas las migraciones pendientes
python migrate.py upgrade

# Ejecutar solo la siguiente migración
python migrate.py upgrade +1

# Revertir la última migración (¡CUIDADO!)
python migrate.py downgrade -1
```

### Comandos Avanzados

```bash
# Migrar a una revisión específica
python migrate.py upgrade abc123

# Revertir a una revisión específica
python migrate.py downgrade def456

# Verificar migraciones pendientes
python migrate.py check
```

## 🔒 Variables de Entorno

### Desarrollo

```env
DEBUG=true
SQL_ECHO=true  # Para ver queries SQL
DATABASE_URL=postgresql://user:pass@localhost:5432/sst_dev
ENVIRONMENT=development
```

### Producción

```env
DEBUG=false
SQL_ECHO=false  # Deshabilitado para performance
DATABASE_URL=postgresql://user:pass@db:5432/sst_platform
ENVIRONMENT=production
LOG_LEVEL=INFO
```

## 🛡️ Mejores Prácticas

### Antes del Despliegue

1. **Backup de la base de datos**
   ```bash
   pg_dump -h localhost -U sst_user sst_platform > backup.sql
   ```

2. **Probar migraciones en staging**
   ```bash
   # En ambiente de staging
   python migrate.py check
   python migrate.py upgrade
   ```

3. **Revisar logs de migración**
   ```bash
   docker-compose logs migrate
   ```

### Durante el Despliegue

1. **Modo de mantenimiento** (si es necesario)
2. **Ejecutar migraciones** con el script dedicado
3. **Verificar estado** antes de continuar
4. **Rollback plan** en caso de problemas

### Después del Despliegue

1. **Verificar salud de la aplicación**
   ```bash
   curl -f http://localhost:8000/health
   ```

2. **Monitorear logs**
   ```bash
   docker-compose logs -f app
   ```

3. **Verificar funcionalidad crítica**

## 🚨 Solución de Problemas

### Error: "Alembic no está instalado"

```bash
# Instalar dependencias
poetry install
# o
pip install alembic
```

### Error: "No se puede conectar a la base de datos"

```bash
# Verificar que la base de datos esté corriendo
docker-compose ps db

# Verificar logs de la base de datos
docker-compose logs db

# Probar conexión manual
psql -h localhost -U sst_user -d sst_platform
```

### Error: "Migración falló"

```bash
# Ver logs detallados
python migrate.py check

# Verificar revisión actual
python migrate.py current

# Si es necesario, revertir
python migrate.py downgrade -1
```

### Logs de SQL aparecen en producción

```bash
# Verificar variables de entorno
echo $DEBUG
echo $SQL_ECHO

# Deben ser:
# DEBUG=false
# SQL_ECHO=false (o no definida)
```

## 📊 Monitoreo

### Verificar Estado de Migraciones

```bash
# Script de monitoreo
#!/bin/bash
echo "=== Estado de Migraciones ==="
docker-compose exec app python migrate.py current
echo "\n=== Verificación de Base de Datos ==="
docker-compose exec app python migrate.py check
```

### Logs Importantes

```bash
# Logs de migración
docker-compose logs migrate

# Logs de aplicación
docker-compose logs app | grep -E "(ERROR|WARNING|Migration)"

# Logs de base de datos
docker-compose logs db | tail -50
```

## 🔄 Rollback de Emergencia

En caso de problemas críticos:

```bash
# 1. Detener la aplicación
docker-compose stop app

# 2. Restaurar backup de base de datos
psql -h localhost -U sst_user -d sst_platform < backup.sql

# 3. Revertir a versión anterior del código
git checkout <previous-commit>

# 4. Reconstruir y desplegar
docker-compose build app
docker-compose up -d app
```

## 📝 Notas Adicionales

- **Nunca ejecutar migraciones automáticamente** en producción
- **Siempre hacer backup** antes de migraciones importantes
- **Probar en staging** antes de producción
- **Monitorear logs** durante y después del despliegue
- **Tener plan de rollback** preparado

---

**Importante**: Este proceso elimina las migraciones automáticas que causaban logs excesivos en producción y proporciona control total sobre cuándo y cómo se ejecutan las migraciones de base de datos.