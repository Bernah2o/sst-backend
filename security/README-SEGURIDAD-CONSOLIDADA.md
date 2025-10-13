# Configuración de Seguridad Consolidada

## 🔒 Descripción

Esta configuración integra todas las mejoras de seguridad directamente en el archivo principal `docker-compose.yml`, eliminando la necesidad de múltiples archivos separados. Es **100% compatible** con GitHub Actions y Dockploy ya que utiliza únicamente imágenes oficiales de Docker Hub.

## 🏗️ Arquitectura Consolidada

### Servicios Integrados

1. **PostgreSQL Seguro** (`db`)
   - Imagen oficial: `postgres:17-alpine`
   - Configuración externa montada como volúmenes
   - Bind solo a localhost (`127.0.0.1:5432`)
   - IP fija para configuraciones de seguridad

2. **Fail2ban** (`fail2ban`)
   - Imagen oficial: `crazymax/fail2ban:latest`
   - Protección automática contra ataques
   - Configuración externa

3. **Monitor de Seguridad** (`security_monitor`)
   - Imagen oficial: `alpine:latest`
   - Monitoreo continuo de seguridad
   - Reportes automáticos

4. **Aplicaciones FastAPI** (`app1`, `app2`)
   - Sin cambios en la lógica
   - Conexión a PostgreSQL por IP fija

## 🚀 Implementación

### Opción 1: Actualización Automática

```bash
# Ejecutar script de actualización
chmod +x update-to-secure.sh
./update-to-secure.sh
```

### Opción 2: Despliegue Manual

```bash
# 1. Crear directorios necesarios
mkdir -p data/{postgres_logs,fail2ban,security_reports}

# 2. Configurar variables de entorno
export DB_PASSWORD="tu_password_seguro"
export SECRET_KEY="tu_secret_key"

# 3. Iniciar servicios
docker-compose up -d

# 4. Verificar estado
docker-compose ps
```

### Opción 3: Integración con Dockploy

La configuración es totalmente compatible con Dockploy:

1. **No requiere builds personalizados**
2. **Usa solo imágenes oficiales**
3. **Configuración externa por volúmenes**
4. **Compatible con GitHub Actions**

## 📁 Estructura de Archivos

```
sst-backend/
├── docker-compose.yml          # ✅ Configuración consolidada
├── security/                   # Configuraciones de seguridad
│   ├── postgresql.conf         # Configuración PostgreSQL
│   ├── pg_hba.conf            # Autenticación PostgreSQL
│   ├── init-scripts/          # Scripts de inicialización
│   ├── fail2ban/              # Configuración Fail2ban
│   ├── fail2ban-filters/      # Filtros personalizados
│   └── monitor-scripts/       # Scripts de monitoreo
├── data/                      # Datos persistentes
│   ├── postgres/              # Datos PostgreSQL
│   ├── postgres_logs/         # Logs PostgreSQL
│   ├── fail2ban/              # Datos Fail2ban
│   └── security_reports/      # Reportes de seguridad
└── update-to-secure.sh        # Script de actualización
```

## 🛡️ Protecciones Implementadas

### PostgreSQL Seguro
- ✅ Autenticación SCRAM-SHA-256
- ✅ SSL/TLS habilitado
- ✅ Logging de conexiones y consultas
- ✅ Límites de conexión configurados
- ✅ Bind solo a localhost
- ✅ Usuario con privilegios mínimos

### Fail2ban Integrado
- ✅ Protección contra fuerza bruta
- ✅ Detección de ataques DDoS
- ✅ Bloqueo automático de IPs maliciosas
- ✅ Filtros personalizados para PostgreSQL

### Monitoreo Continuo
- ✅ Análisis de logs en tiempo real
- ✅ Reportes de seguridad automáticos
- ✅ Alertas de actividad sospechosa
- ✅ Métricas de conexiones

## 🔧 Variables de Entorno

```bash
# Requeridas
DB_PASSWORD=tu_password_muy_seguro
SECRET_KEY=tu_secret_key_para_jwt

# Opcionales
DB_NAME=bd_sst
DB_USER=sstuser
ENVIRONMENT=production
LOG_LEVEL=WARNING
```

