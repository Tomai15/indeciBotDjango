"""
Management command simple para ejecutar Django + Django-Q (mejor para Windows).

Uso:
    python manage.py rundev_simple
"""

from django.core.management.base import BaseCommand
import subprocess
import sys
import os
import platform


class Command(BaseCommand):
    help = 'Inicia el servidor y worker (versión simple para Windows)'

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('=' * 60))
        self.stdout.write(self.style.SUCCESS('  🚀 Iniciando CruceBotSupremo'))
        self.stdout.write(self.style.SUCCESS('=' * 60))
        self.stdout.write('')

        python_exe = sys.executable
        is_windows = platform.system() == 'Windows'

        if is_windows:
            # Windows: Usar start para abrir ventana separada
            self.stdout.write(self.style.HTTP_INFO('📋 Iniciando Django-Q Worker (ventana separada)...'))

            subprocess.Popen(
                ['start', 'cmd', '/k', python_exe, 'manage.py', 'qcluster'],
                shell=True
            )

            import time
            time.sleep(2)

            self.stdout.write(self.style.HTTP_INFO('🌐 Iniciando Servidor Django...'))
            self.stdout.write('')

            # Servidor en la ventana actual
            subprocess.run([python_exe, 'manage.py', 'runserver'])

        else:
            # Linux/Mac: Usar nohup o screen
            self.stdout.write(self.style.HTTP_INFO('📋 Iniciando Django-Q Worker (background)...'))

            subprocess.Popen(
                [python_exe, 'manage.py', 'qcluster'],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )

            import time
            time.sleep(2)

            self.stdout.write(self.style.HTTP_INFO('🌐 Iniciando Servidor Django...'))
            self.stdout.write('')

            subprocess.run([python_exe, 'manage.py', 'runserver'])
