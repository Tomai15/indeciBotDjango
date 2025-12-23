@echo off
REM Script para iniciar Django + Django-Q en desarrollo

echo ========================================
echo   Iniciando CruceBotSupremo
echo ========================================

REM Activar virtual environment
call .venv\Scripts\activate.bat

REM Iniciar Django-Q worker en background
echo.
echo [1/2] Iniciando Django-Q Worker...
start "Django-Q Worker" cmd /k "python manage.py qcluster"

REM Esperar 2 segundos
timeout /t 2 /nobreak > nul

REM Iniciar servidor Django
echo.
echo [2/2] Iniciando Servidor Django...
echo.
python manage.py runserver

REM Si el servidor se detiene, preguntar si cerrar el worker
echo.
echo ¿Desea detener el worker de Django-Q? (S/N)
set /p DETENER=

if /i "%DETENER%"=="S" (
    taskkill /FI "WINDOWTITLE eq Django-Q Worker*" /F
    echo Worker detenido.
)

pause
