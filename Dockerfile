# Scraper IMSS — imagen para ejecución headless en contenedor.
#
# Mantiene Microsoft Edge (el scraper está validado en producción contra
# Edge; cambiar a Chromium sería riesgo de regresión no validado).
#
# Estrategia de versiones: instala Edge stable y descarga el msedgedriver
# que matchea exactamente la versión instalada (build-time matching). Más
# robusto que pinear una versión fija — el repo apt de Microsoft solo
# conserva versiones recientes. Para reproducibilidad estricta, pinear un
# .deb específico de Edge (ver DEPLOY.md).

# Platform fijada a amd64: Microsoft Edge para Linux solo existe en amd64
# (no hay build arm64). El target de prod (AWS ECS/Fargate) es amd64 igual.
# En hosts Apple Silicon el build/run usa emulación QEMU (más lento, pero
# es el artefacto correcto para desplegar).
FROM --platform=linux/amd64 python:3.12-slim-bookworm

# Deps mínimas. Las libs de runtime del browser las resuelve apt al
# instalar microsoft-edge-stable (no se hand-mantienen aquí).
RUN apt-get update && apt-get install -y --no-install-recommends \
      curl \
      gnupg \
      ca-certificates \
      fonts-liberation \
      unzip \
    && rm -rf /var/lib/apt/lists/*

# Repo y llave de Microsoft Edge
RUN curl -fsSL https://packages.microsoft.com/keys/microsoft.asc \
      | gpg --dearmor -o /usr/share/keyrings/microsoft-edge.gpg \
    && echo "deb [arch=amd64 signed-by=/usr/share/keyrings/microsoft-edge.gpg] https://packages.microsoft.com/repos/edge stable main" \
      > /etc/apt/sources.list.d/microsoft-edge.list \
    && apt-get update \
    && apt-get install -y --no-install-recommends microsoft-edge-stable \
    && rm -rf /var/lib/apt/lists/*

# msedgedriver que matchea la versión exacta de Edge instalada.
# CDN: msedgedriver.microsoft.com (msedgedriver.azureedge.net fue deprecado
# por Microsoft — si vuelve a cambiar, actualizar este host).
RUN EDGE_VERSION="$(microsoft-edge --version | awk '{print $3}')" \
    && echo "Edge instalado: ${EDGE_VERSION}" \
    && curl -fsSL "https://msedgedriver.microsoft.com/${EDGE_VERSION}/edgedriver_linux64.zip" \
      -o /tmp/edgedriver.zip \
    && unzip -j /tmp/edgedriver.zip msedgedriver -d /usr/local/bin \
    && chmod +x /usr/local/bin/msedgedriver \
    && rm /tmp/edgedriver.zip \
    && /usr/local/bin/msedgedriver --version

WORKDIR /app

# Instalar deps Python primero (capa cacheable)
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Código del scraper
COPY . .

# Modo contenedor: headless ON + ruta del driver del sistema.
# crear_driver() lee estas env vars; sin ellas el comportamiento es el
# local de siempre (ventana visible, driver en SCRIPT_DIR).
ENV SCRAPER_HEADLESS=true \
    SCRAPER_MSEDGEDRIVER_PATH=/usr/local/bin/msedgedriver

# Usuario no-root
RUN useradd --create-home --uid 10001 scraper \
    && chown -R scraper:scraper /app
USER scraper

# El orquestador elige qué script correr sobrescribiendo el CMD:
#   docker run <img> incapacidades.py
ENTRYPOINT ["python"]
CMD ["idse_incapacidades.py"]
