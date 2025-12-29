"""
Launcher para CruceBotSupremo.

Este script inicia el servidor Django y el worker de Django-Q,
luego abre el navegador automáticamente.

Uso:
    python launcher.py          # Inicia todo
    python launcher.py --no-browser  # Sin abrir navegador
"""

import subprocess
import sys
import os
import time
import webbrowser
import threading
import signal
from pathlib import Path

# Configuración
HOST = "127.0.0.1"
PORT = 8000
URL = f"http://{HOST}:{PORT}"

# Colores para la consola (Windows compatible)
class Colors:
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    BLUE = '\033[94m'
    RESET = '\033[0m'
    BOLD = '\033[1m'


def print_banner():
    """Muestra el banner de inicio."""
    print(f"""
{Colors.BLUE}{Colors.BOLD}
╔═══════════════════════════════════════════════════════════════╗
║                                                               ║
║               🚀 CruceBotSupremo Launcher 🚀                  ║
║                                                               ║
║   Sistema de Reportes y Cruces de Transacciones               ║
║                                                               ║
╚═══════════════════════════════════════════════════════════════╝
{Colors.RESET}
""")


def print_status(message, status="info"):
    """Imprime un mensaje con formato."""
    icons = {
        "info": f"{Colors.BLUE}ℹ{Colors.RESET}",
        "success": f"{Colors.GREEN}✓{Colors.RESET}",
        "warning": f"{Colors.YELLOW}⚠{Colors.RESET}",
        "error": f"{Colors.RED}✗{Colors.RESET}",
    }
    print(f"  {icons.get(status, icons['info'])} {message}")


def check_requirements():
    """Verifica e instala dependencias si es necesario."""
    print_status("Verificando dependencias de Python...")

    requirements_file = Path(__file__).parent / "requirements.txt"

    if not requirements_file.exists():
        print_status("No se encontró requirements.txt", "warning")
        return True

    try:
        # Instalar/actualizar dependencias silenciosamente
        result = subprocess.run(
            [sys.executable, "-m", "pip", "install", "-r", str(requirements_file), "-q"],
            capture_output=True,
            text=True
        )
        if result.returncode == 0:
            print_status("Dependencias de Python instaladas", "success")
        else:
            print_status(f"Error instalando dependencias: {result.stderr}", "error")
            return False
    except Exception as e:
        print_status(f"Error verificando dependencias: {e}", "error")
        return False

    # Verificar e instalar navegadores de Playwright
    return check_playwright()


def check_playwright():
    """Verifica e instala los navegadores de Playwright si es necesario."""
    print_status("Verificando navegadores de Playwright...")

    try:
        # Intentar importar playwright para ver si está instalado
        import playwright
        from playwright.sync_api import sync_playwright

        # Verificar si Chromium está instalado intentando obtener el path
        try:
            with sync_playwright() as p:
                # Si esto funciona, el navegador está instalado
                browser = p.chromium.launch(headless=True)
                browser.close()
            print_status("Navegadores de Playwright OK", "success")
            return True
        except Exception:
            # El navegador no está instalado, instalarlo
            print_status("Instalando navegador Chromium (esto puede tardar)...", "warning")
            result = subprocess.run(
                [sys.executable, "-m", "playwright", "install", "chromium"],
                capture_output=True,
                text=True
            )
            if result.returncode == 0:
                print_status("Navegador Chromium instalado", "success")
                return True
            else:
                print_status(f"Error instalando Chromium: {result.stderr}", "error")
                return False

    except ImportError:
        print_status("Playwright no está instalado correctamente", "error")
        return False
    except Exception as e:
        print_status(f"Error verificando Playwright: {e}", "error")
        return False


def run_migrations():
    """Ejecuta las migraciones de Django."""
    print_status("Ejecutando migraciones...")

    try:
        result = subprocess.run(
            [sys.executable, "manage.py", "migrate", "--no-input"],
            capture_output=True,
            text=True,
            cwd=Path(__file__).parent
        )
        if result.returncode == 0:
            print_status("Migraciones aplicadas", "success")
            return True
        else:
            print_status(f"Error en migraciones: {result.stderr}", "error")
            return False
    except Exception as e:
        print_status(f"Error ejecutando migraciones: {e}", "error")
        return False


