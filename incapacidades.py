# -*- coding: utf-8 -*-
import csv
import logging
import os
import time
from datetime import datetime, date, timedelta
import configparser

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

# ===========================================================================
# CONFIGURACIÓN Y DIRECTORIOS
# ===========================================================================
SCRIPT_DIR  = os.path.dirname(os.path.abspath(__file__))
OUTPUT_DIR  = os.path.join(SCRIPT_DIR, "resultados")
LOG_DIR     = os.path.join(SCRIPT_DIR, "logs")
DEBUG_DIR   = os.path.join(SCRIPT_DIR, "debug")

for _d in (OUTPUT_DIR, LOG_DIR, DEBUG_DIR):
    os.makedirs(_d, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(
            os.path.join(LOG_DIR, f"escritorio_virtual_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"), 
            encoding="utf-8"
        ),
        logging.StreamHandler(),
    ],
)
log = logging.getLogger(__name__)

# ===========================================================================
# UTILIDADES
# ===========================================================================
def cargar_config():
    config_path = os.path.join(SCRIPT_DIR, "config.ini")
    config = configparser.ConfigParser()
    if not config.read(config_path, encoding="utf-8"):
        raise FileNotFoundError(f"No se encontró config.ini en: {config_path}")
    if "IMSS_CREDENCIALES" not in config:
        raise KeyError("Falta la seccion [IMSS_CREDENCIALES] en config.ini")
    return config

def crear_driver():
    ruta_driver = os.path.join(SCRIPT_DIR, "msedgedriver")
    if os.name == "nt":
        ruta_driver += ".exe"
        
    prefs = {
        "download.default_directory": OUTPUT_DIR,
        "download.prompt_for_download": False,
        "download.directory_upgrade": True,
        "safebrowsing.enabled": True,
        "profile.default_content_setting_values.automatic_downloads": 1,
    }
    options = EdgeOptions()
    options.add_experimental_option("prefs", prefs)
    # options.add_argument("--headless=new") # Descomentar para modo oculto
    
    service = EdgeService(executable_path=ruta_driver)
    driver = webdriver.Edge(service=service, options=options)
    driver.maximize_window()
    return driver

def guardar_html(driver, nombre):
    ruta = os.path.join(DEBUG_DIR, nombre)
    with open(ruta, "w", encoding="utf-8") as f:
        f.write(driver.page_source)
    log.info(f"HTML guardado en debug: {nombre}")

