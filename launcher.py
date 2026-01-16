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
import urllib.request
import zipfile
import shutil
import tempfile
import json
from pathlib import Path

# Configuración
HOST = "127.0.0.1"
PORT = 8000
URL = f"http://{HOST}:{PORT}"

# Configuración de GitHub para auto-actualización
GITHUB_OWNER = "Tomai15"
GITHUB_REPO = "indeciBotDjango"
GITHUB_BRANCH = "main"

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


def get_local_version():
    """Obtiene la versión local desde un archivo VERSION o el commit hash."""
    version_file = Path(__file__).parent / "VERSION"
    if version_file.exists():
        return version_file.read_text().strip()
    return None


def save_local_version(version):
    """Guarda la versión local en un archivo VERSION."""
    version_file = Path(__file__).parent / "VERSION"
    version_file.write_text(version)


def get_github_latest_commit():
    """Obtiene el SHA del último commit en GitHub."""
    try:
        api_url = f"https://api.github.com/repos/{GITHUB_OWNER}/{GITHUB_REPO}/commits/{GITHUB_BRANCH}"
        req = urllib.request.Request(api_url, headers={"User-Agent": "CruceBotSupremo"})
        with urllib.request.urlopen(req, timeout=15) as response:
            data = json.loads(response.read().decode())
            return data.get("sha", "")[:12]  # Primeros 12 caracteres del SHA
    except Exception:
        return None


def update_from_github_zip():
    """Descarga y extrae el ZIP del repositorio desde GitHub."""
    print_status("Descargando actualización desde GitHub...", "info")

    try:
        zip_url = f"https://github.com/{GITHUB_OWNER}/{GITHUB_REPO}/archive/refs/heads/{GITHUB_BRANCH}.zip"
        project_dir = Path(__file__).parent

        # Crear directorio temporal
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            zip_path = temp_path / "update.zip"

            # Descargar el ZIP
            print_status("Descargando...", "info")
            req = urllib.request.Request(zip_url, headers={"User-Agent": "CruceBotSupremo"})
            with urllib.request.urlopen(req, timeout=120) as response:
                with open(zip_path, 'wb') as f:
                    f.write(response.read())

            # Extraer el ZIP
            print_status("Extrayendo archivos...", "info")
            with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                zip_ref.extractall(temp_path)

            # El ZIP de GitHub crea una carpeta con nombre "repo-branch"
            extracted_dir = temp_path / f"{GITHUB_REPO}-{GITHUB_BRANCH}"

            if not extracted_dir.exists():
                # Buscar la carpeta extraída
                dirs = [d for d in temp_path.iterdir() if d.is_dir()]
                if dirs:
                    extracted_dir = dirs[0]
                else:
                    print_status("Error: no se encontró el contenido extraído", "error")
                    return False

            # Archivos/carpetas a preservar (no sobrescribir)
            preserve = {'.git', '.venv', 'venv', 'db.sqlite3', '__pycache__', '.env', 'VERSION'}

            # Copiar archivos actualizados
            for item in extracted_dir.iterdir():
                if item.name in preserve:
                    continue

                dest = project_dir / item.name

                if item.is_dir():
                    if dest.exists():
                        shutil.rmtree(dest)
                    shutil.copytree(item, dest)
                else:
                    shutil.copy2(item, dest)

            # Guardar la versión actual
            latest_commit = get_github_latest_commit()
            if latest_commit:
                save_local_version(latest_commit)

            print_status("Actualización completada", "success")
            return True

    except urllib.error.URLError as e:
        print_status(f"Error de conexión: {e.reason}", "error")
        return False
    except Exception as e:
        print_status(f"Error durante la actualización: {e}", "error")
        return False


