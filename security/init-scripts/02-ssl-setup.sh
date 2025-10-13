#!/bin/bash
# =============================================================================
# CONFIGURACIÓN SSL AUTOMÁTICA PARA POSTGRESQL
# =============================================================================
# Este script se ejecuta automáticamente durante la inicialización
# Genera certificados SSL auto-firmados si no existen

set -e

echo "🔐 Configurando SSL para PostgreSQL..."

# Directorio para certificados SSL
SSL_DIR="/var/lib/postgresql/ssl"
mkdir -p "$SSL_DIR"

# Generar certificados SSL auto-firmados si no existen
if [ ! -f "$SSL_DIR/server.crt" ] || [ ! -f "$SSL_DIR/server.key" ]; then
    echo "📜 Generando certificados SSL auto-firmados..."
    
    # Generar clave privada
    openssl genrsa -out "$SSL_DIR/server.key" 2048
    
    # Generar certificado auto-firmado
    openssl req -new -x509 -key "$SSL_DIR/server.key" -out "$SSL_DIR/server.crt" -days 365 -subj "/C=CO/ST=Bogota/L=Bogota/O=DH2O/OU=SST/CN=postgres"
    
    # Configurar permisos
    chmod 600 "$SSL_DIR/server.key"
    chmod 644 "$SSL_DIR/server.crt"
    chown postgres:postgres "$SSL_DIR/server.key" "$SSL_DIR/server.crt"
    
    echo "✅ Certificados SSL generados exitosamente"
else
    echo "✅ Certificados SSL ya existen"
fi

# Configurar directorio de logs
LOG_DIR="/var/log/postgresql"
mkdir -p "$LOG_DIR"
chown postgres:postgres "$LOG_DIR"
chmod 755 "$LOG_DIR"

echo "🔐 Configuración SSL completada"