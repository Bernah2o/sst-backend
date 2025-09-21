#!/bin/bash

# Script de acceso rápido para el despliegue de SST Platform
# Uso: ./deploy.sh [opciones]

# Cambiar al directorio del script
cd "$(dirname "$0")"

echo ""
echo "========================================"
echo "   SST PLATFORM - DESPLIEGUE RAPIDO"
echo "========================================"
echo ""

case "$1" in
    "")
        echo "Ejecutando despliegue completo..."
        python3 deploy.py
        ;;
    "check")
        echo "Verificando prerequisitos..."
        python3 deploy.py --check
        ;;
    "deps")
        echo "Actualizando dependencias..."
        python3 deploy.py --deps-only
        ;;
    "migrate")
        echo "Ejecutando migraciones..."
        python3 deploy.py --migrate-only
        ;;
    "build")
        echo "Construyendo frontend..."
        python3 deploy.py --build-only
        ;;
    "restart")
        echo "Reiniciando servicios..."
        python3 deploy.py --restart-only
        ;;
    "rollback")
        echo "Ejecutando rollback..."
        python3 deploy.py --rollback
        ;;
    "help")
        echo ""
        echo "Uso: ./deploy.sh [opcion]"
        echo ""
        echo "Opciones disponibles:"
        echo "  [sin opcion]  - Despliegue completo"
        echo "  check         - Verificar prerequisitos"
        echo "  deps          - Solo actualizar dependencias"
        echo "  migrate       - Solo ejecutar migraciones"
        echo "  build         - Solo construir frontend"
        echo "  restart       - Solo reiniciar servicios"
        echo "  rollback      - Ejecutar rollback"
        echo "  help          - Mostrar esta ayuda"
        echo ""
        ;;
    *)
        echo "Pasando argumentos directamente al script Python..."
        python3 deploy.py "$@"
        ;;
esac

echo ""
echo "Proceso completado."