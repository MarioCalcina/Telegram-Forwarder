"""Tests para el indice de medios de los canales destino."""
from __future__ import annotations

import asyncio
import tempfile
import unittest
from pathlib import Path
from typing import Any

from telegram_fakes import mensaje_gif, mensaje_video

from reenviador.seleccion.duplicados import obtener_medios_existentes
from reenviador.seleccion.indice_destinos import IndiceDeDestinos


class FakeDestino:
    """Canal destino en memoria; registra desde que mensaje se pidio cada lectura."""

    def __init__(self, mensajes: dict[int, Any], falla_en: int | None = None):
        self.mensajes = mensajes
        self.falla_en = falla_en
        self.lecturas_desde: list[int] = []

    async def get_messages(self, entidad: Any, min_id: int = 0, topic_id: int | None = None):
        self.lecturas_desde.append(min_id)
        for message_id in sorted(m for m in self.mensajes if m > min_id):
            if message_id == self.falla_en:
                raise ConnectionError("se corto la conexion")
            yield self.mensajes[message_id]


class IndiceDeDestinosTestCase(unittest.TestCase):
    def setUp(self) -> None:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.archivo = str(Path(tmp.name) / "indice.json")

    def test_guardar_y_volver_a_cargar(self) -> None:
        indice = IndiceDeDestinos(self.archivo)
        indice.medios("-100d").update({"video:1", "photo:2"})
        indice.avanzar("-100d", 10)
        indice.guardar()

        cargado = IndiceDeDestinos(self.archivo)
        self.assertEqual(cargado.ultimo_id("-100d"), 10)
        self.assertEqual(cargado.medios("-100d"), {"video:1", "photo:2"})

    def test_avanzar_nunca_retrocede(self) -> None:
        indice = IndiceDeDestinos(self.archivo)
        indice.avanzar("d", 10)
        indice.avanzar("d", 5)

        self.assertEqual(indice.ultimo_id("d"), 10)

    def test_medios_es_siempre_el_mismo_set(self) -> None:
        indice = IndiceDeDestinos(self.archivo)
        indice.medios("d").add("video:1")

        self.assertIn("video:1", indice.medios("d"))

    def test_archivo_danado_se_descarta(self) -> None:
        Path(self.archivo).write_text("no es json", encoding="utf-8")

        indice = IndiceDeDestinos(self.archivo)
        self.assertEqual((indice.ultimo_id("d"), indice.medios("d")), (0, set()))


class ObtenerMediosExistentesTestCase(unittest.TestCase):
    def setUp(self) -> None:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.archivo = str(Path(tmp.name) / "indice.json")

    def _revisar(self, destino: FakeDestino) -> set[str]:
        # Un indice nuevo por llamada: como una corrida nueva que lo lee del disco.
        return asyncio.run(obtener_medios_existentes(destino, "entidad", "d", IndiceDeDestinos(self.archivo)))

    def test_primera_vez_recorre_todo_y_despues_solo_lo_nuevo(self) -> None:
        destino = FakeDestino({1: mensaje_video(1), 2: mensaje_gif(2)})
        # Guarda todos los tipos, no solo los elegidos: sirve aunque cambien los filtros.
        self.assertEqual(self._revisar(destino), {"video:100", "gif:200"})

        destino.mensajes[3] = mensaje_video(3)
        self.assertEqual(self._revisar(destino), {"video:100", "gif:200", "video:300"})
        self.assertEqual(destino.lecturas_desde, [0, 2])

    def test_si_se_corta_guarda_hasta_donde_llego(self) -> None:
        destino = FakeDestino({i: mensaje_video(i) for i in (1, 2, 3, 4)}, falla_en=3)

        self.assertEqual(self._revisar(destino), {"video:100", "video:200"})
        self.assertEqual(IndiceDeDestinos(self.archivo).ultimo_id("d"), 2)


if __name__ == "__main__":
    unittest.main()
