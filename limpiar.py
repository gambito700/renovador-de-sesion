# =============================================================================
# Renovador de sesion -- Limpiador de instalacion
# =============================================================================
# Elimina todo lo instalado por sesion.py para volver al estado inicial:
# - selenium y sus dependencias
# - geckodriver / chromedriver / msedgedriver
# - archivo de log sesion_log.txt
# - cache de pip y __pycache__
#
# Los archivos sesion.py, limpiar.py y README.md NO se eliminan.
#
# Uso:     python3 limpiar.py
# Linux:   puede pedir sudo para drivers en /usr/local/bin o /usr/bin
# =============================================================================

import sys
import os
import shutil
import platform
import subprocess
from datetime import datetime

SO = platform.system()

# -----------------------------------------------------------------------------
# ENCODING SEGURO
# -----------------------------------------------------------------------------

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

# -----------------------------------------------------------------------------
# UTILIDADES
# -----------------------------------------------------------------------------

def ui(msg):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}")

def confirmar(msg):
    return input(f"\n  {msg} (s/n): ").strip().lower() == "s"

def es_root():
    # Verifica privilegios root en Linux/macOS
    # En Windows siempre False — usa otro mecanismo de permisos
    if SO == "Windows":
        return False
    return os.geteuid() == 0

# -----------------------------------------------------------------------------
# DESINSTALAR SELENIUM
# En Linux instalado con --break-system-packages queda en paquetes del sistema
# pip uninstall normal no lo ve — hay que agregar --break-system-packages
# -----------------------------------------------------------------------------

def desinstalar_selenium():
    ui("Desinstalando selenium y dependencias...")

    paquetes = [
        "selenium",
        "urllib3",
        "trio",
        "trio-websocket",
        "outcome",
        "sniffio",
        "wsproto",
        "h11",
        "exceptiongroup",
    ]

    flags = ["--break-system-packages"] if SO == "Linux" else []

    for paquete in paquetes:
        try:
            cmd    = [sys.executable, "-m", "pip", "uninstall", "-y", paquete] + flags
            result = subprocess.run(cmd, capture_output=True, text=True)

            if "Successfully uninstalled" in result.stdout:
                ui(f"  eliminado: {paquete}")
            elif "not installed" in result.stdout or not result.stdout.strip():
                ui(f"  no encontrado: {paquete}")
            else:
                # Reintenta con sudo en Linux si fallo por permisos
                if SO == "Linux" and not es_root():
                    ui(f"  reintentando con sudo: {paquete}")
                    cmd_sudo = ["sudo", sys.executable, "-m", "pip", "uninstall", "-y", paquete] + flags
                    result2  = subprocess.run(cmd_sudo, capture_output=True, text=True)
                    if "Successfully uninstalled" in result2.stdout:
                        ui(f"  eliminado con sudo: {paquete}")
                    else:
                        ui(f"  no se pudo eliminar: {paquete}")
                else:
                    ui(f"  no se pudo eliminar: {paquete}")
        except Exception as e:
            ui(f"  error en {paquete}: {e}")

# -----------------------------------------------------------------------------
# ELIMINAR DRIVERS INSTALADOS MANUALMENTE
# Busca en PATH y en la carpeta del script
# En Linux los drivers en /usr/local/bin requieren sudo
# -----------------------------------------------------------------------------

def eliminar_drivers():
    ui("Buscando drivers instalados manualmente...")

    drivers = ["geckodriver", "chromedriver", "msedgedriver"]
    if SO == "Windows":
        drivers = [d + ".exe" for d in drivers]

    encontrados = []
    for driver in drivers:
        path = shutil.which(driver)
        if path and path not in encontrados:
            encontrados.append(path)
        local = os.path.join(os.path.dirname(os.path.abspath(__file__)), driver)
        if os.path.exists(local) and local not in encontrados:
            encontrados.append(local)

    if not encontrados:
        ui("  no se encontraron drivers instalados manualmente")
        return

    for path in encontrados:
        try:
            os.remove(path)
            ui(f"  eliminado: {path}")
        except PermissionError:
            if SO == "Linux":
                ui(f"  requiere sudo: {path}")
                try:
                    result = subprocess.run(["sudo", "rm", path], capture_output=True, text=True)
                    if result.returncode == 0:
                        ui(f"  eliminado con sudo: {path}")
                    else:
                        ui(f"  no se pudo eliminar: {path}")
                        ui(f"  ejecuta manualmente: sudo rm {path}")
                except Exception as e:
                    ui(f"  error: {e}")
            else:
                ui(f"  sin permisos: {path}")
        except Exception as e:
            ui(f"  error: {e}")

# -----------------------------------------------------------------------------
# ELIMINAR DRIVERS INSTALADOS VIA APT (solo Linux)
# apt remove es la forma correcta — pip y os.remove no pueden tocar paquetes apt
# Detecta instalacion apt si el driver esta en /usr/bin
# -----------------------------------------------------------------------------

def eliminar_drivers_apt():
    if SO != "Linux":
        return

    paquetes_apt = {
        "geckodriver":  "firefox-geckodriver",
        "chromedriver": "chromium-driver",
    }

    for driver, paquete_apt in paquetes_apt.items():
        path = shutil.which(driver)
        if not path:
            continue
        # /usr/bin indica instalacion via apt — /usr/local/bin es instalacion manual
        if "/usr/bin" in path:
            if confirmar(f"Eliminar {paquete_apt} instalado via apt?"):
                try:
                    result = subprocess.run(
                        ["sudo", "apt", "remove", "-y", paquete_apt],
                        capture_output=True, text=True
                    )
                    if result.returncode == 0:
                        ui(f"  {paquete_apt} eliminado via apt")
                    else:
                        ui(f"  no se pudo eliminar: {result.stderr.strip()}")
                except Exception as e:
                    ui(f"  error: {e}")

