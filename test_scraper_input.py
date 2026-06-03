# -*- coding: utf-8 -*-
"""
Tests unitarios del contrato de entrada del scraper.

Usa solo stdlib (unittest). Sin dependencias externas — no requiere selenium,
no requiere conexión, no requiere portal real.

Ejecutar:
    python -m unittest test_scraper_input -v
"""
from __future__ import annotations

import unittest
from datetime import date

from scraper_input import (
    MAX_DIAS_RANGO,
    MODE_DATE_RANGE,
    MODE_HISTORICO,
    MODE_NSS,
    PORTAL_EV,
    PORTAL_IDSE,
    parse_input,
)


def _creds(**overrides):
    base = {
        "ruta_cer": "/tmp/c.cer",
        "ruta_key": "/tmp/k.key",
        "usuario": "ABC123456EF7",
        "contrasena": "secret",
    }
    base.update(overrides)
    return base


def _payload(portal=PORTAL_IDSE, creds=None, search=None):
    return {
        "portal": portal,
        "credentials": creds or _creds(),
        "search": search or {"mode": MODE_HISTORICO},
    }


class TestPortalValidation(unittest.TestCase):
    def test_idse_valido(self):
        r = parse_input(_payload(portal=PORTAL_IDSE))
        self.assertEqual(r.portal, PORTAL_IDSE)

    def test_escritorio_virtual_valido(self):
        r = parse_input(_payload(portal=PORTAL_EV))
        self.assertEqual(r.portal, PORTAL_EV)

    def test_portal_invalido_rechazado(self):
        with self.assertRaisesRegex(ValueError, "portal"):
            parse_input(_payload(portal="sat"))

    def test_portal_faltante_rechazado(self):
        p = _payload()
        del p["portal"]
        with self.assertRaisesRegex(ValueError, "portal"):
            parse_input(p)

    def test_top_level_no_dict_rechazado(self):
        with self.assertRaisesRegex(ValueError, "objeto JSON"):
            parse_input(["not", "a", "dict"])


class TestCredentialsValidation(unittest.TestCase):
    def test_credenciales_completas(self):
        r = parse_input(_payload())
        self.assertEqual(r.credentials.usuario, "ABC123456EF7")
        # RFC default = usuario cuando no se provee
        self.assertEqual(r.credentials.rfc, "ABC123456EF7")

    def test_rfc_explicito_se_respeta(self):
        r = parse_input(_payload(creds=_creds(rfc="OTRO123456XX1")))
        self.assertEqual(r.credentials.rfc, "OTRO123456XX1")

    def test_falta_ruta_cer_rechazado(self):
        bad = _creds()
        del bad["ruta_cer"]
        with self.assertRaisesRegex(ValueError, "ruta_cer"):
            parse_input(_payload(creds=bad))

    def test_string_vacio_rechazado(self):
        with self.assertRaisesRegex(ValueError, "contrasena"):
            parse_input(_payload(creds=_creds(contrasena="   ")))

    def test_credentials_no_dict_rechazado(self):
        p = _payload()
        p["credentials"] = "not a dict"
        with self.assertRaisesRegex(ValueError, "credentials"):
            parse_input(p)


class TestSearchNss(unittest.TestCase):
    def test_nss_valido(self):
        r = parse_input(_payload(search={"mode": MODE_NSS, "nss": "12345678901"}))
        self.assertEqual(r.search.mode, MODE_NSS)
        self.assertEqual(r.search.nss, "12345678901")

    def test_nss_10_digitos_rechazado(self):
        with self.assertRaisesRegex(ValueError, "11 dígitos"):
            parse_input(_payload(search={"mode": MODE_NSS, "nss": "1234567890"}))

    def test_nss_con_letras_rechazado(self):
        with self.assertRaisesRegex(ValueError, "11 dígitos"):
            parse_input(_payload(search={"mode": MODE_NSS, "nss": "1234567890A"}))

    def test_nss_ausente_rechazado(self):
        with self.assertRaisesRegex(ValueError, "nss"):
            parse_input(_payload(search={"mode": MODE_NSS}))


class TestSearchDateRange(unittest.TestCase):
    def test_rango_valido_15_dias_exactos(self):
        r = parse_input(_payload(search={
            "mode": MODE_DATE_RANGE,
            "fecha_inicio": "2026-05-01",
            "fecha_fin": "2026-05-16",  # +15 días
        }))
        self.assertEqual(r.search.mode, MODE_DATE_RANGE)
        self.assertEqual(r.search.fecha_inicio, date(2026, 5, 1))
        self.assertEqual(r.search.fecha_fin, date(2026, 5, 16))

    def test_rango_excede_15_dias_rechazado(self):
        with self.assertRaisesRegex(ValueError, "excede"):
            parse_input(_payload(search={
                "mode": MODE_DATE_RANGE,
                "fecha_inicio": "2026-05-01",
                "fecha_fin": "2026-05-17",  # +16 días
            }))

    def test_fecha_fin_anterior_a_inicio_rechazado(self):
        with self.assertRaisesRegex(ValueError, "anterior"):
            parse_input(_payload(search={
                "mode": MODE_DATE_RANGE,
                "fecha_inicio": "2026-05-15",
                "fecha_fin": "2026-05-01",
            }))

    def test_formato_fecha_invalido_rechazado(self):
        with self.assertRaisesRegex(ValueError, "fecha_inicio"):
            parse_input(_payload(search={
                "mode": MODE_DATE_RANGE,
                "fecha_inicio": "15/05/2026",  # formato erroneo
                "fecha_fin": "2026-05-16",
            }))

    def test_mismo_dia_es_valido(self):
        r = parse_input(_payload(search={
            "mode": MODE_DATE_RANGE,
            "fecha_inicio": "2026-05-01",
            "fecha_fin": "2026-05-01",
        }))
        self.assertEqual(r.search.fecha_inicio, r.search.fecha_fin)


class TestSearchHistorico(unittest.TestCase):
    def test_historico_sin_params_extra(self):
        r = parse_input(_payload(search={"mode": MODE_HISTORICO}))
        self.assertEqual(r.search.mode, MODE_HISTORICO)
        self.assertIsNone(r.search.nss)
        self.assertIsNone(r.search.fecha_inicio)


class TestModoInvalido(unittest.TestCase):
    def test_modo_desconocido(self):
        with self.assertRaisesRegex(ValueError, "mode"):
            parse_input(_payload(search={"mode": "ultimos_30_dias"}))

    def test_constantes_consistentes(self):
        # Si alguien cambia MAX_DIAS_RANGO, debe estar alineado con el doc.
        self.assertEqual(MAX_DIAS_RANGO, 15)


if __name__ == "__main__":
    unittest.main(verbosity=2)
