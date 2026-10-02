"""Deteccion de medios que ya existen en el canal destino."""
from __future__ import annotations

import logging
from typing import Any

from reenviador.infraestructura.cliente_telegram import TelegramClientWrapper
from reenviador.seleccion.indice_destinos import IndiceDeDestinos
from reenviador.seleccion.tipos_de_medio import get_media_keys_for_message

logger = logging.getLogger("telegram_bot")


async def obtener_medios_existentes(
    client: TelegramClientWrapper,
    entidad_destino: Any,
    canal_destino: str,
    indice: IndiceDeDestinos,
) -> set[str]:
    """
    Medios que ya hay en el destino: los del indice guardado mas los publicados despues.

    La primera vez recorre el canal entero; las siguientes, solo los mensajes nuevos.
    Se guardan todos los tipos de medio, asi el indice sirve aunque cambien los filtros.
    """
    medios = indice.medios(canal_destino)
    desde = indice.ultimo_id(canal_destino)
    if desde:
        logger.info("Revisando duplicados en el destino: %s medios ya conocidos", len(medios))
    else:
        logger.info("Analizando canal de destino para evitar duplicados (la primera vez lo recorre entero)")

    ultimo_revisado = desde
    revisados = 0
    try:
        # En orden ascendente: si se corta, todo lo anterior a ultimo_revisado ya esta en el indice.
        async for mensaje in client.get_messages(entidad_destino, desde):
            medios.update(get_media_keys_for_message(mensaje))
            ultimo_revisado = mensaje.id
            revisados += 1

        logger.info(
            "Analisis completado. %s medios en el destino (%s mensajes nuevos revisados)",
            len(medios),
            revisados,
        )
    except Exception as exc:
        logger.warning(
            "Error al analizar duplicados: %s. Se sigue con lo revisado hasta ahora.",
            exc,
        )
    finally:
        indice.avanzar(canal_destino, ultimo_revisado)
        indice.guardar()

    return medios