# ===========================================================================
# FASE 1 - LOGIN EN ESCRITORIO VIRTUAL
# ===========================================================================
def iniciar_sesion_escritorio_virtual(driver, config):
    creds = config["IMSS_CREDENCIALES"]
    
    rfc = creds.get("RFC", creds.get("USUARIO", ""))
    ruta_cer = creds["RUTA_CER"]
    ruta_key = creds["RUTA_KEY"]
    contrasena = creds["CONTRASENA_SITIO"]
    
    wait = WebDriverWait(driver, 20)
    
    try:
        log.info("Navegando al Escritorio Virtual...")
        driver.get("https://serviciosdigitales.imss.gob.mx/portal-web/portal")
        
        # --- EL PASO QUE NOS FALTABA ---
        log.info("Haciendo clic en el botón 'Ingresar'...")
        btn_ingresar = wait.until(EC.element_to_be_clickable((By.ID, "enviarForm")))
        btn_ingresar.click()
        # --------------------------------
        
        log.info("Esperando a que carguen los iframes del login...")
        wait.until(EC.presence_of_element_located((By.TAG_NAME, "iframe")))
        time.sleep(3) # Pausa breve para que el IMSS termine de inyectar sus scripts
        
        # --- BUSCADOR INTELIGENTE DE IFRAMES ---
        iframes = driver.find_elements(By.TAG_NAME, "iframe")
        log.info(f"Se encontraron {len(iframes)} iframes. Buscando el formulario de login...")
        
        iframe_correcto = False
        for iframe in iframes:
            driver.switch_to.default_content() # Volvemos al inicio antes de entrar a otro
            try:
                driver.switch_to.frame(iframe)
                # Buscamos si existe el inputRFC en este iframe (con una espera cortita)
                if len(driver.find_elements(By.ID, "inputRFC")) > 0:
                    iframe_correcto = True
                    break # ¡Lo encontramos! Rompemos el ciclo y nos quedamos en este iframe
            except:
                continue
                
        if not iframe_correcto:
            raise Exception("No se encontró el iframe que contiene el login de la e.firma.")
            
        log.info("¡Dentro del iframe de login correcto!")
        
        # -----------------------------------------------------

        # 2. LLENAR EL RFC (Asegurando mayúsculas y sin espacios)
        rfc_limpio = rfc.strip().upper()
        log.info(f"Iniciando login con RFC: {rfc_limpio}")
        log.info(f"Ruta CER detectada: {ruta_cer}")
        
        campo_rfc = wait.until(EC.visibility_of_element_located((By.ID, "inputRFC")))
        campo_rfc.clear()
        campo_rfc.send_keys(rfc_limpio)
        driver.execute_script("arguments[0].dispatchEvent(new Event('change', { bubbles: true }));", campo_rfc)


        # 3. SUBIR CERTIFICADO (.cer)
        log.info("Inyectando archivo .cer...")
        campo_cer = wait.until(EC.presence_of_element_located((By.ID, "inputCertificado")))
        campo_cer.send_keys(ruta_cer)
        driver.execute_script("arguments[0].dispatchEvent(new Event('change', { bubbles: true }));", campo_cer)

        # 4. SUBIR LLAVE PRIVADA (.key)
        log.info("Inyectando archivo .key...")
        campo_key = wait.until(EC.presence_of_element_located((By.ID, "inputKey")))
        campo_key.send_keys(ruta_key)
        driver.execute_script("arguments[0].dispatchEvent(new Event('change', { bubbles: true }));", campo_key)

        # 5. INGRESAR CONTRASEÑA
        log.info("Escribiendo contraseña...")
        campo_pass = wait.until(EC.visibility_of_element_located((By.ID, "inputPassword")))
        campo_pass.clear()
        campo_pass.send_keys(contrasena)
        driver.execute_script("arguments[0].dispatchEvent(new Event('change', { bubbles: true }));", campo_pass)

        
        time.sleep(2) # Pausa estratégica para que la librería del IMSS procese los archivos

        # 6. HACER CLIC EN VALIDAR
        log.info("Validando e.firma...")
        btn_validar = wait.until(EC.element_to_be_clickable((By.ID, "botonValidarCert")))
        btn_validar.click()

        # Regresar al contexto principal fuera del iframe
        driver.switch_to.default_content()

        log.info("Esperando a que la página principal cargue después del login...")
        time.sleep(8) 
        log.info("¡Login completado con éxito!")
        guardar_html(driver, "debug_escritorio_virtual_inicio.html")
        return True

    except Exception as e:
        log.error(f"Error durante el login: {e}")
        # Asegurarnos de guardar el HTML del contexto principal si falla
        driver.switch_to.default_content() 
        guardar_html(driver, "debug_error_login_ev.html")
        return False

# ===========================================================================
# CONFIGURACIÓN DE MODO
# ===========================================================================
# True  → explora todos los portlets y genera reporte. Úsalo primero para
#         identificar qué sección contiene las incapacidades.
# False → va directo a la URL definida en RUTA_INCAPACIDADES.
MODO_EXPLORACION = True

# Una vez identificada la sección en el reporte, pon aquí la URL completa
# y cambia MODO_EXPLORACION = False.
RUTA_INCAPACIDADES = ""

PORTAL_BASE = "https://serviciosdigitales.imss.gob.mx"
KEYWORDS_INCAP = ["incapacidad", "subsidio", "st-", "días", "dias", "baja", "médica", "medica", "enfermedad"]

# Registro patronal asociado a la cuenta. Se usa para ingresar al portal patrón
# donde están los trámites de los trabajadores (incapacidades, movimientos, etc.)
REGISTRO_PATRONAL = "A8084992107"


# ===========================================================================
# FASE 2 — EXPLORACIÓN DEL PORTAL
# ===========================================================================

def _esperar_portlets(driver, timeout=25):
    """Espera hasta que al menos un portlet tenga contenido cargado."""
    log.info("Esperando que los portlets carguen su contenido via AJAX...")
    try:
        WebDriverWait(driver, timeout).until(
            lambda d: any(
                len(p.get_attribute("innerHTML") or "") > 50
                for p in d.find_elements(By.CSS_SELECTOR, "[portlet-url]")
            )
        )
        log.info("Portlets cargados.")
    except TimeoutException:
        log.warning("Tiempo de espera agotado para portlets. Continuando de todas formas.")
    time.sleep(3)


