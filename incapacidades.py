# -*- coding: utf-8 -*-
import logging
import os
import time
from datetime import datetime
import configparser

from selenium import webdriver
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
# MAIN
# ===========================================================================
def main():
    log.info("=" * 60)
    log.info("  IMSS Escritorio Virtual - Scraper de Incapacidades")
    log.info("=" * 60)

    try:
        config = cargar_config()
    except Exception as e:
        log.error(f"Error cargando la configuración: {e}")
        return

    driver = None
    try:
        driver = crear_driver()
        
        if not iniciar_sesion_escritorio_virtual(driver, config):
            log.error("Login fallido. Revisa la carpeta 'debug' para ver en dónde se atascó.")
            return
            
        log.info("✅ El bot está dentro del portal. Dejando el navegador abierto 15 segundos para comprobar...")
        time.sleep(15)
        
        # AQUÍ AGREGAREMOS EL CÓDIGO PARA NAVEGAR A LAS INCAPACIDADES EN EL SIGUIENTE PASO
        
    except Exception as e:
        log.exception(f"Error inesperado: {e}")
    finally:
        if driver:
            driver.quit()
            log.info("Navegador cerrado.")

if __name__ == "__main__":
    main()