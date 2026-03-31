# =============================================================================
# Renovador de sesion automatico
# =============================================================================
# Mantiene activa la sesion en una plataforma web haciendo click en el
# modulo del curso cada 30 minutos antes de que la sesion expire.
#
# Compatible: Linux (Kali/Debian/Ubuntu), macOS, Windows
# Navegadores: Firefox, Chrome, Edge (detecta automaticamente)
#
# Uso:     python3 sesion.py
# Detener: Ctrl+C  o  q + ENTER
# =============================================================================

import sys
import os
import shutil
import platform
import time
import threading
import logging
import subprocess
import gc
import importlib
import json
import urllib.request
import zipfile
import tarfile
from datetime import datetime

# -----------------------------------------------------------------------------
# ENCODING SEGURO
# Previene errores de codificacion en terminales que no soportan UTF-8
# Windows PowerShell y cmd pueden fallar con caracteres especiales
# -----------------------------------------------------------------------------

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

# -----------------------------------------------------------------------------
# CONFIGURACION GLOBAL
# -----------------------------------------------------------------------------

URL_LOGIN    = "https://auladigital.sence.cl/login/index.php"
URL_CURSO    = "https://auladigital.sence.cl/course/view.php?id=6076"
INTERVALO    = 30 * 60

LOG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "sesion_log.txt")
inicio   = time.time()
SO       = platform.system()

logging.getLogger("selenium").setLevel(logging.CRITICAL)
logging.getLogger("urllib3").setLevel(logging.CRITICAL)

modo_rapido = threading.Event()
salir       = threading.Event()

# -----------------------------------------------------------------------------
# ASCII ART
# Diseno con reloj de arena — compatible UTF-8 con fallback seguro
# -----------------------------------------------------------------------------

LOGO = r"""
                +++++++++++++++++++++++++++
                +++++++++++++++++++++++++++
               +++                        ++
              +++                          ++
              ++                            ++
             ++                             ++
             ++                              ++
             ++                              ++
             ++                      +++++  ++
              ++  +++++++++++++++++++++++   ++
              ++   +++++++++++++++++++++   +++
               ++   +++++++++++++++++++   +++
                +++   +++++++++++++++    +++
                  +++     ++++++++    ++++
                    ++     +++++     +++
                     ++    +++++     ++
                    ++               +++
                  +++                 ++++
                +++                     +++
               +++                        ++
              +++                          ++
              ++                            ++
             ++                             ++
             ++  ++++++++++++++++++++++ ++   ++
             ++  +++++++++++++++++++++++++   ++
             ++   ++++++++++++++++++++++++   ++
              ++  +++++++++++++++++++++++   ++
              ++   +++++++++++++++++++++   +++
               ++                         +++
                ++++++++++++++++++++++++++++
                ++++++++++++++++++++++++++++
"""

TITULO = "Renovador de sesion"

def _imprimir_logo():
    """Imprime el logo y titulo con emojis si el terminal los soporta."""
    try:
        print(LOGO)
        linea = f"  {TITULO}"
        # Intentar emojis — si falla, se usa version sin ellos
        try:
            emoji_linea = f"              {chr(8987)} {TITULO} {chr(9203)}"
            print(emoji_linea)
        except (UnicodeEncodeError, UnicodeDecodeError):
            print(f"              {TITULO}")
        print()
    except Exception:
        # Fallback minimo si todo falla
        print(f"\n  === {TITULO} ===\n")

# -----------------------------------------------------------------------------
# LOGGING
# log()  -> archivo (formato maquina, util para debug)
# ui()   -> pantalla (formato humano, legible para el usuario)
# -----------------------------------------------------------------------------

def log_separador():
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write("\n" + "=" * 60 + "\n\n")

def log(nivel, msg):
    uptime = int(time.time() - inicio)
    linea  = f"[{datetime.now().strftime('%H:%M:%S')}][{nivel}][up={uptime}s] {msg}"
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(linea + "\n")

def ui(msg):
    print(f"\n[{datetime.now().strftime('%H:%M:%S')}] {msg}")

def mostrar_bienvenida():
    _imprimir_logo()
    print("  " + "-" * 34)
    print()

# -----------------------------------------------------------------------------
# GESTION DEL LOG
# Verifica el tamano antes de iniciar y ofrece limpiarlo
# -----------------------------------------------------------------------------

