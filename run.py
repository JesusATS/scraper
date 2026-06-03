# -*- coding: utf-8 -*-
"""
Entry point unificado del scraper para invocación desde orquestador.

Uso:
    python run.py < input.json
    docker run -i idse-scraper:latest < input.json

Lee un JSON de stdin (ver scraper_input.py para el shape), valida, y dispatcha
al script del portal correcto pasándole las credenciales y los parámetros de
búsqueda.

Exit codes (estables para el orquestador):
    0 — éxito
    1 — falla durante scraping (login, navegación, extracción)
    2 — error de input (JSON inválido o validación falla)
    3 — error de configuración (driver no encontrado, etc.)
"""
from __future__ import annotations

import json
import logging
import sys

from credentials import ImssCredentials
from scraper_input import PORTAL_EV, PORTAL_IDSE, parse_input

# Logging básico a stderr — el stdout queda libre por si en futuro el
# orquestador quiere consumir resultados directamente por pipe.
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    stream=sys.stderr,
)
log = logging.getLogger("scraper.run")


def main() -> int:
    # 1. Leer JSON de stdin
    try:
        payload = json.load(sys.stdin)
    except json.JSONDecodeError as e:
        log.error("Input no es JSON válido: %s", e)
        return 2
    except Exception as e:
        log.error("No se pudo leer stdin: %s", e)
        return 2

    # 2. Validar contrato
    try:
        validated = parse_input(payload)
    except ValueError as e:
        log.error("Input inválido: %s", e)
        return 2

    log.info(
        "Input validado: portal=%s, search_mode=%s",
        validated.portal,
        validated.search.mode,
    )

    # 3. Construir credenciales para el scraper
    creds = ImssCredentials.from_input(validated.credentials)

    # 4. Dispatch al script del portal
    if validated.portal == PORTAL_IDSE:
        import idse_incapacidades

        return idse_incapacidades.main(creds=creds, search_params=validated.search) or 0

    if validated.portal == PORTAL_EV:
        import incapacidades

        return incapacidades.main(creds=creds, search_params=validated.search) or 0

    # Defensivo: parse_input ya valida portal, pero por si cambia el enum.
    log.error("Portal desconocido tras validación: %s", validated.portal)
    return 2


if __name__ == "__main__":
    sys.exit(main())
