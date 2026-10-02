"""Tests para el envio con reintentos."""
from __future__ import annotations

import asyncio
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

from telegram_fakes import mensaje_video
from telethon.errors import ServerError
from telethon.errors.rpcerrorlist import (
    ChatForwardsRestrictedError,
    MediaCaptionTooLongError,
    MediaInvalidError,
)
from telethon.tl import types

from reenviador.fallidos.cola_fallidos import DeadLetterQueue
from reenviador.reenvio.enviador import MessageSender


class MessageSenderTestCase(unittest.TestCase):
    def setUp(self) -> None:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.dlq = DeadLetterQueue(str(Path(tmp.name) / "failed.json"))
        self.telethon = SimpleNamespace(send_message=AsyncMock(), send_file=AsyncMock())
        self.sender = MessageSender(
            SimpleNamespace(client=self.telethon),
            max_retries=3,
            retry_base_delay=0,
            dead_letter_queue=self.dlq,
        )

    def _enviar(self) -> bool:
        return asyncio.run(
            self.sender.enviar_con_reintentos("destino", mensaje_video(7), "origen", "destino")
        )

    def test_caption_largo_se_trunca_sin_reintentar(self) -> None:
        self.telethon.send_message.side_effect = MediaCaptionTooLongError(request=None)

        self.assertTrue(self._enviar())
        self.assertEqual(self.telethon.send_message.await_count, 1)
        self.assertEqual(self.telethon.send_file.await_count, 1)

    def test_error_pasajero_se_reintenta(self) -> None:
        self.telethon.send_message.side_effect = [
            ServerError(None, "INTERNAL"),
            ServerError(None, "INTERNAL"),
            None,
        ]

        self.assertTrue(self._enviar())
        self.assertEqual(self.telethon.send_message.await_count, 3)
        self.assertEqual(self.dlq.get_count(), 0)

    def test_error_pasajero_agota_reintentos_y_va_a_dlq(self) -> None:
        self.telethon.send_message.side_effect = ConnectionError("sin red")

        self.assertFalse(self._enviar())
        self.assertEqual(self.telethon.send_message.await_count, 4)
        self.assertEqual(self.dlq.get_failed_videos()[0]["retry_count"], 3)

    def test_error_permanente_va_a_dlq_sin_reintentar(self) -> None:
        self.telethon.send_message.side_effect = ChatForwardsRestrictedError(request=None)

        self.assertFalse(self._enviar())
        self.assertEqual(self.telethon.send_message.await_count, 1)
        self.assertEqual(self.dlq.get_failed_videos()[0]["retry_count"], 0)

    def test_album_conserva_el_texto_y_formato_de_cada_archivo(self) -> None:
        negrita = [types.MessageEntityBold(offset=0, length=4)]
        mensajes = [mensaje_video(1, grouped_id=7, texto="Hola mundo"), mensaje_video(2, grouped_id=7)]
        mensajes[0].entities = negrita

        self.assertTrue(asyncio.run(self.sender.enviar_album("destino", mensajes, topic_id=55)))

        args, kwargs = self.telethon.send_file.await_args
        self.assertEqual(args[1], [mensaje.media for mensaje in mensajes])
        self.assertEqual(kwargs["caption"], ["Hola mundo", ""])
        self.assertEqual(kwargs["formatting_entities"], [negrita, []])
        self.assertEqual(kwargs["reply_to"], 55)

    def test_album_que_falla_no_va_a_la_dlq(self) -> None:
        # Quien llama lo reenvia de a uno, y ese camino es el que registra los fallos.
        self.telethon.send_file.side_effect = MediaInvalidError(request=None)

        self.assertFalse(asyncio.run(self.sender.enviar_album("destino", [mensaje_video(1), mensaje_video(2)])))
        self.assertEqual(self.dlq.get_count(), 0)


if __name__ == "__main__":
    unittest.main()