def verificar_log():
    if not os.path.exists(LOG_FILE):
        return

    tamano = os.path.getsize(LOG_FILE)
    if tamano < 1024:
        tamano_str = f"{tamano} B"
    elif tamano < 1024 * 1024:
        tamano_str = f"{tamano / 1024:.1f} KB"
    else:
        tamano_str = f"{tamano / (1024 * 1024):.1f} MB"

    print(f"\n  Log existente: {tamano_str} -- {LOG_FILE}")
    if input("  Limpiar el log antes de iniciar? (s/n): ").strip().lower() == "s":
        try:
            os.remove(LOG_FILE)
            print("  Log eliminado.")
        except Exception as e:
            print(f"  No se pudo eliminar: {e}")

# -----------------------------------------------------------------------------
# CONTRASENA CON MASCARA (#)
# - Windows: msvcrt — incluido en Python/Windows
# - Linux/macOS: tty + termios — modulos POSIX, no existen en Windows
# -----------------------------------------------------------------------------

def pedir_contrasena():
    print("  Contrasena: ", end="", flush=True)
    password = ""

    if SO == "Windows":
        import msvcrt
        while True:
            ch = msvcrt.getwch()
            if ch in ("\r", "\n"):
                print()
                break
            elif ch == "\x03":
                raise KeyboardInterrupt
            elif ch in ("\x7f", "\x08"):
                if password:
                    password = password[:-1]
                    print("\b \b", end="", flush=True)
            else:
                password += ch
                print("#", end="", flush=True)
    else:
        import tty
        import termios
        fd  = sys.stdin.fileno()
        old = termios.tcgetattr(fd)
        try:
            tty.setraw(fd)
            while True:
                ch = sys.stdin.read(1)
                if ch in ("\r", "\n"):
                    print()
                    break
                elif ch in ("\x7f", "\x08"):
                    if password:
                        password = password[:-1]
                        print("\b \b", end="", flush=True)
                elif ch == "\x03":
                    raise KeyboardInterrupt
                else:
                    password += ch
                    print("#", end="", flush=True)
        finally:
            termios.tcsetattr(fd, termios.TCSADRAIN, old)

    return password

# -----------------------------------------------------------------------------
# DETECCION DE NAVEGADOR
# Prioridad: Firefox > Chrome > Edge
# Linux: shutil.which() en PATH
# macOS: /Applications/
# Windows: %ProgramFiles% con rutas fijas
# -----------------------------------------------------------------------------

NAVEGADORES_CONFIG = {
    "firefox": {
        "cmds_linux": ["firefox", "firefox-esr"],
        "driver":     "geckodriver",
        "win_paths": [
            r"%ProgramFiles%\Mozilla Firefox\firefox.exe",
            r"%ProgramFiles(x86)%\Mozilla Firefox\firefox.exe",
        ],
        "mac_path": "/Applications/Firefox.app",
        "driver_install": {
            "Linux": [
                "opcion 1 (apt):    sudo apt install firefox-geckodriver",
                "opcion 2 (manual): wget https://github.com/mozilla/geckodriver/releases/download/v0.36.0/geckodriver-v0.36.0-linux64.tar.gz",
                "                   tar -xzf geckodriver-v0.36.0-linux64.tar.gz",
                "                   sudo mv geckodriver /usr/local/bin/",
                "                   sudo chmod +x /usr/local/bin/geckodriver",
            ],
            "Darwin":  ["brew install geckodriver"],
            "Windows": ["https://github.com/mozilla/geckodriver/releases"],
        },
    },
    "chrome": {
        "cmds_linux": ["google-chrome", "chromium", "chromium-browser"],
        "driver":     "chromedriver",
        "win_paths": [
            r"%ProgramFiles%\Google\Chrome\Application\chrome.exe",
            r"%ProgramFiles(x86)%\Google\Chrome\Application\chrome.exe",
            r"%LocalAppData%\Google\Chrome\Application\chrome.exe",
        ],
        "mac_path": "/Applications/Google Chrome.app",
        "driver_install": {
            "Linux":   ["sudo apt install chromium-driver"],
            "Darwin":  ["brew install chromedriver"],
            "Windows": ["https://chromedriver.chromium.org/downloads"],
        },
    },
    "edge": {
        "cmds_linux": ["microsoft-edge"],
        "driver":     "msedgedriver",
        "win_paths": [
            r"%ProgramFiles%\Microsoft\Edge\Application\msedge.exe",
            r"%ProgramFiles(x86)%\Microsoft\Edge\Application\msedge.exe",
        ],
        "mac_path": "/Applications/Microsoft Edge.app",
        "driver_install": {
            "Linux":   ["https://developer.microsoft.com/microsoft-edge/tools/webdriver"],
            "Darwin":  ["https://developer.microsoft.com/microsoft-edge/tools/webdriver"],
            "Windows": ["https://developer.microsoft.com/microsoft-edge/tools/webdriver"],
        },
    },
}

