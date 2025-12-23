#!/bin/bash

# Script para iniciar Django + Django-Q en desarrollo (Linux/Mac)

echo "========================================"
echo "  Iniciando CruceBotSupremo"
echo "========================================"

# Activar virtual environment
source .venv/bin/activate

# Función para manejar Ctrl+C
cleanup() {
    echo ""
    echo "Deteniendo servicios..."
    kill $QCLUSTER_PID $RUNSERVER_PID 2>/dev/null
    exit 0
}

trap cleanup SIGINT SIGTERM

# Iniciar Django-Q worker en background
echo ""
echo "[1/2] Iniciando Django-Q Worker..."
python manage.py qcluster &
QCLUSTER_PID=$!
echo "Worker PID: $QCLUSTER_PID"

# Esperar 2 segundos
sleep 2

# Iniciar servidor Django en background
echo ""
echo "[2/2] Iniciando Servidor Django..."
echo ""
python manage.py runserver &
RUNSERVER_PID=$!
echo "Server PID: $RUNSERVER_PID"

# Esperar a que ambos procesos terminen
wait