def ingresar_portal_patron(driver):
    """
    Expande el portlet de registros patronales (carga diferida) y hace clic en el
    registro patronal para entrar al portal empresa (portal patrón).
    El portlet usa lazy-loading: el contenido sólo se inyecta al expandirlo.
    """
    log.info("Ingresando al portal patrón...")
    wait = WebDriverWait(driver, 30)

    try:
        # 1. Esperar que el contenedor del portlet patronal esté en el DOM
        wait.until(EC.presence_of_element_located((By.ID, "listaPatronesAsociados")))

        # 2. Si el portlet usa carga diferida, expandirlo para disparar el AJAX
        contenido = driver.find_element(By.CSS_SELECTOR, "#listaPatronesAsociados .contenido")
        if contenido.get_attribute("already-loaded") != "true":
            log.info("Expandiendo portlet patronal para cargar su contenido...")
            btn_expandir = driver.find_element(
                By.CSS_SELECTOR, "#listaPatronesAsociados .widget-resize"
            )
            driver.execute_script("arguments[0].click();", btn_expandir)

            # Esperar a que el AJAX inyecte el contenido
            wait.until(lambda d: bool(
                d.find_elements(By.CSS_SELECTOR,
                                "#listaPatronesAsociados .contenido[already-loaded='true']")
            ))
            time.sleep(2)

        # 3. Hacer clic en el enlace del registro patronal
        log.info(f"Seleccionando registro patronal {REGISTRO_PATRONAL}...")
        enlace = wait.until(EC.element_to_be_clickable(
            (By.CSS_SELECTOR, f"a.patronAsociado[numeroregistropatronal='{REGISTRO_PATRONAL}']")
        ))
        url_antes = driver.current_url
        driver.execute_script("arguments[0].click();", enlace)

        # 4. Esperar a que el portal patrón cargue (la URL cambia tras el POST)
        WebDriverWait(driver, 25).until(lambda d: d.current_url != url_antes)
        time.sleep(5)
        guardar_html(driver, "debug_portal_patron.html")
        log.info(f"Portal patrón cargado: {driver.current_url}")
        return True

    except TimeoutException:
        log.error("No se pudo ingresar al portal patrón. Revisa debug_error_portal_patron.html")
        guardar_html(driver, "debug_error_portal_patron.html")
        return False


def explorar_portal(driver):
    """
    Explora todos los portlets del Escritorio Virtual y genera un reporte
    con los enlaces y contenido de cada uno, para identificar dónde están
    las incapacidades.
    """
    log.info("=" * 60)
    log.info("  MODO EXPLORACIÓN: Escritorio Virtual IMSS")
    log.info("=" * 60)

    _esperar_portlets(driver)
    guardar_html(driver, "debug_portal_explorado.html")

    reporte = [
        "EXPLORACIÓN DEL ESCRITORIO VIRTUAL IMSS",
        f"Fecha: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        "=" * 60,
        f"Keywords buscadas: {', '.join(KEYWORDS_INCAP)}",
        "",
    ]

    # Recopilar portlets Y widgets desde la página actual
    # El portal usa tanto portlet-url como widget-url para cargar contenido dinámico
    urls_raw = []
    for attr in ("portlet-url", "widget-url"):
        urls_raw += [
            el.get_attribute(attr)
            for el in driver.find_elements(By.CSS_SELECTOR, f"[{attr}]")
            if el.get_attribute(attr)
        ]
    portlets_urls = list(dict.fromkeys(urls_raw))
    log.info(f"Portlets encontrados: {len(portlets_urls)}")

    for portlet_url in portlets_urls:
        url_completa = f"{PORTAL_BASE}{portlet_url}"
        log.info(f"Explorando portlet: {portlet_url}")

        reporte += ["", "=" * 60, f"PORTLET: {portlet_url}"]

        try:
            driver.get(url_completa)
            time.sleep(3)

            nombre_html = "debug_portlet_" + portlet_url.strip("/").replace("/", "_") + ".html"
            guardar_html(driver, nombre_html)

            try:
                body_text = driver.find_element(By.TAG_NAME, "body").text
            except Exception:
                body_text = ""

            encontradas = [kw for kw in KEYWORDS_INCAP if kw.lower() in body_text.lower()]
            resumen = " ".join(body_text.split()[:80])

            reporte += [
                f"  HTML: debug/{nombre_html}",
                f"  Keywords encontradas: {encontradas if encontradas else 'ninguna'}",
                f"  Texto (resumen): {resumen[:400]}",
            ]

            # Enumerar enlaces disponibles en este portlet
            for enlace in driver.find_elements(By.TAG_NAME, "a"):
                try:
                    texto = enlace.text.strip()
                    href = enlace.get_attribute("href") or ""
                    onclick = enlace.get_attribute("onclick") or ""
                    if texto and len(texto) > 2:
                        destino = href or onclick or "(sin destino)"
                        reporte.append(f"  ENLACE: [{texto}] → {destino}")
                except StaleElementReferenceException:
                    continue

            if encontradas:
                log.info(f"  *** CANDIDATO: keywords={encontradas}")
            else:
                log.info(f"  Sin keywords de incapacidades.")

        except Exception as e:
            log.warning(f"  Error al explorar portlet: {e}")
            reporte.append(f"  ERROR: {e}")

        time.sleep(1)

    # Volver al portal principal y revisar los enlaces del menú
    log.info("Revisando menú principal del portal...")
    driver.get(f"{PORTAL_BASE}/portal-web/portal")
    _esperar_portlets(driver)

    reporte += ["", "=" * 60, "ENLACES EN MENÚ PRINCIPAL:"]
    for enlace in driver.find_elements(By.TAG_NAME, "a"):
        try:
            texto = enlace.text.strip()
            href = enlace.get_attribute("href") or ""
            if texto and len(texto) > 2:
                reporte.append(f"  [{texto}] → {href}")
        except StaleElementReferenceException:
            continue

    reporte += [
        "",
        "=" * 60,
        "PRÓXIMOS PASOS:",
        "1. Revisa los HTMLs en debug/ para ver el contenido de cada portlet",
        "2. Identifica qué portlet/sección contiene las incapacidades",
        "3. Copia la URL completa en RUTA_INCAPACIDADES al inicio del script",
        "4. Cambia MODO_EXPLORACION = False",
        "5. Ejecuta el script de nuevo",
        "=" * 60,
    ]

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    ruta = os.path.join(OUTPUT_DIR, f"exploracion_ev_{timestamp}.txt")
    with open(ruta, "w", encoding="utf-8") as f:
        f.write("\n".join(reporte))

    log.info(f"Reporte guardado: {ruta}")
    log.info(f"HTMLs de portlets guardados en: {DEBUG_DIR}")
    return ruta


