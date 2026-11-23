@echo off
chcp 65001 >nul
setlocal EnableExtensions
title GEMINI ONE Portable (LDPlayer)

set "ROOT=%~dp0"
set "PY=%ROOT%python\python.exe"
set "TOOLS=%ROOT%google-one-tools"
set "ADB=%TOOLS%\adb.exe"

:: Aisla el Python portable de cualquier configuracion previa del PC
set "PYTHONHOME="
set "PYTHONPATH="
set "PYTHONNOUSERSITE=1"
set "PYTHONUTF8=1"
set "ADB_PATH=%ADB%"
set "PATH=%ROOT%python;%TOOLS%;%PATH%"

if not exist "%PY%" (
    echo [ERROR] No se encontro Python portable en "%PY%".
    pause
    exit /b 1
)

:MENU
cls
echo ====================================================================
echo   GEMINI ONE - Paquete 100%% Portable para LDPlayer
echo ====================================================================
echo   Carpeta: %ROOT%
echo.
echo   [1] Diagnosticar entorno (probe_env.py)  ^<-- Ejecutar primero
echo   [2] Escanear todas las ofertas / pruebas gratis (scan_all.py)
echo   [3] Consultar SKU(s) especifico(s) (query_sku.py)
echo   [4] Escaneo completo + generar reporte Markdown (scan_everything.py)
echo   [5] Abrir checkout de un SKU en el emulador (launch_checkout.py)
echo   [6] Ver dispositivos ADB conectados (adb devices)
echo   [7] Abrir consola CMD lista (Python portable + ADB)
echo   [0] Salir
echo ====================================================================
echo.
set "OPT="
set /p "OPT=Elige una opcion [0-7]: "

if "%OPT%"=="1" goto PROBE
if "%OPT%"=="2" goto SCAN_ALL
if "%OPT%"=="3" goto QUERY_SKU
if "%OPT%"=="4" goto SCAN_EVERYTHING
if "%OPT%"=="5" goto CHECKOUT
if "%OPT%"=="6" goto ADB_LIST
if "%OPT%"=="7" goto SHELL
if "%OPT%"=="0" exit /b 0
goto MENU

:PROBE
echo.
pushd "%TOOLS%"
"%PY%" -B probe_env.py
popd
echo.
pause
goto MENU

:SCAN_ALL
echo.
pushd "%TOOLS%"
"%PY%" -B scan_all.py
popd
echo.
pause
goto MENU

:QUERY_SKU
echo.
echo Ejemplos: g1.20tb g1.20tb.3months_ip_75p.acq g1.play.helium g1.2tb.ai.subs_variant
set "SKUS="
set /p "SKUS=Escribe uno o varios SKUs separados por espacio: "
if "%SKUS%"=="" goto MENU
pushd "%TOOLS%"
"%PY%" -B query_sku.py %SKUS%
popd
echo.
pause
goto MENU

:SCAN_EVERYTHING
echo.
pushd "%TOOLS%"
"%PY%" -B scan_everything.py
popd
echo.
pause
goto MENU

:CHECKOUT
echo.
echo ADVERTENCIA: Abrir el checkout puede consumir la elegibilidad de prueba
echo gratuita de la cuenta aunque no confirmes la suscripcion en pantalla.
echo Ejemplos: g1.20tb  ^|  g1.20tb.3months_ip_75p.acq  ^|  g1.2tb.6months_eft
set "SKU="
set /p "SKU=Escribe el SKU a abrir: "
if "%SKU%"=="" goto MENU
pushd "%TOOLS%"
"%PY%" -B launch_checkout.py --sku %SKU%
popd
echo.
pause
goto MENU

:ADB_LIST
echo.
"%ADB%" devices -l
echo.
pause
goto MENU

:SHELL
echo.
echo Consola portable lista. Ejemplos:
echo   python -B probe_env.py
echo   python -B scan_all.py
echo   python -B query_sku.py g1.20tb g1.30tb
echo   python -B launch_checkout.py --sku g1.20tb
echo.
pushd "%TOOLS%"
cmd /k
popd
goto MENU
