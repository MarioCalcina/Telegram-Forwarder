"""Clasificacion de los medios de un mensaje por tipo de archivo."""
from __future__ import annotations

from typing import Any

TIPOS_ARCHIVO_VALIDOS = {"video", "photo", "audio", "document", "voice", "gif", "sticker"}


def get_media_keys_for_message(mensaje: Any) -> set[str]:
    """Retorna claves de media detectadas para un mensaje."""
    keys: set[str] = set()

    # Telethon marca como "video" todo documento con atributo de video, lo que
    # incluye GIFs y stickers animados; esos se clasifican solo en su propio tipo.
    es_gif_o_sticker = getattr(mensaje, "gif", None) or getattr(mensaje, "sticker", None)
    if getattr(mensaje, "video", None) and not es_gif_o_sticker:
        keys.add(f"video:{mensaje.video.id}")

    if getattr(mensaje, "photo", None):
        keys.add(f"photo:{mensaje.photo.id}")

    if getattr(mensaje, "audio", None):
        keys.add(f"audio:{mensaje.audio.id}")

    if getattr(mensaje, "voice", None):
        keys.add(f"voice:{mensaje.voice.id}")

    if getattr(mensaje, "gif", None):
        keys.add(f"gif:{mensaje.gif.id}")

    if getattr(mensaje, "sticker", None):
        keys.add(f"sticker:{mensaje.sticker.id}")

    if getattr(mensaje, "document", None):
        is_special_document = any(
            [
                getattr(mensaje, "video", None),
                getattr(mensaje, "audio", None),
                getattr(mensaje, "voice", None),
                getattr(mensaje, "gif", None),
                getattr(mensaje, "sticker", None),
            ]
        )
        if not is_special_document:
            keys.add(f"document:{mensaje.document.id}")

    return keys


def keys_por_tipos(mensaje: Any, tipos_archivo: set[str]) -> set[str]:
    """Filtra claves media de un mensaje segun los tipos solicitados."""
    keys = get_media_keys_for_message(mensaje)
    if not keys:
        return set()

    return {key for key in keys if key.split(":", 1)[0] in tipos_archivo}


def normalizar_tipos_archivo(tipos_archivo: set[str] | list[str] | None) -> set[str]:
    """Normaliza tipos de archivo validos; por defecto usa solo video."""
    if not tipos_archivo:
        return {"video"}

    tipos = {str(tipo).strip().lower() for tipo in tipos_archivo if str(tipo).strip()}
    tipos_validos = tipos & TIPOS_ARCHIVO_VALIDOS
    return tipos_validos or {"video"}
