# -*- coding: utf-8 -*-
import time
import configparser
import os
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.edge.options import Options as EdgeOptions
from selenium.webdriver.edge.service import Service as EdgeService
from webdriver_manager.microsoft import EdgeChromiumDriverManager
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import NoSuchElementException, TimeoutException, NoSuchWindowException

def manejar_popups(driver):
    """
    Revisa si hay ventanas emergentes (pop-ups) y las cierra.
    """
    try:
        # Espera un máximo de 3 segundos por si aparece un pop-up
        WebDriverWait(driver, 3).until(EC.number_of_windows_to_be(2))
        ventana_principal = driver.window_handles[0]
        popup = driver.window_handles[1]
        driver.switch_to.window(popup)
        driver.close()
        driver.switch_to.window(ventana_principal)
        print("Ventana emergente de avisos cerrada.")
    except TimeoutException:
        # No se encontraron pop-ups.
        pass

def iniciar_sesion_idse():
    """
    Función principal para automatizar el inicio de sesión en el portal IDSE del IMSS.
    """
    driver = None

    try:
        # --- Cargar configuración desde el archivo config.ini ---
        print("Cargando credenciales desde config.ini...")
        config = configparser.ConfigParser()
        # Construir la ruta absoluta al archivo config.ini
        script_dir = os.path.dirname(os.path.abspath(__file__))
        config_path = os.path.join(script_dir, 'config.ini')

        # Leer el archivo de configuración
        if not config.read(config_path, encoding='utf-8'):
            print(f"Error: No se pudo encontrar o leer el archivo 'config.ini' en la ruta: {config_path}")
            return
            
        # Validar credenciales
        if 'IMSS_CREDENCIALES' not in config:
            print("Error: La sección [IMSS_CREDENCIALES] no se encontró en el archivo config.ini.")
            return

        ruta_cer = config['IMSS_CREDENCIALES']['RUTA_CER']
        ruta_key = config['IMSS_CREDENCIALES']['RUTA_KEY']
        usuario = config['IMSS_CREDENCIALES']['USUARIO']
        contrasena_sitio = config['IMSS_CREDENCIALES']['CONTRASENA_SITIO']

        if not all([ruta_cer, ruta_key, usuario, contrasena_sitio]):
            print("Error: Debes especificar RUTA_CER, RUTA_KEY, USUARIO y CONTRASENA_SITIO en 'config.ini'.")
            return

        # --- Configurar e iniciar el navegador ---
        print("Configurando carpeta de descargas...")
        # Crear carpeta para descargas si no existe
        downloads_path = os.path.join(os.path.dirname(__file__), 'descargas_csv')
        if not os.path.exists(downloads_path):
            os.makedirs(downloads_path)

        edge_options = EdgeOptions()
        prefs = {
            "download.default_directory": downloads_path,
            "download.prompt_for_download": False,
            "download.directory_upgrade": True,
            "safebrowsing.enabled": True,
            "profile.default_content_setting_values.automatic_downloads": 1
        }
        edge_options.add_experimental_option("prefs", prefs)

        print("Iniciando el navegador Microsoft Edge...")
        # Usar un driver descargado manualmente
        # Asegúrate de que el archivo 'msedgedriver' esté en la misma carpeta que este script.
        ruta_driver_manual = os.path.join(os.path.dirname(__file__), 'msedgedriver')
        service = EdgeService(executable_path=ruta_driver_manual)
        driver = webdriver.Edge(service=service, options=edge_options)

        driver.maximize_window()

        
        # --- Navegar a la página de IDSE ---
        driver.get("https://idse.imss.gob.mx/imss/")

        # --- Rellenar el login ---
        print("Llenando los campos del formulario...")
        wait = WebDriverWait(driver, 20)
        
        # Certificado
        campo_certificado = wait.until(EC.visibility_of_element_located((By.ID, 'certificado')))
        campo_certificado.send_keys(ruta_cer)
        # verificar el onchange
        driver.execute_script("arguments[0].dispatchEvent(new Event('change'));", campo_certificado)
        print("Campo 'certificado' llenado.")

        # LLenar llave
        llave_input = wait.until(EC.visibility_of_element_located((By.ID, 'llave')))
        llave_input.send_keys(ruta_key)
        print("Campo 'llave' llenado.")

        # Usuario
        print("Esperando a que el campo 'usuario' sea clickeable...")
        usuario_input = wait.until(EC.element_to_be_clickable((By.ID, 'idUsuario')))
        usuario_input.send_keys(usuario)
        print("Campo 'usuario' llenado.")

        # Contraseña
        print("Esperando a que el campo 'contraseña' sea clickeable...")
        clave_input = wait.until(EC.element_to_be_clickable((By.ID, 'password')))
        clave_input.send_keys(contrasena_sitio)
        print("Campo 'contraseña' llenado.")

        # --- Enviar el formulario ---
        print("Esperando a que el botón 'Iniciar sesión' sea clickeable...")
        btn_ingresar = wait.until(EC.element_to_be_clickable((By.ID, 'botonFirma')))
        btn_ingresar.click()

        # --- Verificar el resultado del inicio de sesión ---
        print("Verificando el resultado del inicio de sesión...")
        time.sleep(5) # Sleep de 5 segundos para que la página reaccione

        try:
            
            driver.find_element(By.ID, 'password')
            # el login falló porque seguimos en la misma página.
            print("Error: El inicio de sesión falló. El script sigue en la página de login.")
            print("Por favor, verifica tus credenciales en config.ini y asegúrate de que no haya un CAPTCHA o un error visible en el navegador.")
            # Imprimir el contenido del div de errores
            error_div = driver.find_element(By.ID, 'imsgErrors')
            if error_div.text:
                print(f"Mensaje de error encontrado en la página: {error_div.text}")
            
        except NoSuchElementException:
            print("Login aparentemente exitoso. Esperando a que cargue la página principal...")
            
            # Manejar pop-ups si existen
            manejar_popups(driver)

            try:
                movimientos_link = wait.until(EC.visibility_of_element_located((By.XPATH, "//a[contains(text(), 'Movimientos Afiliatorios')]")))
                print("¡Inicio de sesión exitoso! Bienvenido al portal IDSE.")

                # --- FASE 2: NAVEGAR Y DESCARGAR CSV ---
                print("\n--- Iniciando Fase 2: Descarga de archivos CSV ---")
                
                # Navegar directamente a la URL de resultados
                url_resultados = "https://idse.imss.gob.mx/imss/AfiliaResultados.idse"
                print(f"Navegando a la página de resultados: {url_resultados}")
                driver.get(url_resultados)

                # Esperar a que la página de resultados cargue buscando los enlaces
                print("Esperando a que la tabla de resultados cargue...")
                wait.until(EC.presence_of_element_located((By.XPATH, "//h2[contains(text(), 'Lotes procesados')]")))
                print("Página de resultados cargada. Buscando archivos CSV para descargar...")

                # --- Lógica de descarga por índice ---
                index = 0
                while True:
                    try:
                        # Espera a que la tabla de resultados esté cargada
                        wait.until(EC.presence_of_element_located((By.XPATH, "//h2[contains(text(), 'Lotes procesados')]")))
                        
                        # Busca TODOS los enlaces csv en la página
                        all_csv_links = driver.find_elements(By.XPATH, "//a[text()='CSV']")
                        
                        # Si el índice terminó, cierra el ciclo
                        if index >= len(all_csv_links):
                            print("Todos los archivos CSV han sido procesados.")
                            break

                        print(f"Procesando archivo en posición {index + 1} de {len(all_csv_links)}...")
                        
                        # Obtener el enlace por su índice
                        link_to_click = all_csv_links[index]

                        driver.execute_script("arguments[0].scrollIntoView(true);", link_to_click)
                        time.sleep(1) # pausa para no sobrecargar el navegador

                        # Hacemos clic para iniciar la descarga
                        print(f"Haciendo clic en el enlace: {link_to_click.text}")
                        driver.execute_script("arguments[0].click();", link_to_click)

                        # --- Espera de Recarga de Página ---
                        print("Descarga iniciada. Esperando a que la página se recargue...")
                        
                        # contador del index
                        index += 1

                        # Pausa para que la página no se sobrecargue
                        print("Pausa de 5 segundos...")
                        time.sleep(5)

                    except (NoSuchElementException, NoSuchWindowException, TimeoutException) as e:
                        print(f"Ocurrió un error: {type(e).__name__}")
                        break

                # --- Lógica para esperar que todas las descargas finalicen ---
                print(f"\nDescargas iniciadas. Verificando la carpeta: {downloads_path}")
                print("Esperando a que los archivos se completen (máximo 2 minutos)...")
                
                tiempo_espera_total = 120
                tiempo_espera_actual = 0
                while tiempo_espera_actual < tiempo_espera_total:
                    archivos_en_progreso = [f for f in os.listdir(downloads_path) if f.endswith('.crdownload')]
                    if not archivos_en_progreso:
                        print("¡Todas las descargas se han completado!")
                        break
                    time.sleep(2)
                    tiempo_espera_actual += 2
                
                if tiempo_espera_actual >= tiempo_espera_total:
                    print("Advertencia: Se agotó el tiempo de espera. Es posible que algunas descargas no se hayan completado.")


            except TimeoutException:
                print("Se ha logueado correctamente, pero no se encontró el enlace 'Movimientos Afiliatorios'.")
                print("La página de bienvenida puede haber cambiado. Aquí está el código fuente para que puedas ajustarlo:")
                print("--- INICIO DEL CÓDIGO FUENTE DE LA PÁGINA POST-LOGIN ---")
                print(driver.page_source)
                print("--- FIN DEL CÓDIGO FUENTE DE LA PÁGINA POST-LOGIN ---")

    except Exception as e:
        print(f"Ha ocurrido un error: {repr(e)}")

    finally:
        # --- Limpiar y cerrar navegador ---
        if driver:
            driver.quit()
        print("Recursos limpiados y navegador cerrado.")

if __name__ == '__main__':
    iniciar_sesion_idse()