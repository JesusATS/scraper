# IDSE IMSS — Scraper de Incapacidades

Automatiza la consulta y descarga de incapacidades de empleados desde el portal IDSE del IMSS.

---

## Requisitos

- Python 3.10 o superior
- Microsoft Edge instalado
- `msedgedriver` compatible con tu versión de Edge

### Instalar dependencias

```bash
pip install -r requirements.txt
```

---

## Configuración

> ⚠️ **Nunca committees archivos de credenciales** (`.env`, `config.ini`, `.cer`, `.key`). El `.gitignore` los bloquea por defecto.

### Opción 1 — Variables de entorno (recomendado)

Copia la plantilla y rellena con tus datos:

```bash
cp .env.example .env
```

Variables disponibles:

| Variable          | Descripción                                                          |
|-------------------|----------------------------------------------------------------------|
| `IMSS_RUTA_CER`   | Ruta absoluta al certificado FIEL `.cer`                            |
| `IMSS_RUTA_KEY`   | Ruta absoluta a la llave privada FIEL `.key`                        |
| `IMSS_USUARIO`    | RFC del firmante (login del portal)                                 |
| `IMSS_CONTRASENA` | Contraseña del portal                                                |
| `IMSS_RFC`        | Opcional. RFC adicional para Escritorio Virtual cuando difiere de `IMSS_USUARIO`. |

Las credenciales también pueden venir directamente del shell (sin `.env`); útil cuando un orquestador externo (p. ej. idse-ai) invoca el scraper.

### Opción 2 — config.ini (legacy, deprecado)

Aún soportado para transición. Genera deprecation warning en logs al ejecutar.

```bash
cp config.example.ini config.ini
```

### Driver de Edge

Descarga el `msedgedriver` que corresponda a tu versión de Edge:
- Revisa tu versión en `edge://settings/help`
- Descarga: https://developer.microsoft.com/en-us/microsoft-edge/tools/webdriver/
- Coloca el binario en la raíz del proyecto. El `.gitignore` lo bloquea — no se sube al repo.

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
- Asegúrate de que la contraseña no tenga espacios al inicio/final (en `.env` o `config.ini`)
- Si usas `.env`, confirma que el archivo está en la raíz del proyecto y se cargó (revisa el log)
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
├── idse_incapacidades.py   # Scraper IDSE
├── incapacidades.py        # Scraper Escritorio Virtual
├── credentials.py          # Helper de carga de credenciales (env > .env > config.ini)
├── .env                    # Credenciales locales (gitignored, NO subir a git)
├── .env.example            # Plantilla
├── config.example.ini      # Plantilla legacy
├── config.ini              # Legacy — gitignored, NO subir a git
├── msedgedriver[.exe]      # Driver de Edge (descargar manualmente, gitignored)
├── resultados/             # Salidas generadas (gitignored)
└── logs/                   # Logs de ejecución (gitignored)
```

---

## Aviso legal

Este script es una herramienta de automatización para uso interno empresarial.
Úsalo únicamente con credenciales que te pertenezcan y respetando los términos de uso del IMSS.