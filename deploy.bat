@echo off
REM Script de acceso rápido para el despliegue de SST Platform
REM Uso: deploy.bat [opciones]

cd /d "%~dp0"

echo.
echo ========================================
echo   SST PLATFORM - DESPLIEGUE RAPIDO
echo ========================================
echo.

if "%1"=="" (
    echo Ejecutando despliegue completo...
    python deploy.py
) else if "%1"=="check" (
    echo Verificando prerequisitos...
    python deploy.py --check
) else if "%1"=="deps" (
    echo Actualizando dependencias...
    python deploy.py --deps-only
) else if "%1"=="migrate" (
    echo Ejecutando migraciones...
    python deploy.py --migrate-only
) else if "%1"=="build" (
    echo Construyendo frontend...
    python deploy.py --build-only
) else if "%1"=="restart" (
    echo Reiniciando servicios...
    python deploy.py --restart-only
) else if "%1"=="rollback" (
    echo Ejecutando rollback...
    python deploy.py --rollback
) else if "%1"=="help" (
    echo.
    echo Uso: deploy.bat [opcion]
    echo.
    echo Opciones disponibles:
    echo   [sin opcion]  - Despliegue completo
    echo   check         - Verificar prerequisitos
    echo   deps          - Solo actualizar dependencias
    echo   migrate       - Solo ejecutar migraciones
    echo   build         - Solo construir frontend
    echo   restart       - Solo reiniciar servicios
    echo   rollback      - Ejecutar rollback
    echo   help          - Mostrar esta ayuda
    echo.
) else (
    echo Pasando argumentos directamente al script Python...
    python deploy.py %*
)

echo.
echo Presiona cualquier tecla para continuar...
pause >nul