# ===========================================================================
# FASE 3 — NAVEGACIÓN Y EXTRACCIÓN
# ===========================================================================

def navegar_a_incapacidades(driver):
    """
    Navega directamente a RUTA_INCAPACIDADES (definida arriba).
    Debe configurarse después de ejecutar en MODO_EXPLORACION.
    """
    if not RUTA_INCAPACIDADES:
        log.error("RUTA_INCAPACIDADES está vacía. Primero ejecuta en MODO_EXPLORACION=True.")
        return False

    log.info(f"Navegando a: {RUTA_INCAPACIDADES}")
    driver.get(RUTA_INCAPACIDADES)
    time.sleep(5)
    guardar_html(driver, "debug_incapacidades_pagina.html")
    return True


def aplicar_filtros(driver, dias_atras=365):
    """Detecta y llena filtros de fecha si los hay en la página actual."""
    hoy = date.today()
    fecha_ini = (hoy - timedelta(days=dias_atras)).strftime("%d/%m/%Y")
    fecha_fin = hoy.strftime("%d/%m/%Y")

    selectores_ini = [
        (By.ID, "fechaInicio"), (By.ID, "fechainicio"), (By.ID, "fecIni"),
        (By.NAME, "fechaInicio"), (By.NAME, "fecIni"),
        (By.XPATH, "//input[contains(@id,'echa') or contains(@name,'echa') or @type='date']"),
    ]
    selectores_fin = [
        (By.ID, "fechaFin"), (By.ID, "fechafin"), (By.ID, "fecFin"),
        (By.NAME, "fechaFin"), (By.NAME, "fecFin"),
    ]
    selectores_btn = [
        (By.XPATH, "//button[contains(text(),'Buscar') or contains(text(),'Consultar')]"),
        (By.XPATH, "//input[@type='button' and (contains(@value,'Buscar') or contains(@value,'Consultar'))]"),
        (By.XPATH, "//input[@type='submit']"),
        (By.ID, "btnBuscar"), (By.ID, "btnConsultar"),
    ]

    campo_ini = None
    for by, sel in selectores_ini:
        try:
            campo_ini = driver.find_element(by, sel)
            campo_ini.clear()
            campo_ini.send_keys(fecha_ini)
            log.info(f"Fecha inicio: {fecha_ini}")
            break
        except NoSuchElementException:
            continue

    if not campo_ini:
        log.info("No se detectaron filtros de fecha.")
        return

    for by, sel in selectores_fin:
        try:
            campo_fin = driver.find_element(by, sel)
            campo_fin.clear()
            campo_fin.send_keys(fecha_fin)
            log.info(f"Fecha fin: {fecha_fin}")
            break
        except NoSuchElementException:
            continue

    for by, sel in selectores_btn:
        try:
            btn = driver.find_element(by, sel)
            driver.execute_script("arguments[0].scrollIntoView({block:'center'});", btn)
            driver.execute_script("arguments[0].click();", btn)
            log.info("Botón de búsqueda presionado.")
            time.sleep(3)
            break
        except NoSuchElementException:
            continue


