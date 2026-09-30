"""Tests para la confirmacion antes de enviar y el resultado final."""
from __future__ import annotations

import contextlib
import io
import unittest
from unittest.mock import patch

from test_eleccion_chats import CATALOGO

from reenviador.asistente import resultado
from reenviador.reenvio.modelo import Estadisticas, ParPorCopiar


class ConfirmarYResultadoTestCase(unittest.TestCase):
    def test_confirmacion_muestra_los_nombres_y_el_total(self) -> None:
        par = ParPorCopiar(
            canal_origen=-1001,
            topic_id_origen=None,
            canal_destino=-1002,
            topic_id_destino=123,
            total=103,
            reintentos=2,
            omitidos=12,
        )
        with contextlib.redirect_stdout(io.StringIO()) as salida, patch("builtins.input", return_value=""):
            self.assertTrue(resultado.confirmador(CATALOGO)(par))

        texto = salida.getvalue()
        self.assertIn("Películas HD (-1001)", texto)
        self.assertIn("Series (-1002), tema Estrenos", texto)
        self.assertIn("103 archivos (incluye 2 fallidos", texto)
        self.assertIn("Omitidos por filtros o duplicados: 12", texto)

    def test_formatear_duracion(self) -> None:
        for segundos, esperado in ((45, "45 s"), (169, "2 min 49 s"), (3900, "1 h 5 min")):
            with self.subTest(segundos=segundos):
                self.assertEqual(resultado.formatear_duracion(segundos), esperado)

    def test_resultado_final(self) -> None:
        stats = Estadisticas(copiados=100, omitidos=12, fallidos=3, pares_cancelados=1)
        with contextlib.redirect_stdout(io.StringIO()) as salida:
            resultado.mostrar_resultado(stats, 169)

        texto = salida.getvalue()
        for esperado in (
            "Copiados: 100",
            "Omitidos por filtros o duplicados: 12",
            "Fallidos: 3",
            "Pares que elegiste no copiar: 1",
            "Tiempo: 2 min 49 s",
        ):
            self.assertIn(esperado, texto)
        self.assertNotIn("interrumpido", texto)


if __name__ == "__main__":
    unittest.main()
