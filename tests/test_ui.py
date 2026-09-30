"""Tests para las primitivas de consola."""
from __future__ import annotations

import contextlib
import io
import unittest
from unittest.mock import patch

from reenviador.asistente import ui

HASH = "0123456789abcdef0123456789abcdef"


class PreguntarOcultoTestCase(unittest.TestCase):
    def test_usa_getpass_en_una_terminal(self) -> None:
        with patch("sys.stdin") as stdin, patch.object(ui, "getpass", return_value=f"  {HASH}  ") as oculto:
            stdin.isatty.return_value = True
            self.assertEqual(ui.preguntar_oculto("API hash"), HASH)
        oculto.assert_called_once()

    def test_sin_terminal_no_usa_getpass(self) -> None:
        # En Windows getpass se quedaria esperando una consola que no existe.
        with patch("sys.stdin") as stdin, patch.object(ui, "getpass") as oculto, patch(
            "builtins.input", return_value=HASH
        ):
            stdin.isatty.return_value = False
            self.assertEqual(ui.preguntar_oculto("API hash"), HASH)
        oculto.assert_not_called()


class PreguntarSiNoTestCase(unittest.TestCase):
    def test_enter_usa_el_valor_por_defecto_y_reintenta_si_es_invalido(self) -> None:
        with contextlib.redirect_stdout(io.StringIO()), patch("builtins.input", side_effect=["", "quiza", "n"]):
            self.assertTrue(ui.preguntar_si_no("Seguir", default=True))
            self.assertFalse(ui.preguntar_si_no("Seguir", default=True))


if __name__ == "__main__":
    unittest.main()
