# Web Scraper para el Portal IDSE del IMSS (Versión PFX)

Este proyecto automatiza el inicio de sesión en el portal IDSE (IMSS Desde Su Empresa) utilizando un único archivo **PFX** y tu **usuario**. El script extrae los componentes necesarios del archivo PFX de forma temporal para realizar la autenticación de manera segura.

**ADVERTENCIA:** Este script es una herramienta para automatizar tareas y debe usarse de manera responsable.

---

### Requisitos Previos

1.  **Python 3.7 o superior.**
2.  **Google Chrome.**
3.  Tu archivo **PFX (.pfx)**, su **contraseña** y tu **nombre de usuario** del IMSS.

---

### Pasos para la Instalación y Configuración

#### 1. Descargar el Proyecto
Guarda los 4 archivos (`scraper.py`, `config.ini`, `requirements.txt`, `README.md`) en una misma carpeta.

#### 2. Instalar las Dependencias
Abre una terminal en la carpeta del proyecto y ejecuta:

```bash
pip install -r requirements.txt