# Despliegue del scraper IMSS — runbook

> Para quien despliega el scraper dentro de la infraestructura idse-ai
> (mx-central-1). Este documento describe el **artefacto contenedor**; la
> infra que lo ejecuta (ECS/Fargate, scheduling, IAM) y el orquestador que
> lo invoca son trabajo de la plataforma, no de este repo.

## Qué es

Imagen Docker con Python 3.12 + Microsoft Edge headless + msedgedriver,
empaquetando los dos scrapers:

- `idse_incapacidades.py` — portal IDSE
- `incapacidades.py` — portal Escritorio Virtual (SAT e.firma)

## Build

```bash
docker build -t idse-scraper:latest .
```

El build instala Edge stable y descarga el msedgedriver que matchea esa
versión exacta (build-time matching). Rebuilds periódicos mantienen
Edge+driver sincronizados.

> **Arquitectura: amd64 obligatorio.** Microsoft Edge para Linux solo
> existe en amd64 (no hay arm64). El `Dockerfile` fija
> `--platform=linux/amd64`, así que `docker build` produce siempre la
> imagen correcta. En hosts Apple Silicon el build corre bajo emulación
> QEMU (más lento; instalar Docker Desktop con Rosetta acelera). El target
> de prod (AWS ECS/Fargate) es amd64, así que esto es lo correcto, no un
> workaround.
>
> Docker emite el warning `FromPlatformFlagConstDisallowed` por el
> `--platform` constante en `FROM` — es **intencional** (Edge amd64-only),
> no lo quiten. El driver se baja de `msedgedriver.microsoft.com`
> (`msedgedriver.azureedge.net` fue deprecado por Microsoft).

> **Reproducibilidad estricta:** si se requiere pinear una versión exacta
> de Edge (no "latest stable"), reemplazar `microsoft-edge-stable` por un
> `.deb` versionado en el Dockerfile. Trade-off: el repo apt de Microsoft
> no conserva versiones viejas indefinidamente.

## Contrato de invocación (modelo Push/Invoke)

El orquestador descifra/baja las credenciales (de S3), las materializa como
archivos + strings, y las inyecta como variables de entorno. El scraper las
consume vía `credentials.py` (`env > .env > config.ini`).

### Variables de entorno requeridas

| Variable | Descripción |
|----------|-------------|
| `IMSS_RUTA_CER` | Ruta absoluta al `.cer` (dentro del contenedor) |
| `IMSS_RUTA_KEY` | Ruta absoluta al `.key` (dentro del contenedor) |
| `IMSS_USUARIO` | RFC del firmante |
| `IMSS_CONTRASENA` | Contraseña del portal |
| `IMSS_RFC` | Opcional. RFC adicional para Escritorio Virtual si difiere de `IMSS_USUARIO` |

### Variables de entorno de contenedor (ya seteadas en la imagen)

| Variable | Valor en imagen | Propósito |
|----------|-----------------|-----------|
| `SCRAPER_HEADLESS` | `true` | Activa modo headless |
| `SCRAPER_MSEDGEDRIVER_PATH` | `/usr/local/bin/msedgedriver` | Driver del sistema |

Sin estas dos env, el código corre en modo local (ventana visible, driver
en `SCRIPT_DIR`) — comportamiento idéntico al previo a la contenerización.

### Invocación

```bash
# IDSE
docker run --rm \
  -e IMSS_RUTA_CER=/secrets/certificado.cer \
  -e IMSS_RUTA_KEY=/secrets/llave.key \
  -e IMSS_USUARIO=XAXX010101000 \
  -e IMSS_CONTRASENA=*** \
  -v /ruta/host/secrets:/secrets:ro \
  -v /ruta/host/salida:/app/resultados \
  idse-scraper:latest idse_incapacidades.py

# Escritorio Virtual: cambiar el último arg a incapacidades.py
```

El orquestador:
1. Monta los `.cer`/`.key` descifrados (read-only) en el contenedor
2. Setea las env `IMSS_*`
3. Elige el script sobrescribiendo el CMD (`idse_incapacidades.py` |
   `incapacidades.py`)
4. Recoge los resultados de `/app/resultados/`
5. Destruye el contenedor y limpia los secretos montados

## Salida

CSV en `/app/resultados/`. El orquestador debe montar un volumen ahí y
recoger los archivos tras la ejecución.

## ⚠️ Validado vs NO validado

| Aspecto | Estado |
|---------|--------|
| Imagen buildea (amd64) | ✅ Validado |
| Edge + msedgedriver versión matcheada (148.0.3967.70) | ✅ Validado en imagen |
| `crear_driver()` no rompe flujo local (env ausente = comportamiento previo) | ✅ Por diseño (opt-in) |
| Sintaxis Python de ambos scripts (en imagen) | ✅ `py_compile` verde |
| Selenium arranca Edge headless + navega + lee DOM (sin IMSS) | ✅ Validado en contenedor |
| Corre como usuario no-root | ✅ Validado |
| **Headless contra el portal real del IMSS** | ❌ **NO validado** (requiere cert real + perímetro) |
| Login E2E headless con cert real | ❌ **NO validado** (requiere cert real + perímetro) |

> **Crítico antes de prod:** los portales del IMSS pueden detectar o
> comportarse distinto en headless. Validar el login E2E headless con un
> certificado real **dentro del perímetro mx-central-1** (§14 — no fuera).
> Si headless falla, evaluar `xvfb` (display virtual) como alternativa sin
> cambiar a modo ventana.

## Limitaciones conocidas (para el orquestador)

- **Exit code no confiable como señal de éxito.** Hoy `main()` hace `return`
  en fallas y el proceso sale 0 igual. El orquestador NO puede depender del
  exit code para detectar si el scraping funcionó — debe verificar presencia
  de output en `/app/resultados/` y/o parsear logs. *Recomendado follow-up:
  instrumentar `sys.exit(1)` en rutas de falla de `main()`.*
- **Sin reintentos ni timeout global.** El orquestador debe imponer su
  propio timeout al contenedor.
- Los scripts deprecados (`scraper.py`, `scraper_server.py`, `scraper/`,
  `scraperie/`) están excluidos del build vía `.dockerignore`.

## Compliance (verificar contra CLAUDE.md)

- §14.1 — el contenedor y los `.cer`/`.key` descifrados corren/viven SOLO
  en mx-central-1. Correrlo fuera con certs reales viola residencia.
- §14.7 — escribir llaves descifradas a disco (montadas en el contenedor)
  requiere evaluación documentada + aprobación de jaaronq.
- §16 — el scraper NO accede a S3/DB directo. El orquestador resuelve y
  monta. El scraper solo lee env + archivos montados.
- Audit — cada invocación debe registrar `credencial.used` (lo emite el
  orquestador, no el scraper).