def collect_static():
    """Recolecta archivos estáticos."""
    print_status("Recolectando archivos estáticos...")

    try:
        result = subprocess.run(
            [sys.executable, "manage.py", "collectstatic", "--no-input", "--clear"],
            capture_output=True,
            text=True,
            cwd=Path(__file__).parent
        )
        if result.returncode == 0:
            print_status("Archivos estáticos recolectados", "success")
            return True
        else:
            # No es crítico si falla
            print_status("Saltando collectstatic (no crítico)", "warning")
            return True
    except Exception as e:
        print_status("Saltando collectstatic", "warning")
        return True


def open_browser_delayed():
    """Abre el navegador después de un pequeño delay."""
    time.sleep(2)  # Esperar a que Django inicie
    print_status(f"Abriendo navegador en {URL}", "info")
    webbrowser.open(URL)


def start_django_q():
    """Inicia el cluster de Django-Q en un proceso separado."""
    print_status("Iniciando Django-Q worker...", "info")

    try:
        if os.name == 'nt':
            # En Windows, abrir en una nueva ventana de consola para evitar bloqueos
            process = subprocess.Popen(
                [sys.executable, "manage.py", "qcluster"],
                cwd=Path(__file__).parent,
                creationflags=subprocess.CREATE_NEW_CONSOLE
            )
        else:
            # En Linux/Mac, usar DEVNULL para no bloquear
            process = subprocess.Popen(
                [sys.executable, "manage.py", "qcluster"],
                cwd=Path(__file__).parent,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )
        print_status("Django-Q worker iniciado (ventana separada)", "success")
        return process
    except Exception as e:
        print_status(f"Error iniciando Django-Q: {e}", "error")
        return None


def start_django_server():
    """Inicia el servidor de Django."""
    print_status(f"Iniciando servidor Django en {URL}...", "info")

    try:
        process = subprocess.Popen(
            [sys.executable, "manage.py", "runserver", f"{HOST}:{PORT}", "--noreload"],
            cwd=Path(__file__).parent,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT
        )
        return process
    except Exception as e:
        print_status(f"Error iniciando Django: {e}", "error")
        return None


def main():
    """Función principal del launcher."""
    print_banner()

    # Parsear argumentos
    open_browser = "--no-browser" not in sys.argv

    # Cambiar al directorio del script
    os.chdir(Path(__file__).parent)

    # Verificar dependencias
    if not check_requirements():
        input("\nPresione Enter para salir...")
        return 1

    # Ejecutar migraciones
    if not run_migrations():
        input("\nPresione Enter para salir...")
        return 1

    # Collectstatic (opcional)
    collect_static()

    print()
    print_status("=" * 50, "info")
    print()

    # Iniciar Django-Q
    qcluster_process = start_django_q()

    # Pequeña pausa para que Django-Q inicie
    time.sleep(1)

    # Iniciar servidor Django
    django_process = start_django_server()

    if not django_process:
        if qcluster_process:
            qcluster_process.terminate()
        input("\nPresione Enter para salir...")
        return 1

    # Abrir navegador en un thread separado
    if open_browser:
        browser_thread = threading.Thread(target=open_browser_delayed)
        browser_thread.daemon = True
        browser_thread.start()

    print()
    print(f"{Colors.GREEN}{Colors.BOLD}")
    print("  ╔═══════════════════════════════════════════════════════╗")
    print(f"  ║  🌐 Servidor corriendo en: {URL:<25} ║")
    print("  ║                                                       ║")
    print("  ║  Presione Ctrl+C para detener el servidor             ║")
    print("  ╚═══════════════════════════════════════════════════════╝")
    print(f"{Colors.RESET}")
    print()

    try:
        # Mantener el proceso principal vivo y mostrar logs de Django
        while True:
            output = django_process.stdout.readline()
            if output:
                print(f"  {output.decode('utf-8', errors='ignore').strip()}")
            elif django_process.poll() is not None:
                break
    except KeyboardInterrupt:
        print()
        print_status("Deteniendo servidores...", "warning")
    finally:
        # Terminar procesos
        if django_process:
            django_process.terminate()
            django_process.wait()
        if qcluster_process:
            qcluster_process.terminate()
            qcluster_process.wait()
        print_status("Servidores detenidos", "success")

    return 0


if __name__ == "__main__":
    # Habilitar colores en Windows
    if os.name == 'nt':
        os.system('color')

    sys.exit(main())
