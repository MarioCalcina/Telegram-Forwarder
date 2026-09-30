"""Deteccion de medios que ya existen en el canal destino."""
from __future__ import annotations

import logging
from typing import Any

from reenviador.infraestructura.cliente_telegram import TelegramClientWrapper
from reenviador.seleccion.tipos_de_medio import keys_por_tipos

logger = logging.getLogger("telegram_bot")


async def obtener_medios_existentes(
    client: TelegramClientWrapper,
    entidad_destino: Any,
    destino_key: str,
    medios_destino_cache: dict[str, set[str]],
    tipos_archivo: set[str],
) -> set[str]:
    """Retorna IDs existentes en destino, usando cache por canal destino."""
    if destino_key not in medios_destino_cache:
        medios_destino_cache[destino_key] = await _analizar_destino(
            client,
            entidad_destino,
            tipos_archivo,
        )

    return medios_destino_cache[destino_key]


async def _analizar_destino(
    client: TelegramClientWrapper,
    entidad: Any,
    tipos_archivo: set[str],
) -> set[str]:
    """Recorre el canal destino y junta las claves de medios de los tipos pedidos."""
    medios_existentes: set[str] = set()

    logger.info("Analizando canal de destino para evitar duplicados")
    try:
        async for mensaje in client.get_messages(entidad):
            medios_existentes.update(keys_por_tipos(mensaje, tipos_archivo))

        logger.info(
            "Analisis completado. Encontrados %s medios existentes",
            len(medios_existentes),
        )
    except Exception as exc:
        logger.warning(
            "Error al analizar duplicados: %s. Continuando sin chequeo de duplicados.",
            exc,
        )

    return medios_existentes
