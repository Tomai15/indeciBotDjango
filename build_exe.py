"""
Script para construir el ejecutable de CruceBotSupremo.

Uso:
    python build_exe.py

Esto generará una carpeta 'dist/CruceBotSupremo' con el .exe y todo lo necesario.
"""

import subprocess
import sys
import os
import shutil
from pathlib import Path

# Directorio base del proyecto
BASE_DIR = Path(__file__).parent


def install_pyinstaller():
    """Instala PyInstaller si no está instalado."""
    print("Verificando PyInstaller...")
    try:
        import PyInstaller
        print(f"  ✓ PyInstaller {PyInstaller.__version__} encontrado")
    except ImportError:
        print("  Instalando PyInstaller...")
        subprocess.run([sys.executable, "-m", "pip", "install", "pyinstaller"], check=True)
        print("  ✓ PyInstaller instalado")


def create_entry_script():
    """Crea el script de entrada para el ejecutable."""
    entry_script = BASE_DIR / "crucebot_main.py"

    content = '''"""
Punto de entrada para el ejecutable CruceBotSupremo.
"""

import os
import sys
import time
import webbrowser
import threading
import multiprocessing

# Configurar el entorno antes de importar Django
def setup_environment():
    """Configura las variables de entorno necesarias."""
    # Obtener el directorio donde está el ejecutable
    if getattr(sys, 'frozen', False):
        # Ejecutando como .exe
        BASE_DIR = os.path.dirname(sys.executable)
    else:
        # Ejecutando como script
        BASE_DIR = os.path.dirname(os.path.abspath(__file__))

    os.chdir(BASE_DIR)

    # Agregar el directorio al path
    if BASE_DIR not in sys.path:
        sys.path.insert(0, BASE_DIR)

    # Configurar Django
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'CruceBotSupremo.settings')

    return BASE_DIR


def run_migrations():
    """Ejecuta las migraciones de Django."""
    print("Aplicando migraciones...")
    from django.core.management import call_command
    try:
        call_command('migrate', '--no-input', verbosity=0)
        print("  ✓ Migraciones aplicadas")
    except Exception as e:
        print(f"  ! Error en migraciones: {e}")


def run_qcluster():
    """Ejecuta el cluster de Django-Q en un proceso separado."""
    from django.core.management import call_command
    try:
        call_command('qcluster')
    except KeyboardInterrupt:
        pass


def run_server(host, port):
    """Ejecuta el servidor Django."""
    from django.core.management import call_command
    try:
        call_command('runserver', f'{host}:{port}', '--noreload')
    except KeyboardInterrupt:
        pass


def open_browser_delayed(url):
    """Abre el navegador después de un delay."""
    time.sleep(2.5)
    webbrowser.open(url)


def main():
    """Función principal."""
    # Permitir multiprocessing en Windows con PyInstaller
    multiprocessing.freeze_support()

    HOST = "127.0.0.1"
    PORT = 8000
    URL = f"http://{HOST}:{PORT}"

    print()
    print("=" * 60)
    print("         CruceBotSupremo - Sistema de Reportes")
    print("=" * 60)
    print()

    # Configurar entorno
    base_dir = setup_environment()
    print(f"Directorio: {base_dir}")

    # Inicializar Django
    print("Inicializando Django...")
    import django
    django.setup()
    print("  ✓ Django inicializado")

    # Ejecutar migraciones
    run_migrations()

    # Iniciar Django-Q en proceso separado
    print("Iniciando worker de tareas...")
    qcluster_process = multiprocessing.Process(target=run_qcluster, daemon=True)
    qcluster_process.start()
    print("  ✓ Worker iniciado")

    # Abrir navegador en thread separado
    print(f"Abriendo navegador en {URL}...")
    browser_thread = threading.Thread(target=open_browser_delayed, args=(URL,), daemon=True)
    browser_thread.start()

    print()
    print("=" * 60)
    print(f"  Servidor corriendo en: {URL}")
    print("  Presione Ctrl+C para detener")
    print("=" * 60)
    print()

    # Ejecutar servidor (bloquea hasta Ctrl+C)
    try:
        run_server(HOST, PORT)
    except KeyboardInterrupt:
        print()
        print("Deteniendo servidor...")
    finally:
        if qcluster_process.is_alive():
            qcluster_process.terminate()
            qcluster_process.join(timeout=2)
        print("Servidor detenido.")


if __name__ == "__main__":
    main()
'''

    entry_script.write_text(content, encoding='utf-8')
    print(f"  ✓ Script de entrada creado: {entry_script}")
    return entry_script


