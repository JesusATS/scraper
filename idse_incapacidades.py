# -*- coding: utf-8 -*-
"""
IDSE IMSS — Scraper de Incapacidades
=====================================
Requisitos:
    pip install selenium openpyxl
Uso:
    python idse_incapacidades.py
"""

import csv
import logging
import os
import time
from datetime import datetime

from selenium import webdriver
from selenium.common.exceptions import (
    NoSuchElementException,
    StaleElementReferenceException,
    TimeoutException,
)
from selenium.webdriver.common.by import By
from selenium.webdriver.edge.options import Options as EdgeOptions
from selenium.webdriver.edge.service import Service as EdgeService
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

from credentials import ImssCredentials, load_imss_credentials

# ===========================================================================
# CONFIGURACIÓN — EDITA AQUÍ
# ===========================================================================

SCRIPT_DIR  = os.path.dirname(os.path.abspath(__file__))
OUTPUT_DIR  = os.path.join(SCRIPT_DIR, "resultados")
LOG_DIR     = os.path.join(SCRIPT_DIR, "logs")
DEBUG_DIR   = os.path.join(SCRIPT_DIR, "debug")

BASE_URL    = "https://idse.imss.gob.mx/imss/"
TIMEOUT     = 20
PAUSA_CORTA = 1.5
PAUSA_LOGIN = 5

# ─────────────────────────────────────────────────────────────────────────────
# MODO EXPLORACIÓN:
#   True  → navega a todos los módulos, guarda HTMLs y genera reporte.
#           Úsalo para identificar qué módulo tiene incapacidades.
#   False → va directo al módulo definido en MODULO_INCAPACIDADES.
# ─────────────────────────────────────────────────────────────────────────────
MODO_EXPLORACION = False

# Una vez identificado el módulo correcto, cámbialo aquí y pon MODO_EXPLORACION = False
# Opciones: afiliacion, emision, confronta, dapsua, ppe, satic,
#           dictamen, irRTT, sipress, incidencias, dictamenOracle
MODULO_INCAPACIDADES = "emision"  # ← confirmado correcto

# Todos los módulos disponibles en el portal IDSE
TODOS_LOS_MODULOS = {
    "afiliacion":     "Movimientos Afiliatorios",
    "emision":        "Emision",
    "confronta":      "Confronta",
    "dapsua":         "DAPSUA",
    "ppe":            "PPE",
    "satic":          "SATIC",
    "dictamen":       "Dictamen",
    "irRTT":          "RTT",
    "sipress":        "SIPRESS",
    "incidencias":    "Incidencias",
    "dictamenOracle": "Dictamen Oracle",
}

# ===========================================================================
# LOGGING
# ===========================================================================

for _d in (OUTPUT_DIR, LOG_DIR, DEBUG_DIR):
    os.makedirs(_d, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(
            os.path.join(
                LOG_DIR, "idse_{}.log".format(datetime.now().strftime("%Y%m%d_%H%M%S"))
            ),
            encoding="utf-8",
        ),
        logging.StreamHandler(),
    ],
)
log = logging.getLogger(__name__)


# ===========================================================================
# UTILIDADES
# ===========================================================================

def cargar_credenciales():
    """Wrapper sobre credentials.load_imss_credentials() — fija SCRIPT_DIR."""
    return load_imss_credentials(SCRIPT_DIR)


def crear_driver():
    ruta_driver = os.path.join(SCRIPT_DIR, "msedgedriver")
    if os.name == "nt":
        ruta_driver += ".exe"
    if not os.path.exists(ruta_driver):
        raise FileNotFoundError(
            "No se encontro msedgedriver en: {}\n"
            "Descargalo en: https://developer.microsoft.com/microsoft-edge/tools/webdriver/\n"
            "Luego ejecuta: chmod +x msedgedriver && xattr -d com.apple.quarantine msedgedriver".format(SCRIPT_DIR)
        )
    prefs = {
        "download.default_directory": OUTPUT_DIR,
        "download.prompt_for_download": False,
        "download.directory_upgrade": True,
        "safebrowsing.enabled": True,
        "profile.default_content_setting_values.automatic_downloads": 1,
    }
    options = EdgeOptions()
    options.add_experimental_option("prefs", prefs)
    # Descomenta para ejecutar sin ventana:
    # options.add_argument("--headless=new")
    service = EdgeService(executable_path=ruta_driver)
    driver = webdriver.Edge(service=service, options=options)
    driver.maximize_window()
    return driver