def check_for_updates_git():
    """Intenta actualizar usando git. Retorna True si tuvo éxito, False si git no está disponible."""
    try:
        # Verificar si git está disponible
        result = subprocess.run(
            ["git", "--version"],
            capture_output=True,
            text=True,
            cwd=Path(__file__).parent
        )
        if result.returncode != 0:
            return False  # Git no disponible

        # Fetch para obtener los cambios remotos
        result = subprocess.run(
            ["git", "fetch"],
            capture_output=True,
            text=True,
            cwd=Path(__file__).parent,
            timeout=30
        )
        if result.returncode != 0:
            print_status("No se pudo conectar al repositorio", "warning")
            return True  # Git disponible pero sin conexión

        # Obtener la rama actual
        result = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            capture_output=True,
            text=True,
            cwd=Path(__file__).parent
        )
        current_branch = result.stdout.strip() if result.returncode == 0 else "main"

        # Comparar commits
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            cwd=Path(__file__).parent
        )
        local_commit = result.stdout.strip() if result.returncode == 0 else ""

        result = subprocess.run(
            ["git", "rev-parse", f"origin/{current_branch}"],
            capture_output=True,
            text=True,
            cwd=Path(__file__).parent
        )
        remote_commit = result.stdout.strip() if result.returncode == 0 else ""

        if local_commit == remote_commit:
            print_status("Ya tienes la última versión", "success")
            return True

        # Hay actualizaciones disponibles
        print_status(f"Actualizaciones disponibles en {current_branch}", "info")
        print_status("Descargando actualizaciones...", "info")

        # Hacer git pull
        result = subprocess.run(
            ["git", "pull", "--ff-only"],
            capture_output=True,
            text=True,
            cwd=Path(__file__).parent,
            timeout=60
        )

        if result.returncode == 0:
            print_status("Actualización completada", "success")
        else:
            print_status("No se pudo actualizar automáticamente", "warning")
            print_status("Puede haber cambios locales sin guardar", "warning")

        return True

    except subprocess.TimeoutExpired:
        print_status("Timeout al conectar con el repositorio", "warning")
        return True
    except FileNotFoundError:
        return False  # Git no está instalado
    except Exception:
        return False


def check_for_updates_zip():
    """Actualiza usando descarga de ZIP desde GitHub (sin git)."""
    # Verificar si hay actualizaciones comparando versiones
    local_version = get_local_version()
    remote_version = get_github_latest_commit()

    if remote_version is None:
        print_status("No se pudo conectar a GitHub", "warning")
        return True

    if local_version == remote_version:
        print_status("Ya tienes la última versión", "success")
        return True

    # Hay actualizaciones
    if local_version:
        print_status(f"Nueva versión disponible: {remote_version}", "info")
    else:
        print_status("Verificando primera actualización...", "info")

    return update_from_github_zip()


def check_for_updates():
    """Verifica si hay actualizaciones en el repositorio de GitHub."""
    print_status("Verificando actualizaciones...")

    # Intentar primero con git
    if check_for_updates_git():
        return True

    # Si git no está disponible, usar método de descarga ZIP
    print_status("Git no disponible, usando descarga directa", "info")
    return check_for_updates_zip()


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
            print_status("Django-Q worker iniciado (ventana separada)", "success")
            return process
        elif sys.platform == 'darwin':
            # En macOS, usar AppleScript para abrir una nueva ventana de Terminal
            cwd = str(Path(__file__).parent)
            python_exe = sys.executable
            
            # Comando para AppleScript
            cmd = f'cd "{cwd}" && "{python_exe}" manage.py qcluster'
            script = f'tell application "Terminal" to do script "{cmd}"'
            
            subprocess.run(['osascript', '-e', script])
            print_status("Django-Q worker iniciado (nueva ventana de Terminal)", "success")
            return None
        else:
            # En Linux, usar DEVNULL para no bloquear
            process = subprocess.Popen(
                [sys.executable, "manage.py", "qcluster"],
                cwd=Path(__file__).parent,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )
            print_status("Django-Q worker iniciado (segundo plano)", "success")
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
    skip_update = "--no-update" in sys.argv

    # Cambiar al directorio del script
    os.chdir(Path(__file__).parent)

    # Verificar actualizaciones de GitHub
    if not skip_update:
        check_for_updates()

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
