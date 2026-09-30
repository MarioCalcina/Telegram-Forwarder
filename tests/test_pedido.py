"""Tests para armar el pedido de reenvio en el asistente."""
from __future__ import annotations

import contextlib
import io
import unittest
from unittest.mock import patch

from test_eleccion_chats import CATALOGO

from reenviador.asistente import pedido
from reenviador.reenvio.modelo import PedidoDeReenvio


class PedirPedidoTestCase(unittest.TestCase):
    def setUp(self) -> None:
        salida = contextlib.redirect_stdout(io.StringIO())
        self.salida = salida.__enter__()
        self.addCleanup(salida.__exit__, None, None, None)

        # Sin canales en el .env, para no depender del .env local.
        patcher = patch.object(pedido, "get_channel_mappings", return_value=[])
        patcher.start()
        self.addCleanup(patcher.stop)

    def _pedir(self, respuestas: list[str], catalogo=None) -> PedidoDeReenvio | None:
        with patch("builtins.input", side_effect=respuestas):
            return pedido.pedir_pedido(catalogo)

    def test_origen_y_destino_se_eligen_de_la_lista(self) -> None:
        resultado = self._pedir(
            [
                "1",  # origen: Peliculas HD
                "2", "1",  # destino: Series, tema Estrenos
                "",  # palabras clave
                "",  # tipos (default video)
                "",  # duracion minima (default)
                "",  # confirmar
            ],
            CATALOGO,
        )

        self.assertEqual(
            (resultado.pares, resultado.topic_id_origen, resultado.topic_id_destino),
            ([(-1001, -1002)], None, 123),
        )

    def test_sin_lista_los_canales_se_escriben_a_mano(self) -> None:
        resultado = self._pedir(
            [
                "-100111", "",  # origen y su tema
                "-100222", "",  # destino y su tema
                "",  # palabras clave
                "",  # tipos (default video)
                "",  # duracion minima (default)
                "",  # confirmar
            ]
        )

        self.assertEqual(resultado.pares, [(-100111, -100222)])

    def test_palabras_clave_tipos_y_duracion(self) -> None:
        resultado = self._pedir(["1", "3", "estreno, 4K ", "1,2", "2,5", ""], CATALOGO)

        self.assertEqual(resultado.palabras_clave, ["estreno", "4K"])
        self.assertEqual(resultado.tipos_archivo, {"video", "photo"})
        self.assertEqual(resultado.min_duracion_video_minutos, 2.5)
        self.assertIn("Palabras clave: estreno, 4K", self.salida.getvalue())

    def test_cancelar_en_el_resumen(self) -> None:
        self.assertIsNone(self._pedir(["1", "3", "", "", "", "n"], CATALOGO))


if __name__ == "__main__":
    unittest.main()
