"""Tests para los archivos que genera el bot: sesion, progreso, fallidos y log."""
from __future__ import annotations

import sqlite3
import tempfile
import unittest
from contextlib import closing
from pathlib import Path
from unittest.mock import patch

from reenviador.sesion import datos_locales
from reenviador.seleccion.indice_destinos import ARCHIVO_INDICE_DESTINOS
from reenviador.sesion.sesion_guardada import SesionGuardada

HASH = "0123456789abcdef0123456789abcdef"


class SesionGuardadaTestCase(unittest.TestCase):
    def setUp(self) -> None:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.nombre = str(Path(tmp.name) / "sesion")
        self.sesion = SesionGuardada(self.nombre)

    def test_sin_archivo_no_hay_sesion(self) -> None:
        self.assertFalse(self.sesion.existe())

    def test_borrar_quita_la_sesion_y_su_journal(self) -> None:
        for extension in (".session", ".session-journal"):
            Path(f"{self.nombre}{extension}").touch()

        self.sesion.borrar()

        self.assertFalse(self.sesion.existe())
        self.assertFalse(Path(f"{self.nombre}.session-journal").exists())

    def test_borrar_sin_archivos_no_falla(self) -> None:
        self.sesion.borrar()

    def test_guardar_y_leer_credenciales_dentro_de_la_sesion(self) -> None:
        Path(f"{self.nombre}.session").touch()

        self.sesion.guardar_credenciales(123, HASH)
        self.sesion.guardar_credenciales(456, HASH)  # reemplaza, no acumula

        self.assertEqual(SesionGuardada(self.nombre).leer_credenciales(), (456, HASH))
        self.assertEqual(len(list(Path(self.nombre).parent.iterdir())), 1)  # sin archivo aparte

    def test_sin_sesion_no_hay_credenciales_ni_se_crea_nada(self) -> None:
        self.sesion.guardar_credenciales(123, HASH)

        self.assertIsNone(self.sesion.leer_credenciales())
        self.assertFalse(self.sesion.existe())

    def test_sesion_sin_la_tabla_no_tiene_credenciales(self) -> None:
        # Como una sesion de Telethon creada por una version anterior del bot.
        with closing(sqlite3.connect(f"{self.nombre}.session")) as conexion, conexion:
            conexion.execute("CREATE TABLE version (version INTEGER)")

        self.assertIsNone(self.sesion.leer_credenciales())

    def test_borrar_la_sesion_borra_las_credenciales(self) -> None:
        Path(f"{self.nombre}.session").touch()
        self.sesion.guardar_credenciales(123, HASH)

        self.sesion.borrar()

        self.assertIsNone(self.sesion.leer_credenciales())


class DatosLocalesTestCase(unittest.TestCase):
    def test_borrar_datos_locales_deja_el_proyecto_limpio(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            archivos = tuple(Path(tmp) / nombre for nombre in ("estado.json", "fallidos.json", "bot.log"))
            archivos[0].write_text("{}", encoding="utf-8")
            archivos[2].write_text("log", encoding="utf-8")

            # Con rutas temporales: el test nunca toca los archivos reales del proyecto.
            with patch.object(datos_locales, "ARCHIVOS_GENERADOS", archivos):
                datos_locales.borrar_datos_locales()

            self.assertEqual(list(Path(tmp).iterdir()), [])

    def test_cerrar_sesion_tambien_borra_el_indice_de_destinos(self) -> None:
        self.assertIn(Path(ARCHIVO_INDICE_DESTINOS), datos_locales.ARCHIVOS_GENERADOS)


if __name__ == "__main__":
    unittest.main()