## 📊 Monitoreo y Verificación

### Comandos Útiles

```bash
# Estado de servicios
docker-compose ps

# Logs de seguridad
docker-compose logs fail2ban
docker-compose logs security_monitor

# Estado de Fail2ban
docker-compose exec fail2ban fail2ban-client status

# Conexión a PostgreSQL
docker-compose exec db psql -U sstuser -d bd_sst

# Ver reportes de seguridad
ls -la data/security_reports/
```

### Verificación de Seguridad

```bash
# Verificar configuración PostgreSQL
docker-compose exec db psql -U sstuser -d bd_sst -c "SHOW ssl;"
docker-compose exec db psql -U sstuser -d bd_sst -c "SHOW log_connections;"

# Verificar jails de Fail2ban
docker-compose exec fail2ban fail2ban-client status postgresql-auth
docker-compose exec fail2ban fail2ban-client status postgresql-ddos

# Ver conexiones activas
docker-compose exec db psql -U sstuser -d bd_sst -c "SELECT * FROM pg_stat_activity;"
```

## 🚨 Alertas y Notificaciones

El sistema genera alertas automáticas para:

- ✅ Intentos de autenticación fallidos
- ✅ Conexiones desde IPs sospechosas
- ✅ Ataques de fuerza bruta detectados
- ✅ Patrones de tráfico anómalos
- ✅ Errores de configuración

## 🔄 Mantenimiento

### Tareas Regulares

```bash
# Rotar logs (semanal)
docker-compose exec fail2ban fail2ban-client reload

# Limpiar reportes antiguos (mensual)
find data/security_reports/ -name "*.json" -mtime +30 -delete

# Actualizar filtros de Fail2ban
docker-compose restart fail2ban

# Verificar integridad de datos
docker-compose exec db pg_checksums -D /var/lib/postgresql/data/pgdata
```

### Backup de Configuración

```bash
# Backup completo de configuración
tar -czf security-config-backup-$(date +%Y%m%d).tar.gz security/

# Backup de datos críticos
docker-compose exec db pg_dump -U sstuser bd_sst > backup-$(date +%Y%m%d).sql
```

## 🆘 Solución de Problemas

### Problemas Comunes

1. **PostgreSQL no inicia**
   ```bash
   # Verificar permisos
   sudo chown -R 999:999 data/postgres_logs/
   
   # Verificar configuración
   docker-compose logs db
   ```

2. **Fail2ban no funciona**
   ```bash
   # Verificar privilegios
   docker-compose logs fail2ban
   
   # Reiniciar servicio
   docker-compose restart fail2ban
   ```

3. **Monitor no genera reportes**
   ```bash
   # Verificar scripts
   docker-compose exec security_monitor ls -la /scripts/
   
   # Ver logs del monitor
   docker-compose logs security_monitor
   ```

## 🔮 Ventajas de la Consolidación

### ✅ Beneficios

1. **Simplicidad**: Un solo archivo de configuración
2. **Compatibilidad**: 100% compatible con Dockploy/GitHub
3. **Mantenimiento**: Más fácil de mantener y actualizar
4. **Despliegue**: Proceso de despliegue simplificado
5. **Debugging**: Más fácil identificar problemas

### ✅ Vs. Archivos Separados

| Aspecto | Consolidado | Separado |
|---------|-------------|----------|
| Archivos | 1 archivo | 3+ archivos |
| Complejidad | Baja | Alta |
| Mantenimiento | Fácil | Complejo |
| Dockploy | ✅ Compatible | ❌ Problemas |
| GitHub Actions | ✅ Compatible | ❌ Builds custom |

## 📞 Soporte

Para problemas o mejoras:

1. Verificar logs: `docker-compose logs [servicio]`
2. Revisar configuración en `security/`
3. Ejecutar script de verificación
4. Consultar documentación de servicios

---

**Nota**: Esta configuración mantiene todas las funcionalidades de seguridad mientras simplifica significativamente el despliegue y mantenimiento.