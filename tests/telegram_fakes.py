"""Helpers para construir mensajes reales de Telethon en los tests."""
from __future__ import annotations

import logging
from typing import Any

from telethon.tl import types

# Evita que los logs del bot ensucien la salida de los tests.
logging.getLogger("telegram_bot").addHandler(logging.NullHandler())


def mensaje_con_documento(message_id: int, attributes: list[Any]) -> types.Message:
    documento = types.Document(
        id=message_id * 100,
        access_hash=0,
        file_reference=b"",
        date=None,
        mime_type="video/mp4",
        size=1,
        dc_id=1,
        attributes=attributes,
    )
    return types.Message(
        id=message_id,
        peer_id=types.PeerChannel(1),
        date=None,
        message="",
        media=types.MessageMediaDocument(document=documento),
    )


def mensaje_video(message_id: int, duracion: int = 600) -> types.Message:
    return mensaje_con_documento(
        message_id,
        [types.DocumentAttributeVideo(duration=duracion, w=1, h=1)],
    )


def mensaje_gif(message_id: int) -> types.Message:
    return mensaje_con_documento(
        message_id,
        [types.DocumentAttributeVideo(duration=3, w=1, h=1), types.DocumentAttributeAnimated()],
    )


def mensaje_sticker_video(message_id: int) -> types.Message:
    return mensaje_con_documento(
        message_id,
        [
            types.DocumentAttributeVideo(duration=3, w=1, h=1),
            types.DocumentAttributeSticker(alt="", stickerset=types.InputStickerSetEmpty()),
        ],
    )