def detectar_navegador():
    for nombre, config in NAVEGADORES_CONFIG.items():
        if SO == "Windows":
            for p in config["win_paths"]:
                ruta = os.path.expandvars(p)
                if os.path.exists(ruta):
                    return nombre, ruta
        elif SO == "Darwin":
            if os.path.exists(config["mac_path"]):
                return nombre, config["mac_path"]
        else:
            for cmd in config["cmds_linux"]:
                ruta = shutil.which(cmd)
                if ruta:
                    return nombre, ruta
    return None, None

def detectar_driver(navegador):
    driver_cmd = NAVEGADORES_CONFIG[navegador]["driver"]
    path = shutil.which(driver_cmd)
    if not path and SO == "Windows":
        local = os.path.join(os.path.dirname(os.path.abspath(__file__)), driver_cmd + ".exe")
        if os.path.exists(local):
            return local
    return path

# -----------------------------------------------------------------------------
# IMPORTACION SELECTIVA DE SELENIUM
# Importa solo los modulos del navegador detectado — menos carga al arrancar
# -----------------------------------------------------------------------------

def importar_selenium(navegador):
    webdriver_mod = importlib.import_module("selenium.webdriver")
    modulo_base   = f"selenium.webdriver.{navegador}"
    Options       = importlib.import_module(f"{modulo_base}.options").Options
    Service       = importlib.import_module(f"{modulo_base}.service").Service
    BrowserDriver = getattr(webdriver_mod, navegador.capitalize())
    By     = importlib.import_module("selenium.webdriver.common.by").By
    Wait   = importlib.import_module("selenium.webdriver.support.ui").WebDriverWait
    Select = importlib.import_module("selenium.webdriver.support.ui").Select
    EC     = importlib.import_module("selenium.webdriver.support.expected_conditions")
    return BrowserDriver, Options, Service, By, Wait, Select, EC

# -----------------------------------------------------------------------------
# INSTALACION AUTOMATICA
# Orden: pip -> herramientas -> navegador -> selenium -> driver
# En sistema limpio con solo Python instala todo lo necesario
# -----------------------------------------------------------------------------

def instalar_pip():
    try:
        subprocess.run([sys.executable, "-m", "pip", "--version"], capture_output=True, check=True)
    except Exception:
        ui("  pip no encontrado -- instalando...")
        subprocess.run([sys.executable, "-m", "ensurepip", "--upgrade"], capture_output=True)
        log("OK", "pip=installed")
    subprocess.run(
        [sys.executable, "-m", "pip", "install", "--upgrade", "pip", "-q"],
        capture_output=True
    )

def instalar_herramientas_linux():
    # wget/curl necesarios para descargar drivers si apt falla
    # tar necesario para descomprimir archivos descargados
    herramientas = []
    if not shutil.which("wget") and not shutil.which("curl"):
        herramientas.append("wget")
    if not shutil.which("tar"):
        herramientas.append("tar")
    if herramientas:
        ui(f"  Instalando herramientas del sistema: {', '.join(herramientas)}")
        subprocess.run(["sudo", "apt", "install", "-y"] + herramientas, capture_output=True)
        log("OK", f"tools=installed {herramientas}")

def instalar_firefox_linux():
    if shutil.which("firefox") or shutil.which("firefox-esr"):
        return
    ui("  Firefox no encontrado -- instalando via apt...")
    log("INFO", "firefox=auto_install_start")
    subprocess.run(["sudo", "apt", "update", "-qq"], capture_output=True)
    result = subprocess.run(["sudo", "apt", "install", "-y", "firefox-esr"], capture_output=True, text=True)
    if result.returncode == 0:
        ui("  Firefox instalado correctamente")
        log("OK", "firefox=auto_installed")
    else:
        ui("  No se pudo instalar Firefox -- instala manualmente: sudo apt install firefox-esr")
        log("ERR", "firefox=install_failed")