def create_spec_file():
    """Crea el archivo .spec para PyInstaller."""
    spec_content = '''# -*- mode: python ; coding: utf-8 -*-

import os
import sys
from pathlib import Path

block_cipher = None

# Directorio base
BASE_DIR = Path(SPECPATH)

# Encontrar el directorio de Django para incluir templates
import django
django_dir = Path(django.__file__).parent

# Archivos de datos a incluir
datas = [
    # Templates de Django
    (str(BASE_DIR / 'core' / 'templates'), 'core/templates'),
    # Archivos estáticos (si existen)
]

# Agregar static si existe
static_dir = BASE_DIR / 'static'
if static_dir.exists():
    datas.append((str(static_dir), 'static'))

# Agregar staticfiles si existe
staticfiles_dir = BASE_DIR / 'staticfiles'
if staticfiles_dir.exists():
    datas.append((str(staticfiles_dir), 'staticfiles'))

# Agregar media si existe (para la base de datos inicial)
media_dir = BASE_DIR / 'media'
if media_dir.exists():
    datas.append((str(media_dir), 'media'))

# Incluir la base de datos si existe
db_file = BASE_DIR / 'db.sqlite3'
if db_file.exists():
    datas.append((str(db_file), '.'))

a = Analysis(
    ['crucebot_main.py'],
    pathex=[str(BASE_DIR)],
    binaries=[],
    datas=datas,
    hiddenimports=[
        'django',
        'django.contrib.admin',
        'django.contrib.auth',
        'django.contrib.contenttypes',
        'django.contrib.sessions',
        'django.contrib.messages',
        'django.contrib.staticfiles',
        'django.template.backends.django',
        'django.template.loader_tags',
        'django_q',
        'django_q.cluster',
        'django_q.brokers',
        'django_q.brokers.orm',
        'core',
        'core.views',
        'core.models',
        'core.forms',
        'core.urls',
        'core.admin',
        'core.tasks',
        'core.services',
        'core.services.ReportePaywayService',
        'core.services.ReporteVtexService',
        'core.services.ReporteCDPService',
        'core.services.CruceService',
        'CruceBotSupremo',
        'CruceBotSupremo.settings',
        'CruceBotSupremo.urls',
        'CruceBotSupremo.wsgi',
        'pandas',
        'openpyxl',
        'playwright',
        'playwright.sync_api',
        'playwright.async_api',
        'asgiref',
        'asgiref.sync',
        'sqlparse',
        'multiprocessing',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='CruceBotSupremo',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=True,  # True para ver logs, False para ocultar consola
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=None,  # Puedes agregar un icono: icon='icono.ico'
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='CruceBotSupremo',
)
'''

    spec_file = BASE_DIR / "CruceBotSupremo.spec"
    spec_file.write_text(spec_content, encoding='utf-8')
    print(f"  ✓ Archivo .spec creado: {spec_file}")
    return spec_file


def build_executable():
    """Ejecuta PyInstaller para crear el ejecutable."""
    print("Construyendo ejecutable...")
    print("  (Esto puede tardar varios minutos)")
    print()

    result = subprocess.run(
        [sys.executable, "-m", "PyInstaller", "CruceBotSupremo.spec", "--clean"],
        cwd=BASE_DIR
    )

    if result.returncode == 0:
        print()
        print("=" * 60)
        print("  ✓ Ejecutable creado exitosamente!")
        print()
        print(f"  Ubicación: {BASE_DIR / 'dist' / 'CruceBotSupremo'}")
        print()
        print("  Para distribuir, comparte la carpeta 'CruceBotSupremo'")
        print("  El usuario solo debe ejecutar 'CruceBotSupremo.exe'")
        print("=" * 60)
    else:
        print()
        print("  ✗ Error al crear el ejecutable")
        return False

    return True


def main():
    print()
    print("=" * 60)
    print("    Construcción de CruceBotSupremo.exe")
    print("=" * 60)
    print()

    # Instalar PyInstaller
    install_pyinstaller()
    print()

    # Crear script de entrada
    create_entry_script()
    print()

    # Crear archivo .spec
    create_spec_file()
    print()

    # Construir
    build_executable()


if __name__ == "__main__":
    main()
