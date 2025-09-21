# Script de Despliegue Automatizado - SST Platform

## 📋 Descripción

Este script automatiza completamente el proceso de despliegue de la plataforma SST tanto en entornos locales como de producción. Detecta automáticamente el entorno y ejecuta todas las tareas necesarias para aplicar cambios y nuevas funcionalidades de manera consistente y segura.

## 🚀 Características Principales

- ✅ **Detección automática de entorno** (local/producción)
- ✅ **Migraciones de base de datos automáticas**
- ✅ **Actualización de dependencias** (Python y Node.js)
- ✅ **Build automático del frontend**
- ✅ **Reinicio inteligente de servicios**
- ✅ **Validaciones y rollback automático** en caso de errores
- ✅ **Logs detallados** de todo el proceso
- ✅ **Backups automáticos** antes del despliegue
- ✅ **Inicialización de base de datos** con datos por defecto

## 📦 Prerequisitos

### Entorno Local
- Python 3.8+
- pip
- Node.js 16+ (si existe frontend)
- npm (si existe frontend)

### Entorno de Producción
- Docker
- Docker Compose
- Todos los prerequisitos del entorno local

## 🛠️ Instalación

1. El script ya está incluido en el proyecto en `sst-backend/deploy.py`
2. Asegúrate de tener todos los prerequisitos instalados
3. ¡Listo para usar!

## 📖 Uso

### Comandos Básicos

```bash
# Despliegue completo (detecta entorno automáticamente)
python deploy.py

# Forzar entorno específico
python deploy.py --env local
python deploy.py --env production

# Solo verificar prerequisitos
python deploy.py --check
```

### Comandos Específicos

```bash
# Solo actualizar dependencias
python deploy.py --deps-only

# Solo ejecutar migraciones de base de datos
python deploy.py --migrate-only

# Solo hacer build del frontend
python deploy.py --build-only

# Solo reiniciar servicios
python deploy.py --restart-only

# Ejecutar rollback al estado anterior
python deploy.py --rollback
```

### Ejemplos de Uso Común

#### 1. Despliegue después de nuevas funcionalidades
```bash
# Ejecuta todo el proceso: dependencias, migraciones, build, restart
python deploy.py
```

#### 2. Solo aplicar cambios de base de datos
```bash
# Útil cuando solo hay cambios en modelos/migraciones
python deploy.py --migrate-only
```

#### 3. Solo actualizar dependencias
```bash
# Útil cuando se agregaron nuevas librerías
python deploy.py --deps-only
```

#### 4. Rollback en caso de problemas
```bash
# Restaura el estado anterior automáticamente
python deploy.py --rollback
```

## 🔄 Proceso de Despliegue

El script ejecuta los siguientes pasos en orden:

1. **Verificación de Prerequisitos**
   - Verifica que todas las herramientas necesarias estén instaladas
   - Muestra las versiones de cada herramienta

2. **Creación de Backup**
   - Respalda archivos de configuración
   - Respalda base de datos (en entorno local)
   - Guarda estado del deployment

3. **Actualización de Dependencias**
   - Backend: `pip install -r requirements.txt`
   - Frontend: `npm ci` (si existe)
   - En producción: rebuild de contenedores Docker

4. **Migraciones de Base de Datos**
   - Ejecuta `alembic upgrade head`
   - En producción: ejecuta dentro del contenedor

5. **Inicialización de Base de Datos**
   - Crea roles por defecto
   - Crea usuario administrador por defecto

6. **Build del Frontend**
   - Ejecuta `npm run build` (si existe frontend)

7. **Reinicio de Servicios**
   - Local: auto-reload automático
   - Producción: `docker-compose down && docker-compose up -d`

8. **Verificación del Despliegue**
   - Verifica que el backend responda
   - Verifica que el frontend responda (en producción)

## 🌍 Detección de Entorno

El script detecta automáticamente el entorno basándose en:

1. **Variables de entorno:**
   - `ENVIRONMENT=production`
   - `NODE_ENV=production`

2. **Archivos del sistema:**
   - Presencia de `/.dockerenv` (contenedor Docker)
   - Existencia de `docker-compose.prod.yml`

3. **Por defecto:** Asume entorno local

## 📁 Estructura de Backups

Los backups se crean en `backups/YYYYMMDD_HHMMSS/`:

```
backups/
└── 20240115_143022/
    ├── .env                    # Variables de entorno
    ├── requirements.txt        # Dependencias Python
    ├── alembic.ini            # Configuración Alembic
    ├── sst_platform.db        # Base de datos (local)
    ├── frontend_package.json  # Dependencias frontend
    └── deployment_state.json  # Estado del deployment
```

## 🚨 Manejo de Errores

### Rollback Automático
Si cualquier paso falla, el script:
1. Muestra el error detallado
2. Inicia rollback automático
3. Restaura el estado anterior
4. Reinicia los servicios

### Logs Detallados
- Todos los comandos ejecutados se registran
- Los logs se guardan en `deploy.log`
- Output colorizado en terminal para fácil lectura

## 🔧 Configuración Avanzada

### Variables de Entorno Soportadas

```bash
# Forzar entorno de producción
export ENVIRONMENT=production

# Configuración de Node.js
export NODE_ENV=production

# Timeout personalizado (segundos)
export DEPLOY_TIMEOUT=600
```

### Personalización del Script

El script está diseñado para ser fácilmente extensible. Puedes:

1. Agregar nuevos pasos en el método `deploy()`
2. Modificar la detección de entorno en `_detect_environment()`
3. Personalizar los comandos en cada método específico

## 📊 Códigos de Salida

- `0`: Éxito
- `1`: Error durante el proceso
- `2`: Prerequisitos faltantes
- `3`: Error en rollback

## 🔍 Troubleshooting

### Problemas Comunes

#### 1. "No permission to operate files"
```bash
# Ejecutar desde el directorio correcto
cd sst-backend
python deploy.py
```

#### 2. "Command not found"
```bash
# Verificar prerequisitos
python deploy.py --check
```

#### 3. "Timeout en comando"
```bash
# Aumentar timeout o verificar conectividad
export DEPLOY_TIMEOUT=900
python deploy.py
```

#### 4. "Error en migraciones"
```bash
# Verificar configuración de Alembic
python deploy.py --migrate-only
```

### Logs de Debug

Para obtener más información sobre errores:

```bash
# Ver logs detallados
tail -f deploy.log

# Ejecutar con más verbosidad
python deploy.py --check
```

## 🤝 Contribución

Para contribuir al script:

1. Mantén la compatibilidad con ambos entornos (local/producción)
2. Agrega logs apropiados para cada operación
3. Incluye manejo de errores y rollback
4. Actualiza esta documentación

## 📞 Soporte

Si encuentras problemas:

1. Revisa los logs en `deploy.log`
2. Ejecuta `python deploy.py --check` para verificar prerequisitos
3. Intenta rollback: `python deploy.py --rollback`
4. Contacta al equipo de desarrollo

---

## 🎯 Casos de Uso Específicos

### Desarrollo Local Diario
```bash
# Después de hacer cambios en el código
python deploy.py --deps-only    # Si agregaste dependencias
python deploy.py --migrate-only # Si cambiaste modelos
```

### Despliegue a Producción
```bash
# Proceso completo con verificaciones
python deploy.py --env production
```

### Mantenimiento
```bash
# Solo actualizar dependencias sin cambios de código
python deploy.py --deps-only

# Solo reiniciar servicios
python deploy.py --restart-only
```

### Emergencias
```bash
# Rollback rápido
python deploy.py --rollback
```

¡El script está diseñado para hacer tu vida más fácil! 🚀