def instalar_selenium():
    try:
        import selenium
        return True
    except ImportError:
        pass
    ui("  selenium no encontrado -- instalando...")
    flags  = ["--break-system-packages"] if SO == "Linux" else []
    result = subprocess.run(
        [sys.executable, "-m", "pip", "install", "selenium", "-q"] + flags,
        capture_output=True, text=True
    )
    if result.returncode == 0:
        ui("  selenium instalado correctamente")
        log("OK", "selenium=auto_installed")
        return True
    log("ERR", f"selenium=install_failed msg={result.stderr.strip()[:100]}")
    return False

def obtener_url_geckodriver():
    """Consulta la API de GitHub para obtener la URL de descarga del ultimo geckodriver."""
    api_url = "https://api.github.com/repos/mozilla/geckodriver/releases/latest"
    try:
        req  = urllib.request.Request(api_url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode())
            tag  = data['tag_name']
            
            # Mapeo de arquitectura
            arch = platform.machine().lower()
            system = SO.lower()
            
            target = ""
            if system == "windows":
                target = "win64.zip" if "64" in arch else "win32.zip"
            elif system == "linux":
                target = "linux64.tar.gz" if "64" in arch else "linux32.tar.gz"
            elif system == "darwin":
                target = "macos.tar.gz" if "arm" not in arch else "macos-aarch64.tar.gz"

            for asset in data['assets']:
                if target in asset['name']:
                    return asset['browser_download_url'], tag
    except Exception as e:
        log("ERR", f"github_api_failed msg={e}")
    return None, None

def instalar_geckodriver():
    """Instalacion robusta de geckodriver con descarga automatica multiplataforma."""
    driver_name = "geckodriver"
    exe_name    = driver_name + (".exe" if SO == "Windows" else "")
    local_dir   = os.path.dirname(os.path.abspath(__file__))
    destino     = os.path.join(local_dir, exe_name)

    if detectar_driver("firefox"):
        log("OK", "geckodriver=found_in_path")
        return True

    ui(f"  {driver_name} no encontrado -- Iniciando autoinstalacion robusta...")
    url, tag = obtener_url_geckodriver()
    
    if not url:
        ui("  Error: No se pudo obtener la URL de descarga de GitHub.")
        return False

    temp_file = os.path.join(local_dir, "geckodriver_temp" + (".zip" if "zip" in url else ".tar.gz"))
    
    try:
        log("INFO", f"downloading_driver version={tag} url={url}")
        ui(f"  Descargando {driver_name} {tag}...")
        
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=30) as resp, open(temp_file, 'wb') as f:
            f.write(resp.read())

        ui("  Extrayendo binario...")
        if temp_file.endswith(".zip"):
            with zipfile.ZipFile(temp_file, 'r') as zip_ref:
                zip_ref.extractall(local_dir)
        else:
            with tarfile.open(temp_file, "r:gz") as tar_ref:
                tar_ref.extractall(local_dir)

        if os.path.exists(temp_file):
            os.remove(temp_file)

        if SO != "Windows":
            os.chmod(destino, 0o755)

        # Validacion final
        try:
            ver = subprocess.check_output([destino, "--version"], text=True).split("\n")[0]
            ui(f"  Instalacion exitosa: {ver}")
            log("OK", f"geckodriver_installed path={destino} version={ver}")
            return True
        except Exception as ve:
            log("ERR", f"driver_validation_failed msg={ve}")
            return False

    except Exception as e:
        ui(f"  Error critico en instalacion: {e}")
        log("ERR", f"geckodriver_install_failed msg={e}")
        return False

def instalar_faltantes(navegador):
    ui("Revisando e instalando dependencias faltantes...")
    log("INFO", "auto_install=start")

    instalar_pip()

    if SO == "Linux":
        instalar_herramientas_linux()
        if not detectar_navegador()[0]:
            instalar_firefox_linux()

    instalar_selenium()

    if navegador == "firefox":
        instalar_geckodriver()
    elif not detectar_driver(navegador):
        config = NAVEGADORES_CONFIG[navegador]["driver_install"]
        ui("  Driver no encontrado.")
        for linea in config.get(SO, []):
            ui(f"  {linea}")

    log("INFO", "auto_install=complete")

# -----------------------------------------------------------------------------
# VERIFICACION DE DEPENDENCIAS
# Se ejecuta despues de instalar — confirma que todo quedo bien
# -----------------------------------------------------------------------------

