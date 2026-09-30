"""Tests para el flujo completo de la consola."""
from __future__ import annotations

import contextlib
import io
import unittest
from unittest.mock import MagicMock, patch

from test_eleccion_chats import CATALOGO

from reenviador.asistente import consola, eleccion_chats, inicio_sesion, pedido
from reenviador.chats.catalogo import CatalogoDeChats
from reenviador.reenvio.modelo import Estadisticas, PedidoDeReenvio


class FlujoConsolaTestCase(unittest.TestCase):
    def setUp(self) -> None:
        salida = contextlib.redirect_stdout(io.StringIO())
        self.salida = salida.__enter__()
        self.addCleanup(salida.__exit__, None, None, None)

        # El log real no se toca en los tests.
        self.setup_logger = MagicMock()
        patcher = patch.object(consola, "setup_logger", self.setup_logger)
        patcher.start()
        self.addCleanup(patcher.stop)

    def _con_sesion_y_pedido(self, pedido_de_reenvio: PedidoDeReenvio | None):
        return (
            patch.object(inicio_sesion, "iniciar_sesion", return_value=(1, "hash")),
            patch.object(eleccion_chats, "cargar_lista_de_chats", return_value=CATALOGO),
            patch.object(pedido, "pedir_pedido", return_value=pedido_de_reenvio),
        )

    def test_login_cancelado_no_crea_el_log(self) -> None:
        with patch.object(inicio_sesion, "iniciar_sesion", side_effect=KeyboardInterrupt):
            consola.ejecutar()

        self.setup_logger.assert_not_called()

    def test_cancelar_el_pedido_no_cierra_la_sesion_ni_reenvia(self) -> None:
        sesion, lista, pedir = self._con_sesion_y_pedido(None)
        with sesion, lista, pedir, patch.object(consola, "ejecutar_reenvio") as reenviar, patch.object(
            inicio_sesion, "_cerrar_sesion"
        ) as cerrar:
            with self.assertRaises(SystemExit):
                consola.ejecutar()

        reenviar.assert_not_called()
        cerrar.assert_not_called()

    def test_ctrl_c_durante_el_reenvio_muestra_el_resultado_parcial(self) -> None:
        async def reenvio_interrumpido(*args: object, stats: Estadisticas, **kwargs: object) -> None:
            stats.copiados = 4
            raise KeyboardInterrupt

        sesion, lista, pedir = self._con_sesion_y_pedido(PedidoDeReenvio(pares=[(-1001, -1002)]))
        with sesion, lista, pedir, patch.object(consola, "ejecutar_reenvio", side_effect=reenvio_interrumpido):
            consola.ejecutar()

        texto = self.salida.getvalue()
        self.assertIn("Resultado (interrumpido)", texto)
        self.assertIn("Copiados: 4", texto)

    def test_la_lista_de_chats_se_carga_con_la_sesion_guardada(self) -> None:
        sesion, _, pedir = self._con_sesion_y_pedido(None)
        with sesion, pedir, patch.object(
            eleccion_chats, "cargar_lista_de_chats", return_value=CatalogoDeChats([])
        ) as cargar, self.assertRaises(SystemExit):
            consola.ejecutar()

        cargar.assert_called_once_with(1, "hash", inicio_sesion.SESION.nombre)


if __name__ == "__main__":
    unittest.main()
