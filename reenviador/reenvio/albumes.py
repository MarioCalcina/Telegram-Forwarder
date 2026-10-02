"""Agrupar los mensajes de un mismo album para enviarlos juntos."""
from __future__ import annotations

from typing import Any

# Telegram no admite albumes de mas de 10 archivos.
MAX_ARCHIVOS_POR_ALBUM = 10

Item = tuple[Any, set[str]]  # (mensaje, claves de medio seleccionadas)


def agrupar_en_lotes(mensajes: list[Item]) -> list[list[Item]]:
    """
    Junta en un lote los mensajes seguidos de un mismo album; el resto va de a uno.

    Si un filtro descarto parte de un album, los que quedan se envian juntos igual.
    """
    lotes: list[list[Item]] = []
    for item in mensajes:
        album = getattr(item[0], "grouped_id", None)
        anterior = lotes[-1] if lotes else None
        if (
            album is not None
            and anterior is not None
            and getattr(anterior[0][0], "grouped_id", None) == album
            and len(anterior) < MAX_ARCHIVOS_POR_ALBUM
        ):
            anterior.append(item)
        else:
            lotes.append([item])
    return lotes
