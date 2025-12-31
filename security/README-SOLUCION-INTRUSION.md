# Solución para Intentos de Intrusión PostgreSQL

## Problema Identificado

Se detectaron múltiples intentos de autenticación fallidos en los logs de PostgreSQL:

```
2025-10-14 03:35:25.134 UTC [67920] FATAL:  password authentication failed for user "postgres"
2025-10-14 03:35:25.134 UTC [67920] DETAIL:  Role "postgres" does not exist.
```

## Causa Raíz

1. **Configuración de pg_hba.conf no aplicada**: PostgreSQL estaba usando la configuración por defecto en lugar de nuestro archivo personalizado.
2. **Filtros de fail2ban incorrectos**: Los filtros no coincidían con el formato real de los logs de PostgreSQL.
3. **Falta de reglas específicas**: No había reglas explícitas para rechazar usuarios comunes de ataques.

## Soluciones Implementadas

### 1. Configuración Mejorada de PostgreSQL

**Archivo modificado**: `docker-compose.yml`

- Se agregó comando específico para usar nuestros archivos de configuración
- Se habilitó logging detallado para mejor monitoreo
- Se configuró correctamente el archivo `pg_hba.conf`

### 2. pg_hba.conf Más Restrictivo

**Archivo modificado**: `security/pg_hba.conf`

- Reglas explícitas para rechazar usuarios comunes de ataques (`postgres`, `admin`, `root`, `user`, `test`)
- Rechazo de conexiones a bases de datos del sistema
- Solo permite conexiones desde redes Docker internas
- Todas las demás conexiones son rechazadas por defecto

### 3. Filtros de Fail2ban Corregidos

**Archivos modificados**:
- `security/fail2ban-filters/postgresql-auth.conf`
- `security/fail2ban-filters/postgresql-scan.conf`

- Patrones actualizados para coincidir con el formato real de logs de PostgreSQL
- Detección específica de usuarios comunes de ataques
- Compatibilidad con ambos formatos de log (estándar y extendido)

### 4. Monitoreo Mejorado

**Archivos modificados/creados**:
- `security/monitor-scripts/monitor-security.sh` (mejorado)
- `security/monitor-scripts/check-fail2ban.sh` (nuevo)

- Detección específica de intentos con usuarios inexistentes
- Alertas críticas para usuarios comunes de ataques
- Monitoreo de IPs sospechosas
- Script dedicado para gestión de fail2ban

## Instrucciones de Aplicación

### 1. Aplicar Cambios en Producción

```bash
# 1. Detener los servicios
docker-compose down

# 2. Aplicar los nuevos archivos de configuración
# (Los archivos ya están actualizados en el repositorio)

# 3. Reiniciar los servicios
docker-compose up -d

# 4. Verificar que PostgreSQL use la nueva configuración
docker logs sst_postgres | grep "pg_hba.conf"
```

### 2. Verificar Fail2ban

```bash
# Verificar estado de fail2ban
./security/monitor-scripts/check-fail2ban.sh status

# Si fail2ban no está funcionando, reiniciarlo
./security/monitor-scripts/check-fail2ban.sh restart
```

### 3. Monitorear Seguridad

```bash
# Ejecutar monitoreo manual
./security/monitor-scripts/monitor-security.sh --check

# Ver logs de seguridad
docker logs sst_security_monitor
```

## Verificación de la Solución

### 1. Verificar Configuración de PostgreSQL

```bash
# Conectarse al contenedor de PostgreSQL
docker exec -it sst_postgres sh

# Verificar que use nuestro pg_hba.conf
cat /etc/postgresql/pg_hba.conf

# Verificar logs
tail -f /var/log/postgresql/postgresql-*.log
```

### 2. Probar Fail2ban

```bash
# Ver estado de las jails
docker exec sst_fail2ban fail2ban-client status

# Ver IPs baneadas
docker exec sst_fail2ban fail2ban-client status postgresql-auth
```

### 3. Monitorear Intentos de Intrusión

```bash
# Ver intentos recientes
grep "password authentication failed" /path/to/postgres/logs/*.log | tail -20

# Verificar que fail2ban esté detectando
docker exec sst_fail2ban fail2ban-client status postgresql-scan
```

## Resultados Esperados

Después de aplicar estas mejoras:

1. **Reducción drástica de intentos exitosos**: Los intentos con usuarios inexistentes serán rechazados inmediatamente por pg_hba.conf
2. **Detección automática**: Fail2ban detectará y baneará IPs que intenten múltiples conexiones fallidas
3. **Alertas proactivas**: El sistema de monitoreo alertará sobre intentos de intrusión
4. **Logs más informativos**: Se registrarán todos los intentos de conexión para análisis

## Configuraciones Adicionales Recomendadas

### 1. Configurar Alertas por Email

Agregar notificaciones por email en fail2ban:

```ini
# En security/fail2ban/postgresql.conf
action = iptables-multiport[name=postgresql-auth, port="5432", protocol=tcp]
         sendmail-whois[name=postgresql-auth, dest=admin@dh2o.com.co]
```

### 2. Configurar Rate Limiting

Ajustar los parámetros de fail2ban según el tráfico:

```ini
# Para entornos de alto tráfico
maxretry = 3
findtime = 300
bantime = 7200
```

### 3. Monitoreo Continuo

Configurar cron job para monitoreo automático:

```bash
# Agregar a crontab
*/15 * * * * /path/to/security/monitor-scripts/monitor-security.sh --check
```

## Contacto y Soporte

Para cualquier problema o pregunta sobre estas configuraciones de seguridad, contactar al equipo de DevOps.