def guardar_html(driver, nombre):
    ruta = os.path.join(DEBUG_DIR, nombre)
    with open(ruta, "w", encoding="utf-8") as f:
        f.write(driver.page_source)
    log.info("  HTML guardado: %s", ruta)


def scroll_click(driver, elemento):
    driver.execute_script("arguments[0].scrollIntoView({block:'center'});", elemento)
    time.sleep(0.4)
    driver.execute_script("arguments[0].click();", elemento)


# ===========================================================================
# FASE 1 — LOGIN
# ===========================================================================

def cerrar_modal(driver):
    xpaths = [
        "//div[contains(@class,'modal-footer')]//button",
        "//button[contains(@class,'close') or @data-dismiss='modal']",
        "//*[@data-dismiss='modal']",
    ]
    for xpath in xpaths:
        try:
            btn = WebDriverWait(driver, 3).until(EC.element_to_be_clickable((By.XPATH, xpath)))
            driver.execute_script("arguments[0].click();", btn)
            log.info("Modal cerrado.")
            time.sleep(1)
            return
        except TimeoutException:
            continue


def cerrar_popups(driver):
    try:
        WebDriverWait(driver, 4).until(EC.number_of_windows_to_be(2))
        principal = driver.window_handles[0]
        driver.switch_to.window(driver.window_handles[1])
        driver.close()
        driver.switch_to.window(principal)
        log.info("Pop-up cerrado.")
    except TimeoutException:
        pass


def iniciar_sesion(driver, creds: ImssCredentials):
    wait  = WebDriverWait(driver, TIMEOUT)

    log.info("Navegando al portal IDSE...")
    driver.get(BASE_URL)
    cerrar_modal(driver)

    try:
        # Los campos certificado y llave son <input type="file">
        # El navegador bloquea asignar rutas via JS por seguridad.
        # send_keys() es el único método válido para inputs de tipo file.
        log.info("Enviando certificado (.cer)...")
        campo = wait.until(EC.presence_of_element_located((By.ID, "certificado")))
        campo.send_keys(creds.ruta_cer)
        time.sleep(PAUSA_CORTA)

        log.info("Enviando llave privada (.key)...")
        campo = wait.until(EC.presence_of_element_located((By.ID, "llave")))
        campo.send_keys(creds.ruta_key)
        time.sleep(PAUSA_CORTA)

        log.info("Llenando usuario...")
        campo = wait.until(EC.element_to_be_clickable((By.ID, "idUsuario")))
        campo.clear()
        campo.send_keys(creds.usuario)

        log.info("Llenando contrasena...")
        campo = wait.until(EC.element_to_be_clickable((By.ID, "password")))
        campo.clear()
        campo.send_keys(creds.contrasena)

        log.info("Esperando que el boton 'Iniciar sesion' se habilite...")
        try:
            WebDriverWait(driver, 10).until(
                lambda d: not d.find_element(By.ID, "botonFirma").get_attribute("disabled")
            )
            log.info("Boton habilitado.")
        except TimeoutException:
            log.warning("El boton no se habilito. Intentando clic de todas formas...")

        log.info("Haciendo clic en 'Iniciar sesion'...")
        btn = driver.find_element(By.ID, "botonFirma")
        driver.execute_script("arguments[0].removeAttribute('disabled'); arguments[0].click();", btn)

        log.info("Esperando respuesta del servidor (max 30 seg)...")
        try:
            WebDriverWait(driver, 30).until(
                EC.invisibility_of_element_located((By.ID, "idModalWaitProcess"))
            )
        except TimeoutException:
            log.warning("El modal de procesamiento no desaparecio. Continuando...")

        time.sleep(2)

    except TimeoutException as e:
        log.error("Timeout durante login: %s", e)
        guardar_html(driver, "debug_login_timeout.html")
        return False

    cerrar_popups(driver)

    try:
        driver.find_element(By.ID, "password")
        try:
            err = driver.find_element(By.ID, "imsgErrors").text.strip()
            if err:
                log.error("Error del portal: %s", err)
        except NoSuchElementException:
            pass
        log.error(
            "Login fallido. Verifica IMSS_RUTA_CER, IMSS_RUTA_KEY y IMSS_CONTRASENA "
            "(en .env o variables de entorno; o los campos equivalentes en config.ini legacy)."
        )
        guardar_html(driver, "debug_login_fallido.html")
        return False
    except NoSuchElementException:
        log.info("Login exitoso.")
        guardar_html(driver, "debug_portal_principal.html")
        return True


# ===========================================================================
# MODO EXPLORACIÓN
# ===========================================================================

