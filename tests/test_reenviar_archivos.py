"""Tests para el progreso guardado y el reintento de fallidos."""
from __future__ import annotations

import asyncio
import functools
import logging
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from typing import Any
from unittest.mock import patch

from telegram_fakes import mensaje_video
from telethon.errors.rpcerrorlist import ChatForwardsRestrictedError
from tqdm import tqdm

from reenviador.fallidos.cola_fallidos import DeadLetterQueue
from reenviador.progreso.progreso_contiguo import ProgresoContiguo
from reenviador.progreso.repositorio_estado import ChannelStateRepository
from reenviador.reenvio import reenviar_archivos
from reenviador.reenvio.enviador import MessageSender
from reenviador.reenvio.modelo import ConfirmarEnvio, Estadisticas, ParPorCopiar


class FakeTelethon:
    """Imita send_message de TelegramClient y registra cada intento."""

    def __init__(self, fallar_en: set[int] | None = None, cancelar_en: set[int] | None = None):
        self.intentos: list[int] = []
        self.fallar_en = fallar_en or set()
        self.cancelar_en = cancelar_en or set()

    async def send_message(self, entidad: Any, mensaje: Any, **kwargs: Any) -> None:
        if mensaje.id in self.cancelar_en:
            # Asi llega un Ctrl+C a las tareas dentro de asyncio.run.
            raise asyncio.CancelledError
        self.intentos.append(mensaje.id)
        if mensaje.id in self.fallar_en:
            raise ChatForwardsRestrictedError(request=None)


class FakeClientWrapper:
    """Imita TelegramClientWrapper con un canal origen en memoria."""

    def __init__(self, mensajes: dict[int, Any]):
        self.mensajes = mensajes

    async def get_entity(self, canal: Any) -> Any:
        return canal

    async def get_messages(self, entidad: Any, min_id: int = 0, topic_id: int | None = None):
        for message_id in sorted(self.mensajes):
            if message_id > min_id:
                yield self.mensajes[message_id]

    async def get_messages_by_ids(self, entidad: Any, ids: list[int]) -> list[Any]:
        return [self.mensajes.get(message_id) for message_id in ids]


class ProgresoContiguoTestCase(unittest.TestCase):
    def test_no_avanza_hasta_que_terminan_los_anteriores(self) -> None:
        progreso = ProgresoContiguo([1, 2, 3])

        self.assertIsNone(progreso.marcar_terminado(3))
        self.assertEqual(progreso.marcar_terminado(1), 1)
        self.assertEqual(progreso.marcar_terminado(2), 3)


