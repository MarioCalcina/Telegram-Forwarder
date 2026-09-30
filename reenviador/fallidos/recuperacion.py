"""Recuperacion de mensajes que fallaron en corridas anteriores."""
from __future__ import annotations

import logging
from typing import Any

from reenviador.fallidos.cola_fallidos import DeadLetterQueue
from reenviador.infraestructura.cliente_telegram import TelegramClientWrapper
from reenviador.seleccion.filtros import SelectorDeMensajes

logger = logging.getLogger("telegram_bot")


async def recolectar_fallidos(
    client: TelegramClientWrapper,
    entidad_origen: Any,
    dlq: DeadLetterQueue,
    canal_origen: str,
    canal_destino: str,
    selector: SelectorDeMensajes,
) -> list[tuple[Any, set[str]]]:
    """Retorna los mensajes de la DLQ que se deben reintentar en esta corrida."""
    ids_fallidos = dlq.get_failed_message_ids(canal_origen, canal_destino)
    if not ids_fallidos:
        return []

    logger.info("Reintentando %s mensaje(s) fallidos en corridas anteriores", len(ids_fallidos))
    a_reintentar: list[tuple[Any, set[str]]] = []

    fallidos = await client.get_messages_by_ids(entidad_origen, ids_fallidos)
    for message_id, mensaje in zip(ids_fallidos, fallidos):
        if mensaje is None or selector.ya_esta_en_destino(mensaje):
            # Borrado en origen o ya copiado: no queda nada que reintentar.
            dlq.remove(message_id, canal_origen, canal_destino)
            continue

        # Si no pasa los filtros de esta corrida, se queda en la DLQ para otra.
        keys_seleccionadas = selector.seleccionar(mensaje)
        if keys_seleccionadas:
            a_reintentar.append((mensaje, keys_seleccionadas))

    return a_reintentar
