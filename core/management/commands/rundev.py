"""
Management command para ejecutar Django + Django-Q juntos en desarrollo.

Uso:
    python manage.py rundev
"""

from django.core.management.base import BaseCommand
from django.core.management import call_command
import subprocess
import sys
import os
import signal
import threading


class Command(BaseCommand):
    help = 'Inicia el servidor de desarrollo y el worker de Django-Q simultáneamente'

    def add_arguments(self, parser):
        parser.add_argument(
            '--noreload',
            action='store_true',
            help='No usar auto-reload en el servidor Django',
        )
        parser.add_argument(
            '--port',
            type=int,
            default=8000,
            help='Puerto para el servidor Django (default: 8000)',
        )

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('=' * 60))
        self.stdout.write(self.style.SUCCESS('  🚀 Iniciando CruceBotSupremo en modo desarrollo'))
        self.stdout.write(self.style.SUCCESS('=' * 60))
        self.stdout.write('')

        # Proceso del worker
        worker_process = None
        # Proceso del servidor
        server_process = None

        def cleanup(signum=None, frame=None):
            """Limpia los procesos al recibir Ctrl+C"""
            self.stdout.write('')
            self.stdout.write(self.style.WARNING('🛑 Deteniendo servicios...'))

            if worker_process:
                worker_process.terminate()
                try:
                    worker_process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    worker_process.kill()

            if server_process:
                server_process.terminate()
                try:
                    server_process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    server_process.kill()

            self.stdout.write(self.style.SUCCESS('✅ Servicios detenidos correctamente'))
            sys.exit(0)

        # Registrar handler para Ctrl+C
        signal.signal(signal.SIGINT, cleanup)
        signal.signal(signal.SIGTERM, cleanup)

        try:
            # Obtener el ejecutable de Python del virtualenv
            python_executable = sys.executable

            # 1. Iniciar Django-Q worker
            self.stdout.write(self.style.HTTP_INFO('📋 [1/2] Iniciando Django-Q Worker...'))
            worker_process = subprocess.Popen(
                [python_executable, 'manage.py', 'qcluster'],
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                universal_newlines=True,
                bufsize=1
            )

            # Thread para mostrar output del worker
            def print_worker_output():
                for line in worker_process.stdout:
                    self.stdout.write(f'[Worker] {line.rstrip()}')

            worker_thread = threading.Thread(target=print_worker_output, daemon=True)
            worker_thread.start()

            # Esperar un poco para que el worker arranque
            import time
            time.sleep(2)

            # 2. Iniciar servidor Django
            self.stdout.write('')
            self.stdout.write(self.style.HTTP_INFO('🌐 [2/2] Iniciando Servidor Django...'))
            self.stdout.write('')

            # Construir argumentos para runserver
            runserver_args = [str(options['port'])]
            if options['noreload']:
                runserver_args.append('--noreload')

            # Ejecutar runserver en el proceso principal (para ver logs)
            call_command('runserver', *runserver_args)

        except KeyboardInterrupt:
            cleanup()
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'❌ Error: {e}'))
            cleanup()
        finally:
            cleanup()
