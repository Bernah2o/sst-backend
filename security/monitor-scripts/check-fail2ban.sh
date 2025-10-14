#!/bin/sh
# =============================================================================
# VERIFICADOR DE FAIL2BAN PARA POSTGRESQL
# =============================================================================
# Script para verificar y gestionar fail2ban específicamente para PostgreSQL

set -e

# Función de logging
log() {
    echo "$(date '+%Y-%m-%d %H:%M:%S') [FAIL2BAN] $1"
}

# Verificar si fail2ban está ejecutándose
check_fail2ban_status() {
    log "🔍 Verificando estado de Fail2ban..."
    
    if docker ps --format "table {{.Names}}" | grep -q "sst_fail2ban"; then
        log "✅ Contenedor Fail2ban está ejecutándose"
        return 0
    else
        log "❌ Contenedor Fail2ban no está ejecutándose"
        return 1
    fi
}

# Verificar jails específicas de PostgreSQL
check_postgresql_jails() {
    log "🔍 Verificando jails de PostgreSQL..."
    
    if check_fail2ban_status; then
        # Verificar estado de las jails de PostgreSQL
        docker exec sst_fail2ban fail2ban-client status postgresql-auth 2>/dev/null && log "✅ Jail postgresql-auth activa" || log "❌ Jail postgresql-auth no activa"
        docker exec sst_fail2ban fail2ban-client status postgresql-scan 2>/dev/null && log "✅ Jail postgresql-scan activa" || log "❌ Jail postgresql-scan no activa"
        docker exec sst_fail2ban fail2ban-client status postgresql-ddos 2>/dev/null && log "✅ Jail postgresql-ddos activa" || log "❌ Jail postgresql-ddos no activa"
    fi
}

# Mostrar IPs baneadas
show_banned_ips() {
    log "🔍 Mostrando IPs baneadas..."
    
    if check_fail2ban_status; then
        log "📋 IPs baneadas por postgresql-auth:"
        docker exec sst_fail2ban fail2ban-client status postgresql-auth 2>/dev/null | grep "Banned IP list" || log "   Ninguna IP baneada"
        
        log "📋 IPs baneadas por postgresql-scan:"
        docker exec sst_fail2ban fail2ban-client status postgresql-scan 2>/dev/null | grep "Banned IP list" || log "   Ninguna IP baneada"
        
        log "📋 IPs baneadas por postgresql-ddos:"
        docker exec sst_fail2ban fail2ban-client status postgresql-ddos 2>/dev/null | grep "Banned IP list" || log "   Ninguna IP baneada"
    fi
}

# Reiniciar fail2ban si es necesario
restart_fail2ban() {
    log "🔄 Reiniciando Fail2ban..."
    
    docker restart sst_fail2ban
    sleep 10
    
    if check_fail2ban_status; then
        log "✅ Fail2ban reiniciado exitosamente"
    else
        log "❌ Error al reiniciar Fail2ban"
        return 1
    fi
}

# Función principal
main() {
    case "${1:-status}" in
        "status")
            check_fail2ban_status
            check_postgresql_jails
            show_banned_ips
            ;;
        "restart")
            restart_fail2ban
            ;;
        "check")
            check_fail2ban_status
            check_postgresql_jails
            ;;
        "banned")
            show_banned_ips
            ;;
        *)
            echo "Uso: $0 {status|restart|check|banned}"
            echo "  status  - Mostrar estado completo (por defecto)"
            echo "  restart - Reiniciar fail2ban"
            echo "  check   - Verificar solo el estado"
            echo "  banned  - Mostrar solo IPs baneadas"
            exit 1
            ;;
    esac
}

main "$@"