def explorar_todos_modulos(driver):
    log.info("=" * 60)
    log.info("  MODO EXPLORACION: revisando %d modulos", len(TODOS_LOS_MODULOS))
    log.info("=" * 60)

    KEYWORDS_BUSCAR = ["incapacidad", "incap", "ST-", "dias", "baja", "subsidio", "medica"]

    reporte = [
        "REPORTE DE EXPLORACION — PORTAL IDSE",
        "Fecha: {}".format(datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
        "=" * 60,
        "",
        "Keywords buscadas: {}".format(", ".join(KEYWORDS_BUSCAR)),
        "",
        "=" * 60,
    ]

    for key, nombre in TODOS_LOS_MODULOS.items():
        log.info("Explorando: %s (irA=%s)...", nombre, key)
        url = "https://idse.imss.gob.mx/imss/Modulos.idse?irA={}".format(key)

        try:
            driver.get(url)
            time.sleep(PAUSA_CORTA * 2)
        except Exception as e:
            log.warning("  Error: %s", e)
            reporte.append("MODULO: {} (irA={}) — ERROR: {}".format(nombre, key, e))
            continue

        if "botonFirma" in driver.page_source or "idUsuario" in driver.page_source:
            log.warning("  Sesion expirada. Deteniendo exploracion.")
            reporte.append("** SESION EXPIRADA — exploracion incompleta **")
            break

        nombre_html = "explorar_{}.html".format(key)
        guardar_html(driver, nombre_html)

        try:
            body_text = driver.find_element(By.TAG_NAME, "body").text
        except Exception:
            body_text = ""

        encontradas = [kw for kw in KEYWORDS_BUSCAR if kw.lower() in body_text.lower()]
        palabras = body_text.split()
        resumen = " ".join(palabras[:80])

        reporte += [
            "",
            "MODULO: {} (irA={})".format(nombre, key),
            "  HTML: debug/{}".format(nombre_html),
            "  Keywords encontradas: {}".format(encontradas if encontradas else "ninguna"),
            "  Texto (resumen): {}".format(resumen[:500]),
            "  " + "-" * 56,
        ]

        if encontradas:
            log.info("  *** CANDIDATO: keywords=%s", encontradas)
        else:
            log.info("  Sin keywords de incapacidades.")

        time.sleep(1)

    reporte += [
        "",
        "=" * 60,
        "PROXIMOS PASOS:",
        "1. Identifica el modulo con keywords relevantes",
        "2. Abre su .html en debug/ para confirmar visualmente",
        "3. Cambia MODULO_INCAPACIDADES al valor irA correcto",
        "4. Pon MODO_EXPLORACION = False",
        "5. Ejecuta el script de nuevo",
        "=" * 60,
    ]

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    ruta = os.path.join(OUTPUT_DIR, "reporte_exploracion_{}.txt".format(timestamp))
    with open(ruta, "w", encoding="utf-8") as f:
        f.write("\n".join(reporte))

    log.info("Reporte guardado: %s", ruta)
    return ruta


# ===========================================================================
# FASE 2 — NAVEGAR AL MÓDULO
# ===========================================================================

# Mapeo de módulo → número de irA() según el portal
IRA_NUMEROS = {
    "afiliacion":     1,
    "emision":        2,
    "confronta":      3,
    "dapsua":         4,
    "satic":          5,
    "dictamen":       6,
    "irRTT":          8,
    "sipress":        101,
    "incidencias":    102,
}

def navegar_a_modulo(driver):
    """
    Navega al módulo haciendo clic en el enlace del menú (javascript:irA(N)).
    Este es el método más confiable ya que replica exactamente lo que hace el usuario.
    """
    numero = IRA_NUMEROS.get(MODULO_INCAPACIDADES)
    log.info("Navegando al modulo '%s' (irA=%s)...", MODULO_INCAPACIDADES, numero)

    # Asegurarse de estar en el menú principal (donde existe frmDatos y los enlaces)
    if "frmDatos" not in driver.page_source:
        log.info("Regresando al menu principal...")
        driver.get(BASE_URL)
        time.sleep(PAUSA_CORTA * 2)

    # Estrategia 1: clic en el enlace javascript:irA(N) del menú
    if numero:
        try:
            xpath = "//a[@href='javascript:irA({});']".format(numero)
            enlace = driver.find_element(By.XPATH, xpath)
            scroll_click(driver, enlace)
            log.info("Clic en enlace irA(%s) realizado.", numero)
            time.sleep(PAUSA_CORTA * 3)
            if _sesion_valida(driver):
                log.info("Modulo '%s' cargado correctamente.", MODULO_INCAPACIDADES)
                guardar_html(driver, "debug_modulo_incapacidades.html")
                return True
        except NoSuchElementException:
            log.warning("Enlace irA(%s) no encontrado. Intentando via frmDatos...", numero)

    # Estrategia 2: submit del formulario frmDatos
    try:
        script = (
            "var f = document.querySelector('form[name=frmDatos]');"
            "if(!f) throw new Error('frmDatos no encontrado');"
            "f.target='_self';"
            "f.action='/imss/Modulos.idse?irA=" + MODULO_INCAPACIDADES + "';"
            "f.submit();"
        )
        driver.execute_script(script)
        time.sleep(PAUSA_CORTA * 3)
        if _sesion_valida(driver):
            log.info("Modulo cargado via frmDatos.")
            guardar_html(driver, "debug_modulo_incapacidades.html")
            return True
    except Exception as e:
        log.error("Error via frmDatos: %s", e)

    guardar_html(driver, "debug_modulo_error.html")
    log.error("No se pudo navegar al modulo '%s'.", MODULO_INCAPACIDADES)
    return False


def _sesion_valida(driver):
    """Verifica que la página actual no sea un error de sesión o de sistema del IMSS."""
    src = driver.page_source
    
    # 1. Detectar el Error 1200 del IMSS
    if "código 1200" in src or "Error en el proceso" in src:
        log.error("El IMSS arrojó el Error 1200 (Módulo no aplicable o sin acceso para este patrón).")
        return False
        
    # 2. Detectar sesión inválida
    if "#01001" in src or "sesi" in src.lower() and "inv" in src.lower():
        log.error("Sesión inválida detectada.")
        return False
        
    # 3. Detectar si nos pateó al login
    if "botonFirma" in src or "idUsuario" in src:
        log.error("Redirigido al login.")
        return False
        
    return True


# ===========================================================================
# FASE 2.5 — APLICAR FILTROS DE BÚSQUEDA (si los hay)
# ===========================================================================

def aplicar_filtros_busqueda(driver, fecha_inicio=None, fecha_fin=None):
    """Llena filtros de fecha. fecha_inicio/fecha_fin opcionales en formato dd/mm/yyyy.
    Si no vienen, default = último año (modo histórico)."""
    """
    Detecta y llena automáticamente formularios de búsqueda en el módulo.
    Busca campos de fecha y aplica un rango del último año por defecto.
    """
    wait = WebDriverWait(driver, 5)

    # Detectar si hay campos de fecha en la página
    selectores_fecha = [
        (By.ID, "fechaInicio"),
        (By.ID, "fechainicio"),
        (By.ID, "fecIni"),
        (By.ID, "fecInicio"),
        (By.NAME, "fechaInicio"),
        (By.NAME, "fecIni"),
        (By.XPATH, "//input[@type='date' or contains(@id,'echa') or contains(@name,'echa')]"),
    ]

    campo_fecha_inicio = None
    campo_fecha_fin = None

    for by, selector in selectores_fecha:
        try:
            campo_fecha_inicio = driver.find_element(by, selector)
            log.info("Campo de fecha inicio encontrado: %s=%s", by, selector)
            break
        except NoSuchElementException:
            continue

    if not campo_fecha_inicio:
        log.info("No se detectaron filtros de fecha. Continuando sin filtros.")
        return

    # Si vienen fechas explícitas (modo date_range del orquestador), usarlas;
    # si no, default histórico = último año (comportamiento previo).
    # NOTA: las firmas locales sobreescriben fecha_ini/fecha_fin del kwargs.
    from datetime import date, timedelta
    hoy = date.today()
    hace_un_anio = hoy - timedelta(days=365)
    fecha_ini = fecha_inicio if fecha_inicio else hace_un_anio.strftime("%d/%m/%Y")
    fecha_fin = fecha_fin if fecha_fin else hoy.strftime("%d/%m/%Y")

    log.info("Aplicando filtro de fechas: %s al %s", fecha_ini, fecha_fin)

    try:
        campo_fecha_inicio.clear()
        campo_fecha_inicio.send_keys(fecha_ini)
    except Exception as e:
        log.warning("No se pudo llenar fecha inicio: %s", e)

    # Buscar campo de fecha fin
    selectores_fin = [
        (By.ID, "fechaFin"),
        (By.ID, "fechafin"),
        (By.ID, "fecFin"),
        (By.NAME, "fechaFin"),
        (By.NAME, "fecFin"),
    ]
    for by, selector in selectores_fin:
        try:
            campo_fecha_fin = driver.find_element(by, selector)
            campo_fecha_fin.clear()
            campo_fecha_fin.send_keys(fecha_fin)
            log.info("Campo fecha fin llenado: %s", fecha_fin)
            break
        except NoSuchElementException:
            continue

    # Buscar y hacer clic en botón de búsqueda pero no es 
    selectores_btn = [
        (By.XPATH, "//button[contains(text(),'Buscar') or contains(text(),'Consultar') or contains(text(),'buscar')]"),
        (By.XPATH, "//input[@type='button' and (contains(@value,'Buscar') or contains(@value,'Consultar'))]"),
        (By.XPATH, "//input[@type='submit']"),
        (By.ID, "btnBuscar"),
        (By.ID, "btnConsultar"),
        (By.NAME, "buscar"),
    ]
    for by, selector in selectores_btn:
        try:
            btn = driver.find_element(by, selector)
            scroll_click(driver, btn)
            log.info("Botón de búsqueda presionado.")
            time.sleep(PAUSA_CORTA * 2)
            break
        except NoSuchElementException:
            continue


# ===========================================================================
# FASE 3 — EXTRACCIÓN
# ===========================================================================

def extraer_todos_los_datos(driver):
    todos = []
    tablas = driver.find_elements(By.TAG_NAME, "table")
    log.info("Tablas encontradas: %d", len(tablas))

    if not tablas:
        log.warning("Sin tablas. Guardando HTML para diagnostico...")
        guardar_html(driver, "debug_sin_tablas.html")
        return todos

    for idx, tabla in enumerate(tablas, 1):
        filas = _parsear_tabla(tabla, "T{}_".format(idx))
        log.info("  Tabla %d: %d filas.", idx, len(filas))
        todos.extend(filas)

    pagina = 2
    while _ir_siguiente_pagina(driver):
        log.info("Pagina %d...", pagina)
        time.sleep(PAUSA_CORTA)
        for idx, tabla in enumerate(driver.find_elements(By.TAG_NAME, "table"), 1):
            filas = _parsear_tabla(tabla, "P{}T{}_".format(pagina, idx))
            todos.extend(filas)
        pagina += 1

    log.info("Total registros: %d", len(todos))
    return todos


def _parsear_tabla(tabla, prefijo=""):
    registros = []
    try:
        filas = tabla.find_elements(By.TAG_NAME, "tr")
    except StaleElementReferenceException:
        return registros

    if len(filas) < 2:
        return registros

    primera = filas[0]
    celdas_enc = primera.find_elements(By.TAG_NAME, "th") or \
                 primera.find_elements(By.TAG_NAME, "td")
    encabezados = []
    for i, c in enumerate(celdas_enc):
        texto = c.text.strip().replace("\n", " ")
        encabezados.append(texto if texto else "{}Col{}".format(prefijo, i + 1))

    if not encabezados:
        return registros

    for fila in filas[1:]:
        try:
            celdas = fila.find_elements(By.TAG_NAME, "td")
            if not celdas:
                continue
            valores = [c.text.strip().replace("\n", " ") for c in celdas]
            while len(valores) < len(encabezados):
                valores.append("")
            registro = dict(zip(encabezados, valores[:len(encabezados)]))
            registro["_fecha_extraccion"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            registros.append(registro)
        except StaleElementReferenceException:
            continue

    return registros


def _ir_siguiente_pagina(driver):
    xpaths = [
        "//a[normalize-space(text())='Siguiente' or normalize-space(text())='>']",
        "//button[contains(text(),'Siguiente')]",
        "//*[contains(@class,'next') or contains(@class,'siguiente')]",
    ]
    for xpath in xpaths:
        try:
            btn = driver.find_element(By.XPATH, xpath)
            if btn.get_attribute("disabled") or "disabled" in (btn.get_attribute("class") or ""):
                return False
            scroll_click(driver, btn)
            time.sleep(PAUSA_CORTA)
            return True
        except (NoSuchElementException, StaleElementReferenceException):
            continue
    return False


# ===========================================================================
# FASE 4 — CSV
# ===========================================================================

def guardar_csv(registros, ruta):
    if not registros:
        log.warning("Sin registros para guardar.")
        return
    campos = list(registros[0].keys())
    if "_fecha_extraccion" in campos:
        campos.remove("_fecha_extraccion")
        campos.append("_fecha_extraccion")
    with open(ruta, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=campos, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(registros)
    log.info("CSV guardado: %s (%d registros)", ruta, len(registros))


# ===========================================================================
# MAIN
# ===========================================================================

def main(creds=None, search_params=None):
    """
    Entry point del scraper IDSE.

    Args:
        creds: ImssCredentials opcional. Si es None, se cargan de env / .env /
               config.ini (modo CLI / backwards compat).
        search_params: SearchParams opcional (de scraper_input). Si es None,
                       comportamiento previo (modo "historico"-like).

    Returns:
        Exit code (0 éxito, 1 falla scraping, 3 error configuración).
        El orquestador puede usar este código para detectar éxito.
    """
    log.info("=" * 60)
    log.info("  IDSE IMSS — Scraper de Incapacidades")
    log.info("  Fecha: %s", datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    log.info("  Modo: %s", "EXPLORACION" if MODO_EXPLORACION else "EXTRACCION")
    if search_params is not None:
        log.info("  Search mode: %s", search_params.mode)
    log.info("=" * 60)

    # Credenciales: inyectadas (orquestador) o cargadas de env (CLI)
    if creds is None:
        try:
            creds = cargar_credenciales()
        except Exception as e:
            log.error("Error cargando credenciales: %s", e)
            return 3

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    driver = None

    try:
        driver = crear_driver()

        if not iniciar_sesion(driver, creds):
            log.error("Login fallido.")
            return 1

        # ── MODO EXPLORACIÓN ────────────────────────────────────────
        if MODO_EXPLORACION:
            ruta = explorar_todos_modulos(driver)
            log.info("")
            log.info("Exploracion completada.")
            log.info("  Reporte → %s", ruta)
            log.info("  HTMLs   → %s", DEBUG_DIR)
            return 0
        # ────────────────────────────────────────────────────────────

        if not navegar_a_modulo(driver):
            log.error("No se pudo acceder al modulo. Revisa MODULO_INCAPACIDADES.")
            return 1

        # Aplicar filtros de búsqueda según el modo
        aplicar_busqueda(driver, search_params)

        registros = extraer_todos_los_datos(driver)

        if not registros:
            log.warning(
                "Sin datos. Revisa debug/debug_modulo_incapacidades.html — "
                "puede que el modulo requiera aplicar filtros de fecha primero."
            )
            return 1

        ruta_csv = os.path.join(OUTPUT_DIR, "incapacidades_{}.csv".format(timestamp))
        guardar_csv(registros, ruta_csv)
        log.info("Proceso completado. CSV → %s", ruta_csv)
        return 0

    except Exception as e:
        log.exception("Error inesperado: %s", e)
        if driver:
            guardar_html(driver, "debug_error_{}.html".format(timestamp))
        return 1
    finally:
        if driver:
            driver.quit()
            log.info("Navegador cerrado.")


def aplicar_busqueda(driver, search_params):
    """
    Dispatcher de búsqueda según el modo solicitado por el orquestador.

    Modos:
      - "historico" o None: comportamiento previo (rango último año por default)
      - "date_range": rango específico (fecha_inicio, fecha_fin)
      - "nss": búsqueda por NSS — TODO Fase B: selectores UI específicos

    Cada rama llama a aplicar_filtros_busqueda() con argumentos distintos.
    """
    if search_params is None or search_params.mode == "historico":
        log.info("Modo: HISTORICO (rango default último año)")
        aplicar_filtros_busqueda(driver)
        return

    if search_params.mode == "date_range":
        fi = search_params.fecha_inicio.strftime("%d/%m/%Y")
        ff = search_params.fecha_fin.strftime("%d/%m/%Y")
        log.info("Modo: DATE_RANGE (%s al %s)", fi, ff)
        aplicar_filtros_busqueda(driver, fecha_inicio=fi, fecha_fin=ff)
        return

    if search_params.mode == "nss":
        log.warning(
            "Modo: NSS=%s — IMPLEMENTACION PENDIENTE (Fase B). "
            "El selector UI específico del portal IDSE para búsqueda por NSS "
            "requiere validación contra el portal real dentro de mx-central-1. "
            "Por ahora se aplican filtros default.",
            search_params.nss,
        )
        # TODO Fase B: navegar al modulo correcto, llenar input de NSS,
        # disparar búsqueda. Selectores XPath/CSS pendientes de identificar.
        aplicar_filtros_busqueda(driver)
        return


if __name__ == "__main__":
    import sys as _sys

    _sys.exit(main() or 0)