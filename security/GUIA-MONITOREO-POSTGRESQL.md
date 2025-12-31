# GUÍA DE MONITOREO POSTGRESQL - SST APP

## 🔍 COMANDOS DE MONITOREO DIARIO

### 1. Verificar Estado de Fail2ban
```bash
# Estado general
fail2ban-client status

# Estado específico de PostgreSQL
fail2ban-client status postgresql-auth
fail2ban-client status postgresql-ddos
fail2ban-client status postgresql-scan

# Ver IPs baneadas actualmente
fail2ban-client get postgresql-auth banip
```

### 2. Monitorear Logs de PostgreSQL
```bash
# Logs recientes del contenedor
docker logs 7b7134bda038 --tail 50 --timestamps

# Buscar intentos de ataque específicos
docker logs 7b7134bda038 | grep "FATAL.*password authentication failed"
docker logs 7b7134bda038 | grep "FATAL.*no pg_hba.conf entry"
docker logs 7b7134bda038 | grep "unsupported frontend protocol"
```

### 3. Verificar Configuración Activa
```bash
# Verificar pg_hba.conf activo
docker exec -it 7b7134bda038 cat /var/lib/postgresql/data/pg_hba.conf

# Verificar conexiones activas
docker exec -it 7b7134bda038 psql -U sstuser -d bd_sst -c "SELECT * FROM pg_stat_activity;"
```

## 🚨 ALERTAS Y UMBRALES

### Indicadores de Ataque
- **Crítico:** Más de 50 intentos fallidos por hora
- **Alto:** Más de 20 intentos fallidos en 10 minutos
- **Medio:** Más de 10 intentos desde la misma IP

### Comandos de Análisis
```bash
# Contar intentos por hora
docker logs 7b7134bda038 --since="1h" | grep "FATAL.*password authentication failed" | wc -l

# Top 10 IPs atacantes
docker logs 7b7134bda038 | grep "FATAL.*password authentication failed" | grep -oP 'client_hostname.*?\K[0-9.]+' | sort | uniq -c | sort -nr | head -10

# Usuarios más atacados
docker logs 7b7134bda038 | grep "FATAL.*password authentication failed" | grep -oP 'user ".*?"' | sort | uniq -c | sort -nr
```

## 🛠️ COMANDOS DE RESPUESTA A INCIDENTES

### Banear IP Manualmente
```bash
# Banear IP específica por 24 horas
fail2ban-client set postgresql-auth banip 192.168.1.100

# Desbanear IP
fail2ban-client set postgresql-auth unbanip 192.168.1.100
```

### Reiniciar Servicios (Solo en Emergencia)
```bash
# Reiniciar fail2ban
systemctl restart fail2ban

# Recargar configuración PostgreSQL
docker exec -it 7b7134bda038 su postgres -c "pg_ctl reload -D /var/lib/postgresql/data"
```

### Bloqueo de Emergencia
```bash
# Bloquear todo el puerto 5432 temporalmente
iptables -A INPUT -p tcp --dport 5432 -j DROP

# Restaurar acceso (eliminar regla)
iptables -D INPUT -p tcp --dport 5432 -j DROP
```

## 📊 SCRIPTS DE MONITOREO AUTOMATIZADO

### Script de Verificación Diaria
```bash
#!/bin/bash
# Guardar como: /root/check_postgresql_security.sh

echo "=== REPORTE DE SEGURIDAD POSTGRESQL $(date) ==="
echo

echo "1. Estado de Fail2ban:"
fail2ban-client status | grep "Jail list"
echo

echo "2. IPs Baneadas:"
fail2ban-client status postgresql-auth | grep "Currently banned"
echo

echo "3. Intentos de ataque en las últimas 24h:"
docker logs 7b7134bda038 --since="24h" | grep "FATAL.*password authentication failed" | wc -l
echo

echo "4. Top 5 IPs atacantes (últimas 24h):"
docker logs 7b7134bda038 --since="24h" | grep "FATAL.*password authentication failed" | grep -oP 'client_hostname.*?\K[0-9.]+' | sort | uniq -c | sort -nr | head -5
echo

echo "5. Estado del contenedor PostgreSQL:"
docker ps | grep 7b7134bda038
echo

echo "=== FIN DEL REPORTE ==="
```

### Hacer el Script Ejecutable
```bash
chmod +x /root/check_postgresql_security.sh

# Ejecutar manualmente
/root/check_postgresql_security.sh

# Programar ejecución diaria (opcional)
# echo "0 8 * * * /root/check_postgresql_security.sh >> /var/log/postgresql_security.log" | crontab -
```

## 🔧 CONFIGURACIONES AVANZADAS

### Ajustar Sensibilidad de Fail2ban
```bash
# Editar configuración
nano /etc/fail2ban/jail.d/postgresql.conf

# Parámetros ajustables:
# maxretry = 5     # Número de intentos antes del ban
# findtime = 600   # Ventana de tiempo en segundos
# bantime = 3600   # Duración del ban en segundos
```

### Whitelist de IPs Confiables
```bash
# Editar configuración principal
nano /etc/fail2ban/jail.local

# Agregar:
[DEFAULT]
ignoreip = 127.0.0.1/8 ::1 172.16.0.0/12 10.0.0.0/8 TU_IP_OFICINA
```

## 📈 MÉTRICAS DE RENDIMIENTO

### Verificar Impacto en Rendimiento
```bash
# Uso de CPU de fail2ban
ps aux | grep fail2ban

# Memoria utilizada
systemctl status fail2ban | grep Memory

# Reglas de iptables activas
iptables -L -n | grep 5432
```

## 🚀 PROCEDIMIENTOS DE DEPLOYMENT

### Pre-Deployment
1. Verificar que `pg_hba.conf` en `/security/` esté actualizado
2. Confirmar que fail2ban está funcionando
3. Hacer backup de configuraciones actuales

### Post-Deployment
1. Verificar que el nuevo contenedor use la configuración segura
2. Confirmar que fail2ban detecta el nuevo contenedor
3. Actualizar ID del contenedor en configuraciones si es necesario

### Comando para Actualizar ID de Contenedor
```bash
# Obtener nuevo ID
NEW_CONTAINER_ID=$(docker ps | grep postgres | awk '{print $1}')

# Actualizar configuración de fail2ban
sed -i "s/7b7134bda038/$NEW_CONTAINER_ID/g" /etc/fail2ban/jail.d/postgresql.conf

# Recargar fail2ban
systemctl reload fail2ban
```

## 📞 CONTACTOS DE EMERGENCIA

- **Administrador Sistema:** [Tu contacto]
- **Desarrollador Principal:** [Tu contacto]
- **Proveedor VPS:** [Contacto del proveedor]

## 📝 REGISTRO DE CAMBIOS

- **2025-10-17:** Implementación inicial de seguridad PostgreSQL
- **2025-10-17:** Configuración de fail2ban con 3 jails
- **2025-10-17:** Creación de guía de monitoreo

---

**Última actualización:** 2025-10-17 21:35 UTC  
**Próxima revisión:** 2025-10-24