def verificar_dependencias(navegador):
    ok = True
    log("INFO", f"os={SO} kernel={platform.release()} python={sys.version.split()[0]}")
    ui("Verificando dependencias...")

    has_manager = False
    try:
        import selenium
        log("OK", f"selenium={selenium.__version__}")
        ui(f"  selenium OK -- v{selenium.__version__}")
        
        # Selenium 4.6.0+ incluye Selenium Manager para autogestionar drivers
        v_parts = [int(x) for x in selenium.__version__.split(".") if x.isdigit()]
        if len(v_parts) >= 2 and (v_parts[0] > 4 or (v_parts[0] == 4 and v_parts[1] >= 6)):
            has_manager = True
            log("INFO", "selenium_manager=available")
    except ImportError:
        log("ERR", "selenium=missing")
        ui("  ERROR: selenium no instalado")
        ui("  Instala con: pip install selenium" + (" --break-system-packages" if SO == "Linux" else ""))
        ok = False

    driver_path = detectar_driver(navegador)
    driver_name = NAVEGADORES_CONFIG[navegador]["driver"]

    if not driver_path:
        if has_manager:
            log("INFO", f"{driver_name}=missing action=use_selenium_manager")
            ui(f"  {driver_name} no encontrado localmente (se usara Selenium Manager)")
        else:
            log("ERR", f"{driver_name}=missing")
            ui(f"  ERROR: {driver_name} no encontrado")
            for linea in NAVEGADORES_CONFIG[navegador]["driver_install"].get(SO, []):
                ui(f"  {linea}")
            ok = False
    else:
        try:
            ver = subprocess.check_output([driver_path, "--version"], stderr=subprocess.DEVNULL).decode().strip().split("\n")[0]
            log("OK", f"{driver_name}={driver_path} version={ver}")
            ui(f"  {driver_name} OK -- {ver}")
        except Exception:
            log("OK", f"{driver_name}={driver_path} version=unknown")
            ui(f"  {driver_name} OK")

    if not ok:
        log("ERR", "deps=incomplete exit=1")
        ui("\nCorrige los errores anteriores y vuelve a ejecutar.")
        input("\n  Presiona ENTER para salir...")
        sys.exit(1)

# -----------------------------------------------------------------------------
# ENTRADA DE DATOS
# -----------------------------------------------------------------------------

def pedir_modo():
    print("\n  +-----------------------------------+")
    print("  |       modo de ejecucion           |")
    print("  +-----------------------------------+")
    print("  |  1.  solo terminal                |")
    print("  |      navegador en segundo plano   |")
    print("  |                                   |")
    print("  |  2.  con ventana visible          |")
    print("  |      navegador abierto            |")
    print("  +-----------------------------------+")
    while True:
        opcion = input("\n  Elige 1 o 2: ").strip()
        if opcion == "1":
            return True
        elif opcion == "2":
            return False
        print("  Opcion invalida, elige 1 o 2.")

def pedir_credenciales():
    print("\n  +-----------------------------------+")
    print("  |       credenciales                |")
    print("  |       Clave Unica                 |")
    print("  |  no se guardan en disco           |")
    print("  +-----------------------------------+")
    rut = input("\n  RUN (sin puntos, con guion Ej: 12345678-9): ").strip()
    if not rut:
        ui("  ERROR: RUN no puede estar vacio.")
        sys.exit(1)
    password = pedir_contrasena()
    if not password:
        ui("  ERROR: Contrasena no puede estar vacia.")
        sys.exit(1)
    return rut, password

# -----------------------------------------------------------------------------
# INICIAR NAVEGADOR
# Firefox: -headless (un guion)
# Chrome/Edge: --headless=new (dos guiones, Chromium)
# --no-sandbox: requerido en Linux como root (Kali)
# --disable-dev-shm-usage: evita crashes por /dev/shm limitado
# -----------------------------------------------------------------------------

def iniciar_driver(navegador, headless, BrowserDriver, Options, Service):
    """Configuracion avanzada de capacidades oficiales de Firefox/Chromium."""
    driver_path = detectar_driver(navegador)
    opciones    = Options()

    # Configuracion de PageLoadStrategy y Timeouts
    opciones.page_load_strategy = 'normal' # Asegura que scripts de redireccion terminen
    
    if navegador == "firefox":
        if headless:
            opciones.add_argument("-headless")
        # Optimizacion de logs y estabilidad
        opciones.set_preference("browser.tabs.remote.autostart", False)
        opciones.set_preference("dom.ipc.processCount", 1)
    else:
        if headless:
            opciones.add_argument("--headless=new")
        opciones.add_argument("--no-sandbox")
        opciones.add_argument("--disable-dev-shm-usage")
        opciones.add_experimental_option("excludeSwitches", ["enable-logging"])

    service = Service(
        executable_path=driver_path if driver_path else None,
        log_output=os.devnull
    )
    
    try:
        driver = BrowserDriver(options=opciones, service=service)
        # Timeout implicito de seguridad (capa base)
        driver.implicitly_wait(5)
        log("OK", f"browser=started name={navegador} headless={headless} strategy=normal")
        return driver
    except Exception as e:
        log("ERR", f"browser_init_failed msg={e}")
        raise

