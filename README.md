# Renovador de Sesion

```
                +++++++++++++++++++++++++++
                +++++++++++++++++++++++++++
               +++                        ++
              +++                          ++
              ++                            ++
             ++                             ++
             ++                              ++
             ++                              ++
             ++                      +++++   ++
              ++  +++++++++++++++++++++++   ++
              ++   +++++++++++++++++++++   +++
               ++   +++++++++++++++++++   +++
                +++   +++++++++++++++    +++
                  +++     ++++++++    ++++
                    ++     +++++     +++
                     ++    +++++     ++
                    ++        ++     +++
                  +++       ++        ++++
                +++                     +++
               +++                        ++
              +++  ⏳Renovador de sesion⌛  ++
              ++                             ++
             ++                              ++
             ++  ++++++++++++++++++++++ ++   ++
             ++  +++++++++++++++++++++++++   ++
             ++   ++++++++++++++++++++++++   ++
              ++  +++++++++++++++++++++++   ++
              ++   +++++++++++++++++++++   +++
               ++                         +++
                ++++++++++++++++++++++++++++
                ++++++++++++++++++++++++++++
```

---

## Que hace

Este programa mantiene activa una sesion web que expira si no se hace click en un elemento.
Cada 30 minutos navega automaticamente al modulo del curso, registra la actividad y vuelve a esperar.
El estudiante solo necesita hacer login una vez y el programa se encarga del resto.

---

## Como funciona

1. Detecta el navegador instalado (Firefox, Chrome o Edge)
2. Instala automaticamente las dependencias que falten
3. Ofrece limpiar el log anterior antes de iniciar
4. Pregunta si correr con ventana visible o en segundo plano
5. Pide RUN y contrasena — no se guardan en disco
6. Hace login automatico via Clave Unica
7. Cada 30 minutos navega al modulo y registra la actividad
8. Vuelve al curso y espera el siguiente ciclo
9. Guarda todo en un log para facilitar el debug

---

## Arbol del proyecto

```
renovador-de-sesion/
├── sesion.py         — programa principal
├── limpiar.py        — desinstala todo para volver a empezar
├── README.md         — este archivo
└── sesion_log.txt    — generado automaticamente al ejecutar
```

---

## Flujo completo

```
python3 sesion.py
        │
        ├── verificar_log()
        │       muestra tamano del log y ofrece limpiarlo
        │
        ├── detectar_navegador()
        │       Firefox > Chrome > Edge
        │
        ├── instalar_faltantes()
        │       ├── instalar_pip()
        │       │       verifica y actualiza pip
        │       ├── instalar_herramientas_linux()
        │       │       wget, curl, tar si faltan
        │       ├── instalar_firefox_linux()
        │       │       si no hay ningun navegador
        │       ├── instalar_selenium()
        │       │       pip install automatico
        │       └── instalar_geckodriver()
        │               apt -> descarga directa desde GitHub
        │
        ├── verificar_dependencias()
        │       confirma que todo quedo bien
        │
        ├── importar_selenium()
        │       solo los modulos del navegador detectado
        │
        ├── pedir_modo()
        │       1 = segundo plano (headless)
        │       2 = ventana visible
        │
        ├── pedir_credenciales()
        │       RUN + contrasena con mascara (#)
        │       nunca se guardan en disco
        │
        ├── hacer_login()
        │       ├── formulario de la plataforma (RUT + curso)
        │       ├── redireccion a Clave Unica
        │       ├── formulario Clave Unica (RUN + contrasena)
        │       └── si falla -> abre ventana visible para login manual
        │
        └── BUCLE cada 30 minutos
                ├── navega a course/view.php
                ├── hace click en el modulo del curso
                ├── espera que cargue
                ├── vuelve al curso
                ├── muestra horas acumuladas
                └── limpia cache del navegador
```

---

## Carga para el sistema

El programa consume muy pocos recursos. El 99% del tiempo esta
durmiendo entre ciclos con `time.sleep()`.

| Momento | RAM | CPU |
|---------|-----|-----|
| Firefox headless esperando | 150 - 200 MB | 0 - 1% |
| Firefox con ventana visible | 250 - 350 MB | 1 - 2% |
| Durante el click (~3 segundos) | pico 400 MB | 5 - 15% |
| Python durmiendo | 10 MB | 0% |
| Red por ciclo | 2 - 5 MB | -- |

---

## Instalacion por sistema operativo

### Linux / Kali -- instalacion automatica

El programa detecta lo que falta y lo instala solo al ejecutarse:

```bash
python3 sesion.py
```

Si prefieres instalar manualmente:

```bash
# selenium
pip install selenium --break-system-packages

# geckodriver opcion 1 (apt)
sudo apt install firefox-geckodriver

# geckodriver opcion 2 (si apt no funciona -- probado en Kali)
wget https://github.com/mozilla/geckodriver/releases/download/v0.36.0/geckodriver-v0.36.0-linux64.tar.gz
tar -xzf geckodriver-v0.36.0-linux64.tar.gz
sudo mv geckodriver /usr/local/bin/
sudo chmod +x /usr/local/bin/geckodriver
geckodriver --version
```

### macOS

```bash
brew install python
pip install selenium
brew install geckodriver
```

### Windows

```bash
pip install selenium
```

Descargar geckodriver desde:
`https://github.com/mozilla/geckodriver/releases`

Buscar `geckodriver-vX.XX.X-win64.zip`, descomprimir y copiar
`geckodriver.exe` a la misma carpeta que `sesion.py`.

---

## Uso

```bash
python3 sesion.py
```

Al iniciar el programa verifica el log existente:

```
  Log existente: 24.3 KB -- /ruta/sesion_log.txt
  Limpiar el log antes de iniciar? (s/n):
```

Luego pregunta el modo:

```
  1. Solo terminal  -- Firefox corre invisible
  2. Ventana visible -- Firefox se abre en pantalla
```

Y las credenciales:

```
  RUN: 12345678-9
  Contrasena: ########
```

### Comandos durante la ejecucion

| Tecla | Accion |
|-------|--------|
| `f` + ENTER | Salta al proximo click en 2 segundos |
| `q` + ENTER | Cierra el programa limpiamente |
| Ctrl+C | Detiene el programa |

### Barra de progreso

```
  [################..................]  14:32
```

---

## Navegadores compatibles

| Navegador | Driver | Autoinstalacion |
|-----------|--------|-----------------|
| Firefox | geckodriver | Linux: automatica / macOS: brew / Windows: manual |
| Chrome | chromedriver | manual en todos los SO |
| Edge | msedgedriver | manual en todos los SO |

El programa usa el primero que encuentre en el sistema.

---

## Log

Archivo `sesion_log.txt` generado automaticamente.
Formato para debug claro:

```
[HH:MM:SS][NIVEL][up=Xs] clave=valor clave=valor
```

Ejemplo de ejecucion exitosa:

```
[09:45:57][OK]    selenium=4.41.0
[09:45:57][OK]    geckodriver=0.36.0
[09:46:22][OK]    curso_selected value=6076
[09:46:36][OK]    login=success t=18.5s
[09:46:39][OK]    cycle_complete t=2.3s
[09:46:39][INFO]  dedication=194 hours 41 mins
[09:46:39][OK]    cycle=1 status=success next_click=10:16:39
```

Niveles: `OK` | `INFO` | `DEBUG` | `WARN` | `ERR`

Cada ejecucion queda separada por `====` en el archivo.

---

## Seguridad

- Las credenciales se piden por consola con mascara (#)
- Nunca se escriben a disco en ningun momento
- Se borran de memoria inmediatamente despues del login
- El log no registra usuario ni contrasena

---

## Limpiar instalacion

```bash
python3 limpiar.py
```

Elimina selenium, drivers, log y cache.
No elimina sesion.py, limpiar.py ni README.md.

---

## Problemas frecuentes

**El programa no encuentra ningun navegador:**

```bash
sudo apt install firefox-esr        # Linux
brew install --cask firefox         # macOS
# Windows: descargar desde mozilla.org/firefox
```

**Login falla automaticamente:**
Selecciona modo con ventana visible (opcion 2) y completa
el login manualmente. El programa sigue desde ahi.

**La sesion expira igual:**
El modulo puede haber sido actualizado. Revisa el log
buscando `modulo_750764=0` y actualiza `URL_CURSO` en `sesion.py`.

**geckodriver incompatible con Firefox:**
geckodriver 0.36.0 es compatible con Firefox 140+.
Descarga desde: `https://github.com/mozilla/geckodriver/releases`

**Error de permisos en Linux:**

```bash
sudo chmod +x /usr/local/bin/geckodriver
```

---

## Requisitos minimos

| Componente | Minimo |
|------------|--------|
| Python | 3.8+ |
| selenium | 4.0+ |
| Firefox | 90+ |
| geckodriver | 0.30+ |
| RAM libre | 300 MB |
| Conexion a internet | requerida durante ejecucion |
