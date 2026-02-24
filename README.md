# IDSE IMSS — Scraper de Incapacidades

Automatiza la consulta y descarga de incapacidades de empleados desde el portal IDSE del IMSS.

---

## Requisitos

- Python 3.10 o superior
- Microsoft Edge instalado
- `msedgedriver` compatible con tu versión de Edge

### Instalar dependencias

```bash
pip install selenium openpyxl
```

> **Nota:** `webdriver-manager` es opcional. Este proyecto usa el driver manual colocado en la carpeta del script.

---

## Configuración

1. Edita el archivo `config.ini` con tus datos:

```ini
[IMSS_CREDENCIALES]
RUTA_CER        = C:\Ruta\A\Tu\Certificado.cer
RUTA_KEY        = C:\Ruta\A\Tu\Llave.key
USUARIO         = XAXX010101000
CONTRASENA_SITIO = tu_contrasena_aqui
```

2. Descarga el `msedgedriver` que corresponda a tu versión de Edge:
   - Revisa tu versión de Edge en `edge://settings/help`
   - Descarga el driver en: https://developer.microsoft.com/en-us/microsoft-edge/tools/webdriver/
   - Coloca el archivo `msedgedriver` (o `msedgedriver.exe` en Windows) en la misma carpeta que el script

---

## Uso

```bash
python idse_incapacidades.py
```

---

## Archivos generados

| Carpeta / Archivo                        | Descripción                              |
|------------------------------------------|------------------------------------------|
| `resultados/incapacidades_YYYYMMDD.csv`  | Datos en formato CSV (compatible con Excel) |
| `resultados/incapacidades_YYYYMMDD.xlsx` | Datos en formato Excel con formato visual  |
| `logs/idse_YYYYMMDD_HHMMSS.log`          | Log detallado de la ejecución             |
| `debug_post_login.html`                  | Página fuente post-login (si hay errores) |
| `debug_tabla_pag*.html`                  | Páginas de tabla (si no se encontró data) |

---

## Solución de problemas

### El login falla
- Verifica que las rutas al `.cer` y `.key` sean absolutas y correctas
- Asegúrate de que la contraseña en `config.ini` no tenga espacios al inicio/final
- Revisa si el portal muestra un CAPTCHA (el script no puede resolverlos)

### No se encuentran incapacidades
- Abre el archivo `debug_post_login.html` en tu navegador
- Inspecciona el menú o los enlaces de navegación
- Ajusta los XPaths en la función `navegar_a_incapacidades()` según la estructura real

### El driver de Edge falla
- Confirma que la versión del `msedgedriver` coincide exactamente con tu Edge instalado
- En Windows, asegúrate de que el archivo se llame `msedgedriver.exe`

---

## Estructura del proyecto

```
idse_scraper/
├── idse_incapacidades.py   # Script principal
├── config.ini              # Credenciales (NO subir a git)
├── msedgedriver[.exe]      # Driver de Edge (descargar manualmente)
├── resultados/             # Archivos de salida generados automáticamente
└── logs/                   # Logs de ejecución
```

---

## Aviso legal

Este script es una herramienta de automatización para uso interno empresarial.
Úsalo únicamente con credenciales que te pertenezcan y respetando los términos de uso del IMSS.