# -----------------------------------------------------------------------------
# LOGIN
# Paso 1: formulario de la plataforma (RUT + selector de curso dinamico via JS)
# Paso 2: formulario Clave Unica del gobierno (RUN + contrasena)
# Si falla headless: reinicia en modo visible para login manual
# -----------------------------------------------------------------------------

def hacer_login(driver, rut, password, headless, navegador, selenium_mod):
    """Flujo de login resiliente con manejo de redirecciones externas y reintentos."""
    BrowserDriver, Options, Service, By, Wait, Select, EC = selenium_mod
    intentos_max = 3
    
    for intento in range(1, intentos_max + 1):
        try:
            t = time.time()
            log("INFO", f"login_attempt={intento} url={URL_LOGIN}")
            ui(f"Iniciando sesion (Intento {intento}/{intentos_max})...")
            
            driver.get(URL_LOGIN)
            
            # Paso 1: Plataforma SENCE
            wait_sence = Wait(driver, 20)
            wait_sence.until(EC.presence_of_element_located((By.ID, "rut")))
            driver.find_element(By.ID, "rut").send_keys(rut)
            driver.find_element(By.TAG_NAME, "body").click()
            
            # Espera dinamica a que el selector de curso cargue opciones
            wait_sence.until(lambda d: len(Select(d.find_element(By.ID, "curso")).options) > 0)
            select = Select(driver.find_element(By.ID, "curso"))
            opciones = [o for o in select.options if o.text.strip()]
            
            opcion_elegida = opciones[0]
            if len(opciones) > 1 and intento == 1: # Solo preguntar la primera vez
                print("\n  Cursos disponibles:")
                for i, o in enumerate(opciones, 1):
                    print(f"  {i}. {o.text.strip()}")
                seleccion = input("  Selecciona el numero de curso: ").strip()
                try:
                    opcion_elegida = opciones[int(seleccion) - 1]
                except:
                    opcion_elegida = opciones[0]
            
            select.select_by_value(opcion_elegida.get_attribute("value"))
            ui(f"  Curso: {opcion_elegida.text.strip()[:50]}")
            
            driver.find_element(By.ID, "btnLogin").click()
            
            # Paso 2: Redireccion Clave Unica (DOMINIO EXTERNO)
            log("INFO", "waiting_for_clave_unica_redirect")
            ui("  Redirigiendo a Clave Unica (gob.cl)...")
            
            # Sincronizacion critica: esperar cambio de URL y presencia de campos
            wait_gov = Wait(driver, 30)
            wait_gov.until(EC.url_contains("claveunica.gob.cl"))
            wait_gov.until(EC.visibility_of_element_located((By.ID, "uname")))
            
            driver.find_element(By.ID, "uname").send_keys(rut)
            driver.find_element(By.ID, "pword").send_keys(password)
            driver.find_element(By.ID, "login-submit").click()
            
            # Paso 3: Retorno a plataforma
            ui("  Validando retorno a plataforma...")
            wait_gov.until(EC.url_contains("auladigital"))
            
            # Verificar si las credenciales fueron invalidas
            time.sleep(2)
            try:
                error = driver.find_element(By.CSS_SELECTOR, ".alert, .error, #error-message")
                ui(f"  ERROR: {error.text.strip()}")
                log("ERR", f"auth_failed msg={error.text.strip()}")
                return driver # No reintentar si el error es de clave
            except:
                pass

            driver.get(URL_CURSO)
            Wait(driver, 20).until(EC.url_contains("course/view.php"))
            
            log("OK", f"login_success duration={time.time()-t:.1f}s")
            ui(f"  Sesion iniciada exitosamente.")
            return driver

        except Exception as e:
            log("WARN", f"login_attempt={intento} failed error={type(e).__name__}")
            ui(f"  Intento {intento} fallido. " + ("Reintentando..." if intento < intentos_max else ""))
            if intento == intentos_max:
                raise e
            time.sleep(5)
            
    return driver

