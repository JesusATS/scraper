# -*- coding: utf-8 -*-
"""
Carga centralizada de credenciales IMSS para los scrapers.

Orden de precedencia (de más alto a más bajo):
  1. Variables de entorno IMSS_* (caso integración con idse-ai u orquestador
     externo que las exporta antes de invocar el script).
  2. Archivo .env en SCRIPT_DIR (local dev, vía python-dotenv).
  3. config.ini en SCRIPT_DIR (legacy — emite deprecation warning).

Cuando idse-ai integre el scraper, exportará las variables de entorno antes
de invocar el script; los pasos 2-3 nunca se ejecutarán.
"""
from __future__ import annotations

import configparser
import logging
import os
from dataclasses import dataclass
from pathlib import Path

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class ImssCredentials:
    """Credenciales IMSS para scrapers IDSE / Escritorio Virtual."""

    ruta_cer: str
    ruta_key: str
    usuario: str
    contrasena: str
    rfc: str  # Default: == usuario. Algunos portales (EV) lo distinguen.

    @classmethod
    def from_input(cls, creds_input: object) -> "ImssCredentials":
        """
        Construye ImssCredentials desde un CredentialsInput de scraper_input.

        Se usa cuando el orquestador (idse-ai) provee las credenciales vía
        JSON en stdin. La validación de campos ya ocurrió en scraper_input.
        """
        return cls(
            ruta_cer=creds_input.ruta_cer,  # type: ignore[attr-defined]
            ruta_key=creds_input.ruta_key,  # type: ignore[attr-defined]
            usuario=creds_input.usuario,    # type: ignore[attr-defined]
            contrasena=creds_input.contrasena,  # type: ignore[attr-defined]
            rfc=creds_input.rfc,            # type: ignore[attr-defined]
        )


_REQUIRED_ENV_KEYS = (
    "IMSS_RUTA_CER",
    "IMSS_RUTA_KEY",
    "IMSS_USUARIO",
    "IMSS_CONTRASENA",
)


def _load_dotenv_if_available(script_dir: Path) -> None:
    """Carga .env desde SCRIPT_DIR si python-dotenv y el archivo existen."""
    try:
        from dotenv import load_dotenv
    except ImportError:
        return

    env_path = script_dir / ".env"
    if env_path.exists():
        # override=False — variables ya seteadas en el ambiente tienen prioridad.
        load_dotenv(env_path, override=False)
        log.debug("Cargado .env desde %s", env_path)


def _from_env() -> ImssCredentials | None:
    """Lee credenciales de variables de entorno. Devuelve None si falta alguna."""
    values = {k: os.environ.get(k, "").strip() for k in _REQUIRED_ENV_KEYS}
    if not all(values.values()):
        return None
    usuario = values["IMSS_USUARIO"]
    rfc = os.environ.get("IMSS_RFC", "").strip() or usuario
    return ImssCredentials(
        ruta_cer=values["IMSS_RUTA_CER"],
        ruta_key=values["IMSS_RUTA_KEY"],
        usuario=usuario,
        contrasena=values["IMSS_CONTRASENA"],
        rfc=rfc,
    )


def _from_config_ini(script_dir: Path) -> ImssCredentials | None:
    """Fallback legacy. Emite deprecation warning si encuentra config.ini."""
    config_path = script_dir / "config.ini"
    if not config_path.exists():
        return None

    log.warning(
        "Cargando credenciales desde config.ini — DEPRECATED. "
        "Migra a variables de entorno (.env). Ver README."
    )

    config = configparser.ConfigParser()
    config.read(config_path, encoding="utf-8")
    if "IMSS_CREDENCIALES" not in config:
        log.error("Falta seccion [IMSS_CREDENCIALES] en config.ini")
        return None

    section = config["IMSS_CREDENCIALES"]
    try:
        usuario = section["USUARIO"].strip()
        return ImssCredentials(
            ruta_cer=section["RUTA_CER"].strip(),
            ruta_key=section["RUTA_KEY"].strip(),
            usuario=usuario,
            contrasena=section["CONTRASENA_SITIO"].strip(),
            rfc=(section.get("RFC", "").strip() or usuario),
        )
    except KeyError as e:
        log.error("Falta el campo %s en [IMSS_CREDENCIALES] de config.ini", e)
        return None


def load_imss_credentials(script_dir: Path | str | None = None) -> ImssCredentials:
    """
    Carga credenciales IMSS aplicando la precedencia env > .env > config.ini.

    Args:
        script_dir: Directorio del script invocador, usado para localizar .env
            y config.ini. Si es None, usa el cwd.

    Raises:
        RuntimeError: si ninguna fuente provee credenciales completas.
    """
    if script_dir is None:
        script_dir_path = Path.cwd()
    else:
        script_dir_path = Path(script_dir)

    _load_dotenv_if_available(script_dir_path)

    creds = _from_env()
    if creds is not None:
        log.info("Credenciales IMSS cargadas desde variables de entorno.")
        return creds

    creds = _from_config_ini(script_dir_path)
    if creds is not None:
        log.info("Credenciales IMSS cargadas desde config.ini (legacy).")
        return creds

    raise RuntimeError(
        "No se pudieron cargar credenciales IMSS. Define las variables de entorno "
        "IMSS_RUTA_CER, IMSS_RUTA_KEY, IMSS_USUARIO, IMSS_CONTRASENA "
        "(opcionalmente IMSS_RFC), o copia config.example.ini a config.ini "
        "para uso legacy. Ver README."
    )