class ReenvioTestCase(unittest.TestCase):
    def setUp(self) -> None:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.estado_path = str(Path(tmp.name) / "estado.json")
        self.dlq_path = str(Path(tmp.name) / "failed.json")

        # Aisla los tests de los valores del .env local.
        for nombre, valor in {
            "EVITAR_DUPLICADOS": False,
            "DELAY_ENTRE_MENSAJES": 0,
            "MAX_CONCURRENT_VIDEOS": 1,
            "tqdm": functools.partial(tqdm, disable=True),
        }.items():
            patcher = patch.object(reenviar_archivos, nombre, valor)
            patcher.start()
            self.addCleanup(patcher.stop)

    def _ultimo_id_guardado(self) -> int:
        return ChannelStateRepository(self.estado_path).leer_ultimo_id("o", "d")

    def _sender(self, telethon: FakeTelethon, dlq: DeadLetterQueue) -> MessageSender:
        return MessageSender(
            SimpleNamespace(client=telethon),
            max_retries=0,
            retry_base_delay=0,
            dead_letter_queue=dlq,
        )

    def _correr(
        self,
        client: FakeClientWrapper,
        telethon: FakeTelethon,
        confirmar_envio: ConfirmarEnvio | None = None,
    ) -> Estadisticas:
        dlq = DeadLetterQueue(self.dlq_path)
        stats = Estadisticas()
        asyncio.run(
            reenviar_archivos.procesar_par_canales(
                client=client,
                sender=self._sender(telethon, dlq),
                state_repo=ChannelStateRepository(self.estado_path),
                dlq=dlq,
                canal_origen="o",
                canal_destino="d",
                min_duracion_segundos=0,
                min_duracion_video_minutos=0,
                stats=stats,
                medios_destino_cache={},
                palabras_clave=set(),
                tipos_archivo={"video"},
                topic_id_origen=None,
                topic_id_destino=None,
                confirmar_envio=confirmar_envio,
            )
        )
        return stats

    def test_confirmar_envio_recibe_el_resumen_del_par(self) -> None:
        DeadLetterQueue(self.dlq_path).add_failed_video(5, 500, "o", "d", "error")
        mensajes = {5: mensaje_video(5), 10: mensaje_video(10), 11: mensaje_video(11)}
        vistos: list[ParPorCopiar] = []

        def confirmar(par: ParPorCopiar) -> bool:
            vistos.append(par)
            return True

        telethon = FakeTelethon()
        self._correr(FakeClientWrapper(mensajes), telethon, confirmar)

        self.assertEqual(len(vistos), 1)
        self.assertEqual((vistos[0].total, vistos[0].reintentos), (3, 1))
        self.assertEqual(telethon.intentos, [5, 10, 11])

    def test_fallido_posterior_al_progreso_guardado_no_se_envia_dos_veces(self) -> None:
        # La corrida anterior se corto antes de guardar el progreso: el 5 esta en la DLQ
        # y tambien entre los mensajes nuevos.
        DeadLetterQueue(self.dlq_path).add_failed_video(5, 500, "o", "d", "error")
        telethon = FakeTelethon()

        self._correr(FakeClientWrapper({5: mensaje_video(5), 6: mensaje_video(6)}), telethon)

        self.assertEqual(telethon.intentos, [5, 6])
        self.assertEqual(DeadLetterQueue(self.dlq_path).get_failed_message_ids("o", "d"), [])
        self.assertEqual(self._ultimo_id_guardado(), 6)

    def test_no_confirmar_no_envia_ni_avanza_el_progreso(self) -> None:
        DeadLetterQueue(self.dlq_path).add_failed_video(5, 500, "o", "d", "error")
        telethon = FakeTelethon()
        mensajes = {5: mensaje_video(5), 10: mensaje_video(10)}

        stats = self._correr(FakeClientWrapper(mensajes), telethon, lambda par: False)

        self.assertEqual(telethon.intentos, [])
        self.assertEqual(self._ultimo_id_guardado(), 0)
        self.assertEqual(DeadLetterQueue(self.dlq_path).get_failed_message_ids("o", "d"), [5])
        self.assertEqual(stats.pares_cancelados, 1)

    def test_log_sobre_la_barra_solo_si_el_log_va_a_consola(self) -> None:
        logger = reenviar_archivos.logger
        antes = list(logger.handlers)

        # Sin salida a consola: no agrega ninguna.
        with reenviar_archivos._log_sobre_la_barra():
            self.assertEqual(logger.handlers, antes)

        consola = logging.StreamHandler(sys.stderr)
        logger.addHandler(consola)
        self.addCleanup(logger.removeHandler, consola)

        # Con salida a consola: durante la barra la reemplaza el handler de tqdm.
        with reenviar_archivos._log_sobre_la_barra():
            self.assertNotIn(consola, logger.handlers)
        self.assertIn(consola, logger.handlers)

    def test_ctrl_c_guarda_el_progreso_pendiente(self) -> None:
        dlq = DeadLetterQueue(self.dlq_path)
        mensajes = [(mensaje_video(i), {f"video:{i * 100}"}) for i in range(1, 6)]
        telethon = FakeTelethon(cancelar_en={4})

        with self.assertRaises(asyncio.CancelledError):
            asyncio.run(
                reenviar_archivos.procesar_mensajes_paralelo(
                    mensajes=mensajes,
                    sender=self._sender(telethon, dlq),
                    entidad_destino="d",
                    state_repo=ChannelStateRepository(self.estado_path),
                    dlq=dlq,
                    medios_existentes=set(),
                    canal_origen="o",
                    canal_destino="d",
                    stats=Estadisticas(),
                    topic_id_destino=None,
                )
            )

        self.assertEqual(self._ultimo_id_guardado(), 3)

    def test_fallido_se_reintenta_en_la_siguiente_corrida(self) -> None:
        mensajes = {i: mensaje_video(i) for i in (10, 11, 12)}
        client = FakeClientWrapper(mensajes)

        # Corrida 1: el 11 falla, pero el 12 sale bien.
        primera = FakeTelethon(fallar_en={11})
        self._correr(client, primera)
        self.assertEqual(primera.intentos, [10, 11, 12])
        self.assertEqual(DeadLetterQueue(self.dlq_path).get_failed_message_ids("o", "d"), [11])
        self.assertEqual(self._ultimo_id_guardado(), 12)

        # Corrida 2: se reintenta el 11 y luego sigue con lo nuevo.
        mensajes[13] = mensaje_video(13)
        segunda = FakeTelethon()
        self._correr(client, segunda)
        self.assertEqual(segunda.intentos, [11, 13])
        self.assertEqual(DeadLetterQueue(self.dlq_path).get_failed_message_ids("o", "d"), [])
        self.assertEqual(self._ultimo_id_guardado(), 13)

    def test_fallido_borrado_en_origen_sale_de_la_dlq(self) -> None:
        DeadLetterQueue(self.dlq_path).add_failed_video(5, 500, "o", "d", "error")
        telethon = FakeTelethon()

        self._correr(FakeClientWrapper({}), telethon)

        self.assertEqual(telethon.intentos, [])
        self.assertEqual(DeadLetterQueue(self.dlq_path).get_failed_message_ids("o", "d"), [])


if __name__ == "__main__":
    unittest.main()