# -----------------------------------------------------------------------------
# CICLO PRINCIPAL
# -----------------------------------------------------------------------------

def limpiar_cache(driver):
    try:
        driver.execute_script("window.localStorage.clear(); window.sessionStorage.clear();")
        log("INFO", "browser_cache=cleared")
    except Exception as e:
        log("WARN", f"browser_cache=clear_failed msg={e}")

def obtener_dedicacion(driver, By):
    try:
        elemento   = driver.find_element(By.CSS_SELECTOR, ".block_dedication .card-text p:nth-child(2)")
        dedicacion = elemento.text.strip()
        log("INFO", f"dedication={dedicacion}")
        ui(f"  Horas acumuladas: {dedicacion}")
    except Exception:
        log("WARN", "dedication=not_found")

def hacer_click(driver, selenium_mod):
    By, Wait, EC = selenium_mod[3], selenium_mod[4], selenium_mod[6]
    try:
        t = time.time()
        driver.get(URL_CURSO)

        if "login" in driver.current_url:
            log("ERR", f"session=expired redirect={driver.current_url}")
            ui("  ERROR: La sesion expiro. Reinicia el programa.")
            sys.exit(1)

        todos   = driver.find_elements(By.CSS_SELECTOR, "a[href]")
        modulos = driver.find_elements(By.CSS_SELECTOR, "a[href*='750764']")
        log("DEBUG", f"curso_loaded title={driver.title!r} t={time.time()-t:.1f}s url={driver.current_url} page_links={len(todos)} modulo_750764={len(modulos)}")

        elemento = Wait(driver, 15).until(
            EC.element_to_be_clickable((By.CSS_SELECTOR, "a[href*='750764']"))
        )
        log("DEBUG", f"modulo_element href={elemento.get_attribute('href')} text={elemento.text.strip()[:40]!r} visible={elemento.is_displayed()} enabled={elemento.is_enabled()}")
        elemento.click()

        Wait(driver, 15).until(EC.url_contains("750764"))
        log("DEBUG", f"modulo_loaded title={driver.title!r} t={time.time()-t:.1f}s url={driver.current_url}")

        driver.back()
        Wait(driver, 15).until(EC.url_contains("course/view.php"))
        log("OK", f"cycle_complete title={driver.title!r} t={time.time()-t:.1f}s url={driver.current_url}")

        obtener_dedicacion(driver, By)
        limpiar_cache(driver)
        gc.collect()
        return True

    except Exception as e:
        log("ERR", f"cycle=failed exception={type(e).__name__} msg={e} url={driver.current_url}")
        ui("  Error durante el ciclo.")
        return False

# -----------------------------------------------------------------------------
# INTERFAZ DE TERMINAL
# escuchar_teclas() corre en hilo separado — no bloquea el ciclo principal
# daemon=True: muere automaticamente cuando el programa principal termina
# -----------------------------------------------------------------------------

def escuchar_teclas():
    while True:
        try:
            tecla = input().strip().lower()
            if tecla == "f":
                log("INFO", "fast_forward=activated")
                modo_rapido.set()
            elif tecla == "q":
                log("INFO", "quit=requested")
                salir.set()
                modo_rapido.set()
        except Exception:
            break

def barra_espera(segundos, proximo):
    ancho = 34
    ui(f"  Proximo click a las {proximo}")
    print(f"  f + ENTER = avanzar   q + ENTER = salir\n")
    log("INFO", f"wait_start seconds={segundos} until={proximo}")

    for restante in range(segundos, 0, -1):
        if modo_rapido.is_set():
            modo_rapido.clear()
            if salir.is_set():
                print()
                return
            log("INFO", f"wait_skipped remaining={restante}s")
            for r2 in range(2, 0, -1):
                print(f"\r  [ avance rapido ] proximo click en {r2}s  ", end="", flush=True)
                time.sleep(1)
            print()
            return

        llenos = int(ancho * restante / segundos)
        barra  = "#" * llenos + "." * (ancho - llenos)
        print(f"\r  [{barra}]  {restante // 60:02d}:{restante % 60:02d}", end="", flush=True)
        time.sleep(1)

    print()
    log("INFO", "wait_complete")

