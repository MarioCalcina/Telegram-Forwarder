"""Tests para elegir origen y destino desde la lista de canales, grupos y temas."""
from __future__ import annotations

import contextlib
import io
import unittest
from unittest.mock import AsyncMock, patch

from reenviador.asistente import eleccion_chats
from reenviador.chats.catalogo import CatalogoDeChats, Chat, Tema

CATALOGO = CatalogoDeChats(
    [
        Chat(-1001, "Películas HD", "canal"),
        Chat(-1002, "Series", "foro", (Tema(123, "Estrenos"), Tema(4200, "Archivo", cerrado=True))),
        Chat(-1003, "Charla", "grupo"),
        Chat(-1004, "Privado", "canal", protegido=True),
        Chat(-1005, "Noticias", "canal", puede_publicar=False),
    ]
)


class ElegirChatTestCase(unittest.TestCase):
    def setUp(self) -> None:
        salida = contextlib.redirect_stdout(io.StringIO())
        salida.__enter__()
        self.addCleanup(salida.__exit__, None, None, None)

    def _elegir(self, respuestas: list[str], es_origen: bool = True) -> tuple:
        with patch("builtins.input", side_effect=respuestas):
            return eleccion_chats.elegir_chat("Origen" if es_origen else "Destino", CATALOGO, es_origen)

    def test_elegir_por_numero(self) -> None:
        self.assertEqual(self._elegir(["3"]), (-1003, None))

    def test_buscar_y_luego_elegir_el_resultado(self) -> None:
        self.assertEqual(self._elegir(["peliculas", "1"]), (-1001, None))

    def test_busqueda_sin_resultados_y_numero_fuera_de_rango_se_reintentan(self) -> None:
        self.assertEqual(self._elegir(["nada", "9", "", "1"]), (-1001, None))

    def test_foro_pide_el_tema(self) -> None:
        self.assertEqual(self._elegir(["2", "1"], es_origen=False), (-1002, 123))

    def test_foro_enter_es_todo_el_grupo(self) -> None:
        self.assertEqual(self._elegir(["2", ""]), (-1002, None))

    def test_id_de_la_lista_escrito_a_mano(self) -> None:
        self.assertEqual(self._elegir(["-1003"]), (-1003, None))

    def test_id_desconocido_con_tema_como_antes(self) -> None:
        # ID que no esta en la lista, con tema: Enter mantiene el tema escrito.
        self.assertEqual(self._elegir(["-100999,7", ""]), (-100999, 7))

    def test_origen_protegido_avisa_y_deja_elegir_otro(self) -> None:
        self.assertEqual(self._elegir(["4", "n", "1"]), (-1001, None))

    def test_origen_protegido_se_puede_elegir_igual(self) -> None:
        self.assertEqual(self._elegir(["4", "s"]), (-1004, None))

    def test_destino_sin_permiso_avisa(self) -> None:
        self.assertEqual(self._elegir(["5", "n", "3"], es_origen=False), (-1003, None))

    def test_protegido_no_es_problema_como_destino(self) -> None:
        self.assertEqual(self._elegir(["4"], es_origen=False), (-1004, None))

    def test_la_lista_marca_solo_los_problemas_del_rol(self) -> None:
        with contextlib.redirect_stdout(io.StringIO()) as salida:
            eleccion_chats._mostrar_chats(list(CATALOGO), es_origen=True)
        lineas = salida.getvalue().splitlines()

        self.assertIn("⚠ protegido", lineas[3])
        self.assertNotIn("⚠", lineas[4])  # sin permiso para publicar solo importa en destino


class CargarListaTestCase(unittest.TestCase):
    def test_si_la_lista_no_carga_se_escriben_los_ids(self) -> None:
        with contextlib.redirect_stdout(io.StringIO()), patch.object(
            eleccion_chats, "_leer_catalogo", new=AsyncMock(side_effect=OSError("sin red"))
        ):
            catalogo = eleccion_chats.cargar_lista_de_chats(1, "hash", "sesion")

        self.assertEqual(len(catalogo), 0)


if __name__ == "__main__":
    unittest.main()
