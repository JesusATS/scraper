# -*- coding: utf-8 -*-
"""
Contrato de entrada del scraper cuando se invoca vía orquestador (idse-ai).

El orquestador pipea un JSON por stdin con la forma:

  {
    "portal": "idse" | "escritorio-virtual",
    "credentials": {
      "ruta_cer": "/tmp/.../certificado.cer",
      "ruta_key": "/tmp/.../llave.key",
      "usuario":  "ABC123456EF7",
      "contrasena": "...",
      "rfc": "ABC123456EF7"   // opcional, default = usuario
    },
    "search": {
      "mode": "nss" | "date_range" | "historico",
      "nss": "12345678901",            // requerido si mode="nss"
      "fecha_inicio": "2026-05-01",    // requerido si mode="date_range"
      "fecha_fin":    "2026-05-15"     // requerido si mode="date_range", diff <= 15 días
    }
  }

Validación estricta — cualquier desviación levanta `ValueError` con mensaje
en español. El entry point `run.py` traduce a exit code 2 + stderr.

Sin dependencias externas (solo stdlib).
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date
from typing import Any, Optional

# Constantes del dominio --------------------------------------------------

PORTAL_IDSE = "idse"
PORTAL_EV = "escritorio-virtual"
PORTALES_VALIDOS = (PORTAL_IDSE, PORTAL_EV)

MODE_NSS = "nss"
MODE_DATE_RANGE = "date_range"
MODE_HISTORICO = "historico"
MODOS_VALIDOS = (MODE_NSS, MODE_DATE_RANGE, MODE_HISTORICO)

# NSS mexicano: 11 dígitos (estándar IMSS actual)
_NSS_REGEX = re.compile(r"^\d{11}$")

# Rango máximo permitido por las reglas de negocio
MAX_DIAS_RANGO = 15


# Dataclasses --------------------------------------------------------------


@dataclass(frozen=True)
class CredentialsInput:
    ruta_cer: str
    ruta_key: str
    usuario: str
    contrasena: str
    rfc: str  # Default = usuario si no viene en el JSON


@dataclass(frozen=True)
class SearchParams:
    mode: str
    nss: Optional[str] = None
    fecha_inicio: Optional[date] = None
    fecha_fin: Optional[date] = None


@dataclass(frozen=True)
class ScraperInput:
    portal: str
    credentials: CredentialsInput
    search: SearchParams


# Parsing y validación -----------------------------------------------------


def _require(d: dict, key: str, ctx: str) -> Any:
    if key not in d or d[key] is None or (isinstance(d[key], str) and not d[key].strip()):
        raise ValueError(f"falta campo requerido '{key}' en {ctx}")
    return d[key]


def _parse_credentials(raw: Any) -> CredentialsInput:
    if not isinstance(raw, dict):
        raise ValueError("'credentials' debe ser un objeto JSON")
    ruta_cer = _require(raw, "ruta_cer", "credentials").strip()
    ruta_key = _require(raw, "ruta_key", "credentials").strip()
    usuario = _require(raw, "usuario", "credentials").strip()
    contrasena = _require(raw, "contrasena", "credentials").strip()
    rfc_raw = raw.get("rfc", "")
    rfc = rfc_raw.strip() if isinstance(rfc_raw, str) and rfc_raw.strip() else usuario
    return CredentialsInput(
        ruta_cer=ruta_cer,
        ruta_key=ruta_key,
        usuario=usuario,
        contrasena=contrasena,
        rfc=rfc,
    )


def _parse_iso_date(value: Any, field: str) -> date:
    if not isinstance(value, str):
        raise ValueError(f"'{field}' debe ser string ISO YYYY-MM-DD")
    try:
        return date.fromisoformat(value)
    except ValueError as e:
        raise ValueError(f"'{field}' inválido (formato esperado YYYY-MM-DD): {e}") from e


def _parse_search(raw: Any) -> SearchParams:
    if not isinstance(raw, dict):
        raise ValueError("'search' debe ser un objeto JSON")
    mode = _require(raw, "mode", "search")
    if mode not in MODOS_VALIDOS:
        raise ValueError(
            f"'search.mode' inválido: {mode!r}. Valores válidos: {MODOS_VALIDOS}"
        )

    if mode == MODE_NSS:
        nss = _require(raw, "nss", "search (mode=nss)")
        if not isinstance(nss, str) or not _NSS_REGEX.match(nss.strip()):
            raise ValueError(
                "'search.nss' inválido — debe ser 11 dígitos (estándar IMSS)"
            )
        return SearchParams(mode=MODE_NSS, nss=nss.strip())

    if mode == MODE_DATE_RANGE:
        fi = _parse_iso_date(_require(raw, "fecha_inicio", "search (mode=date_range)"), "fecha_inicio")
        ff = _parse_iso_date(_require(raw, "fecha_fin", "search (mode=date_range)"), "fecha_fin")
        if ff < fi:
            raise ValueError("'fecha_fin' no puede ser anterior a 'fecha_inicio'")
        delta = (ff - fi).days
        if delta > MAX_DIAS_RANGO:
            raise ValueError(
                f"rango de fechas excede el máximo permitido ({delta} días > {MAX_DIAS_RANGO})"
            )
        return SearchParams(mode=MODE_DATE_RANGE, fecha_inicio=fi, fecha_fin=ff)

    # mode == MODE_HISTORICO
    return SearchParams(mode=MODE_HISTORICO)


def parse_input(payload: Any) -> ScraperInput:
    """
    Valida y parsea el JSON recibido por el orquestador.

    Args:
        payload: el dict resultante de json.load(stdin).

    Returns:
        ScraperInput validado e inmutable.

    Raises:
        ValueError con mensaje en español, listo para mostrar al humano.
    """
    if not isinstance(payload, dict):
        raise ValueError("el input debe ser un objeto JSON en el top-level")

    portal = _require(payload, "portal", "input")
    if portal not in PORTALES_VALIDOS:
        raise ValueError(
            f"'portal' inválido: {portal!r}. Valores válidos: {PORTALES_VALIDOS}"
        )

    creds = _parse_credentials(payload.get("credentials"))
    search = _parse_search(payload.get("search"))
    return ScraperInput(portal=portal, credentials=creds, search=search)