# -----------------------------------------------------------------------------
# PROGRAMA PRINCIPAL
# Flujo: log -> deteccion -> instalacion -> verificacion -> modo -> login -> ciclos
# -----------------------------------------------------------------------------

def main():
    mostrar_bienvenida()

    verificar_log()

    log_separador()
    log("INFO", "program=start")
    log("INFO", f"log_file={LOG_FILE}")
    log("INFO", "storage=log_only credentials=memory_only")

    # Detectar navegador disponible
    navegador, ruta = detectar_navegador()

    # Si no hay navegador en Linux, intentar instalar Firefox
    if not navegador and SO == "Linux":
        instalar_firefox_linux()
        navegador, ruta = detectar_navegador()

    if not navegador:
        log("ERR", "browser=none_found")
        ui("  ERROR: No se encontro ningun navegador compatible.")
        ui("  Instala Firefox, Chrome o Edge.")
        sys.exit(1)

    log("INFO", f"browser=detected name={navegador} path={ruta}")
    ui(f"  Navegador detectado: {navegador} -- {ruta}")

    # Paso 1 — instalar dependencias faltantes
    instalar_faltantes(navegador)

    # Paso 2 — verificar que todo quedo correctamente instalado
    verificar_dependencias(navegador)

    # Paso 3 — importar selenium solo despues de confirmar instalacion
    selenium_mod                    = importar_selenium(navegador)
    BrowserDriver, Options, Service = selenium_mod[0], selenium_mod[1], selenium_mod[2]

    headless      = pedir_modo()
    rut, password = pedir_credenciales()

    log("INFO", f"browser={navegador} headless={headless}")
    ui(f"Iniciando {navegador} {'en segundo plano' if headless else 'con ventana visible'}...")

    driver = iniciar_driver(navegador, headless, BrowserDriver, Options, Service)

    try:
        driver = hacer_login(driver, rut, password, headless, navegador, selenium_mod)

        # Limpiar credenciales de memoria inmediatamente
        rut = password = None
        gc.collect()
        log("OK", "credentials=cleared_from_memory")

        log("INFO", "keybinds: f=skip_to_next_click q=quit")
        hilo = threading.Thread(target=escuchar_teclas, daemon=True)
        hilo.start()

        ciclo = errores = 0

        while True:
            if salir.is_set():
                break

            ciclo += 1
            log("INFO", f"cycle={ciclo} errors={errores} uptime={int(time.time()-inicio)}s url={URL_CURSO}")

            print("\n  " + "-" * 34)
            ui(f"  Ciclo #{ciclo}")
            print("  " + "-" * 34)

            if hacer_click(driver, selenium_mod):
                errores = 0
                proximo = datetime.fromtimestamp(time.time() + INTERVALO).strftime('%H:%M:%S')
                log("OK", f"cycle={ciclo} status=success next_click={proximo}")
                barra_espera(INTERVALO, proximo)
            else:
                errores += 1
                log("WARN", f"cycle={ciclo} status=failed consecutive_errors={errores}")
                ui(f"  Fallo #{errores}")
                if errores >= 3:
                    log("WARN", f"errors=3 action=reload url={URL_CURSO}")
                    ui("  3 fallos consecutivos -- recargando...")
                    driver.get(URL_CURSO)
                    time.sleep(5)
                    errores = 0
                else:
                    proximo = datetime.fromtimestamp(time.time() + 120).strftime('%H:%M:%S')
                    log("INFO", "retry_in=120s")
                    ui("  Reintentando en 2 minutos...")
                    barra_espera(120, proximo)

    except KeyboardInterrupt:
        log("INFO", f"program=stopped_by_user cycles_completed={ciclo} total_uptime={int(time.time()-inicio)}s")

    finally:
        if salir.is_set():
            log("INFO", f"program=quit_by_user cycles_completed={ciclo} total_uptime={int(time.time()-inicio)}s")

        print("\n\n  " + "-" * 34)
        ui(f"  Programa detenido.")
        ui(f"  Ciclos completados: {ciclo}")
        ui(f"  Tiempo total:       {int(time.time()-inicio)}s")
        print("  " + "-" * 34)

        try:
            if 'driver' in locals():
                driver.quit()
        except Exception:
            pass
        log("INFO", "browser=closed program=end")
        ui("  Navegador cerrado.")
        input("\n  Presiona ENTER para salir...")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        pass
    except Exception as e:
        print(f"\n  Error critico: {e}")
        input("\n  Presiona ENTER para salir...")
        sys.exit(1)
