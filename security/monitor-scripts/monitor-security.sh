#!/bin/sh
# =============================================================================
# MONITOR DE SEGURIDAD POSTGRESQL - COMPATIBLE CON ALPINE
# =============================================================================
# Script de monitoreo que funciona con imagen oficial Alpine

set -e

# Configuración
POSTGRES_HOST="${POSTGRES_HOST:-172.20.0.10}"
POSTGRES_USER="${POSTGRES_USER:-sstuser}"
POSTGRES_DB="${POSTGRES_DB:-bd_sst}"
LOG_DIR="/var/log/security"
REPORT_FILE="$LOG_DIR/security-report.json"

# Crear directorio de logs
mkdir -p "$LOG_DIR"

# Función de logging
log() {
    echo "$(date '+%Y-%m-%d %H:%M:%S') [SECURITY] $1" | tee -a "$LOG_DIR/monitor.log"
}

# Función para verificar PostgreSQL
check_postgres() {
    log "🔍 Verificando estado de PostgreSQL..."
    
    if nc -z "$POSTGRES_HOST" 5432; then
        log "✅ PostgreSQL está accesible"
        return 0
    else
        log "❌ PostgreSQL no está accesible"
        return 1
    fi
}

# Función para verificar conexiones activas
check_connections() {
    log "🔍 Verificando conexiones activas..."
    
    # Intentar conectar y obtener estadísticas
    if command -v psql >/dev/null 2>&1; then
        PGPASSWORD="$POSTGRES_PASSWORD" psql -h "$POSTGRES_HOST" -U "$POSTGRES_USER" -d "$POSTGRES_DB" -t -c "
            SELECT 
                count(*) as active_connections,
                max(extract(epoch from now() - backend_start)) as longest_connection_seconds
            FROM pg_stat_activity 
            WHERE state = 'active';" 2>/dev/null || log "⚠️  No se pudo obtener estadísticas de conexiones"
    else
        log "⚠️  psql no disponible para verificar conexiones"
    fi
}

# Función para verificar Fail2ban
check_fail2ban() {
    log "🔍 Verificando estado de Fail2ban..."
    
    # Verificar si el contenedor de Fail2ban está ejecutándose
    if docker ps --format "table {{.Names}}" | grep -q "fail2ban"; then
        log "✅ Contenedor Fail2ban está ejecutándose"
        
        # Intentar obtener estado de las jails
        docker exec fail2ban_security fail2ban-client status 2>/dev/null || log "⚠️  No se pudo obtener estado de Fail2ban"
    else
        log "❌ Contenedor Fail2ban no está ejecutándose"
    fi
}

# Función para analizar logs de PostgreSQL
analyze_postgres_logs() {
    log "🔍 Analizando logs de PostgreSQL..."
    
    LOG_PATH="/var/log/postgresql"
    if [ -d "$LOG_PATH" ]; then
        # Buscar intentos de autenticación fallidos en las últimas 24 horas
        FAILED_AUTHS=$(find "$LOG_PATH" -name "*.log" -mtime -1 -exec grep -c "authentication failed\|password authentication failed" {} + 2>/dev/null | awk '{sum+=$1} END {print sum+0}')
        
        log "📊 Intentos de autenticación fallidos (24h): $FAILED_AUTHS"
        
        if [ "$FAILED_AUTHS" -gt 10 ]; then
            log "⚠️  ALERTA: Muchos intentos de autenticación fallidos detectados"
        fi
    else
        log "⚠️  Directorio de logs de PostgreSQL no encontrado"
    fi
}

# Función para generar reporte JSON
generate_report() {
    log "📋 Generando reporte de seguridad..."
    
    TIMESTAMP=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
    
    cat > "$REPORT_FILE" << EOF
{
    "timestamp": "$TIMESTAMP",
    "security_status": {
        "postgresql": {
            "accessible": $(check_postgres && echo "true" || echo "false"),
            "port": 5432,
            "host": "$POSTGRES_HOST"
        },
        "fail2ban": {
            "running": $(docker ps --format "table {{.Names}}" | grep -q "fail2ban" && echo "true" || echo "false")
        },
        "monitoring": {
            "active": true,
            "last_check": "$TIMESTAMP"
        }
    },
    "alerts": [],
    "recommendations": [
        "Revisar logs de PostgreSQL regularmente",
        "Monitorear conexiones activas",
        "Verificar estado de Fail2ban",
        "Mantener certificados SSL actualizados"
    ]
}
EOF
    
    log "📋 Reporte generado: $REPORT_FILE"
}

# Función principal de monitoreo
monitor() {
    log "🚀 Iniciando monitoreo de seguridad..."
    
    while true; do
        check_postgres
        check_connections
        check_fail2ban
        analyze_postgres_logs
        generate_report
        
        log "😴 Esperando 300 segundos para el próximo chequeo..."
        sleep 300
    done
}

# Función de chequeo único
check() {
    log "🔍 Ejecutando chequeo único de seguridad..."
    
    check_postgres
    check_connections
    check_fail2ban
    analyze_postgres_logs
    generate_report
    
    log "✅ Chequeo completado"
}

# Función para mostrar reporte
report() {
    if [ -f "$REPORT_FILE" ]; then
        cat "$REPORT_FILE"
    else
        echo '{"error": "No hay reporte disponible"}'
    fi
}

# Función de ayuda
help() {
    echo "Uso: $0 {monitor|check|report|help}"
    echo ""
    echo "Comandos:"
    echo "  monitor  - Ejecutar monitoreo continuo"
    echo "  check    - Ejecutar chequeo único"
    echo "  report   - Mostrar último reporte"
    echo "  help     - Mostrar esta ayuda"
}

# Procesar argumentos
case "${1:-monitor}" in
    monitor)
        monitor
        ;;
    check)
        check
        ;;
    report)
        report
        ;;
    help)
        help
        ;;
    *)
        echo "Comando no reconocido: $1"
        help
        exit 1
        ;;
esac