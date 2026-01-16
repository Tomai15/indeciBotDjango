#!/bin/bash

# CruceBotSupremo Launcher para macOS
# Doble clic para ejecutar o ejecutar desde terminal: ./Iniciar\ CruceBotSupremo.command

# Cambiar al directorio donde está el script
cd "$(dirname "$0")"

# Verificar si Python está instalado
if ! command -v python3 &> /dev/null; then
    echo "Error: Python3 no está instalado."
    echo "Por favor instala Python desde https://www.python.org/downloads/"
    read -p "Presiona Enter para salir..."
    exit 1
fi

# Ejecutar el launcher
python3 launcher.py

# Pausar al final si hay error
if [ $? -ne 0 ]; then
    read -p "Presiona Enter para salir..."
fi