def extraer_tabla(driver):
    """Extrae datos de todas las tablas visibles en la página actual."""
    registros = []
    tablas = driver.find_elements(By.TAG_NAME, "table")
    log.info(f"Tablas encontradas: {len(tablas)}")

    if not tablas:
        guardar_html(driver, "debug_sin_tablas_ev.html")
        return registros

    for idx, tabla in enumerate(tablas, 1):
        try:
            filas = tabla.find_elements(By.TAG_NAME, "tr")
        except StaleElementReferenceException:
            continue

        if len(filas) < 2:
            continue

        celdas_enc = filas[0].find_elements(By.TAG_NAME, "th") or \
                     filas[0].find_elements(By.TAG_NAME, "td")
        encabezados = []
        for i, c in enumerate(celdas_enc):
            texto = c.text.strip().replace("\n", " ")
            encabezados.append(texto if texto else f"T{idx}Col{i+1}")

        if not encabezados:
            continue

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

        log.info(f"  Tabla {idx}: {len(registros)} registros acumulados.")

    return registros


def guardar_csv(registros, ruta):
    if not registros:
        log.warning("Sin registros para guardar.")
        return
    campos = [c for c in registros[0].keys() if c != "_fecha_extraccion"] + ["_fecha_extraccion"]
    with open(ruta, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=campos, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(registros)
    log.info(f"CSV guardado: {ruta} ({len(registros)} registros)")


# ===========================================================================
# MAIN
# ===========================================================================
def main():
    log.info("=" * 60)
    log.info("  IMSS Escritorio Virtual - Scraper de Incapacidades")
    log.info(f"  Modo: {'EXPLORACIÓN' if MODO_EXPLORACION else 'EXTRACCIÓN'}")
    log.info("=" * 60)

    try:
        config = cargar_config()
    except Exception as e:
        log.error(f"Error cargando la configuración: {e}")
        return

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    driver = None
    try:
        driver = crear_driver()

        if not iniciar_sesion_escritorio_virtual(driver, config):
            log.error("Login fallido. Revisa la carpeta 'debug' para ver en dónde se atascó.")
            return

        # Ingresar al portal patrón (donde están los trámites de trabajadores)
        if not ingresar_portal_patron(driver):
            log.warning("No se pudo ingresar al portal patrón. Continuando en portal persona.")

        # ── MODO EXPLORACIÓN ────────────────────────────────────────────────
        if MODO_EXPLORACION:
            ruta = explorar_portal(driver)
            log.info("")
            log.info("Exploración completada.")
            log.info(f"  Reporte  → {ruta}")
            log.info(f"  HTMLs    → {DEBUG_DIR}")
            log.info("")
            log.info("PRÓXIMOS PASOS:")
            log.info("  1. Abre el reporte y los HTMLs de debug para identificar")
            log.info("     qué portlet/sección tiene las incapacidades.")
            log.info("  2. Copia esa URL en RUTA_INCAPACIDADES (arriba en este script).")
            log.info("  3. Cambia MODO_EXPLORACION = False")
            log.info("  4. Ejecuta de nuevo.")
            return
        # ────────────────────────────────────────────────────────────────────

        if not navegar_a_incapacidades(driver):
            log.error("No se pudo navegar a incapacidades. Revisa RUTA_INCAPACIDADES.")
            return

        aplicar_filtros(driver)

        registros = extraer_tabla(driver)
        if not registros:
            log.warning(
                "Sin datos. Revisa debug/debug_incapacidades_pagina.html — "
                "puede que se necesiten filtros específicos o navegar a una subsección."
            )
            return

        ruta_csv = os.path.join(OUTPUT_DIR, f"incapacidades_ev_{timestamp}.csv")
        guardar_csv(registros, ruta_csv)
        log.info(f"Proceso completado. CSV → {ruta_csv}")

    except Exception as e:
        log.exception(f"Error inesperado: {e}")
        if driver:
            guardar_html(driver, f"debug_error_{timestamp}.html")
    finally:
        if driver:
            driver.quit()
            log.info("Navegador cerrado.")

if __name__ == "__main__":
    main()