# -----------------------------------------------------------------------------
# ELIMINAR LOG
# -----------------------------------------------------------------------------

def eliminar_log():
    log_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "sesion_log.txt")
    if os.path.exists(log_file):
        tamano = os.path.getsize(log_file)
        if tamano < 1024:
            tamano_str = f"{tamano} B"
        elif tamano < 1024 * 1024:
            tamano_str = f"{tamano / 1024:.1f} KB"
        else:
            tamano_str = f"{tamano / (1024 * 1024):.1f} MB"
        try:
            os.remove(log_file)
            ui(f"  log eliminado ({tamano_str}): {log_file}")
        except Exception as e:
            ui(f"  error eliminando log: {e}")
    else:
        ui("  log no encontrado")

    # Tambien limpiar log antiguo si existe
    log_antiguo = os.path.join(os.path.dirname(os.path.abspath(__file__)), "sence_log.txt")
    if os.path.exists(log_antiguo):
        try:
            os.remove(log_antiguo)
            ui(f"  log antiguo eliminado: {log_antiguo}")
        except Exception as e:
            ui(f"  error eliminando log antiguo: {e}")

# -----------------------------------------------------------------------------
# LIMPIAR CACHE DE PIP
# Almacena paquetes descargados — no necesario tras desinstalar
# -----------------------------------------------------------------------------

def limpiar_cache_pip():
    ui("Limpiando cache de pip...")
    try:
        result = subprocess.run(
            [sys.executable, "-m", "pip", "cache", "purge"],
            capture_output=True, text=True
        )
        if result.returncode == 0:
            ui("  cache de pip limpiado")
        else:
            ui(f"  advertencia: {result.stderr.strip()}")
    except Exception as e:
        ui(f"  error: {e}")

# -----------------------------------------------------------------------------
# LIMPIAR __pycache__
# Bytecode compilado .pyc — se regenera automaticamente
# -----------------------------------------------------------------------------

def limpiar_pycache():
    pycache = os.path.join(os.path.dirname(os.path.abspath(__file__)), "__pycache__")
    if os.path.exists(pycache):
        try:
            shutil.rmtree(pycache)
            ui("  __pycache__ eliminado")
        except Exception as e:
            ui(f"  error: {e}")
    else:
        ui("  __pycache__ no encontrado")

# -----------------------------------------------------------------------------
# INSTRUCCIONES DE REINSTALACION
# -----------------------------------------------------------------------------

def mostrar_reinstalacion():
    ui("Para volver a instalar ejecuta:")
    print()

    if SO == "Linux":
        print("  # selenium")
        print("  pip install selenium --break-system-packages")
        print()
        print("  # geckodriver -- opcion 1 (apt)")
        print("  sudo apt install firefox-geckodriver")
        print()
        print("  # geckodriver -- opcion 2 (manual, si apt no funciona)")
        print("  wget https://github.com/mozilla/geckodriver/releases/download/v0.36.0/geckodriver-v0.36.0-linux64.tar.gz")
        print("  tar -xzf geckodriver-v0.36.0-linux64.tar.gz")
        print("  sudo mv geckodriver /usr/local/bin/")
        print("  sudo chmod +x /usr/local/bin/geckodriver")
        print()
        print("  O simplemente ejecuta sesion.py -- se instala solo.")

    elif SO == "Darwin":
        print("  pip install selenium")
        print("  brew install geckodriver")

    elif SO == "Windows":
        print("  pip install selenium")
        print()
        print("  Descargar geckodriver desde:")
        print("  https://github.com/mozilla/geckodriver/releases")
        print("  Copiar geckodriver.exe a la carpeta de sesion.py")

# -----------------------------------------------------------------------------
# PROGRAMA PRINCIPAL
# -----------------------------------------------------------------------------

def main():
    print()
    print("  +-------------------------------------------+")
    print("  |  Renovador de sesion -- Limpiador          |")
    print("  +-------------------------------------------+")
    print()
    print("  Esto eliminara:")
    print("  - selenium y sus dependencias")
    print("  - geckodriver / chromedriver / msedgedriver")
    print("  - sesion_log.txt  (pregunta antes)")
    print("  - cache de pip y __pycache__")
    print()
    print("  NO se eliminan: sesion.py, limpiar.py, README.md")
    print()

    if SO == "Linux" and not es_root():
        print("  NOTA: Algunos pasos pueden requerir sudo.")
        print("  El programa lo pedira automaticamente.")
        print()

    if not confirmar("Confirmas que quieres limpiar todo?"):
        print("\n  Cancelado.\n")
        return

    print()
    ui("Iniciando limpieza...")
    print()

    desinstalar_selenium()
    print()

    eliminar_drivers()
    print()

    eliminar_drivers_apt()
    print()

    if confirmar("Eliminar el archivo de log (sesion_log.txt)?"):
        eliminar_log()
    else:
        ui("  log conservado")

    print()
    limpiar_cache_pip()
    limpiar_pycache()

    print()
    ui("Limpieza completada.")
    print()
    mostrar_reinstalacion()
    print()


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"\n  Error critico: {e}")
        sys.exit(1)
