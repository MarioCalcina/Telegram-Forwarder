"""Flujo de la aplicacion de consola: sesion, lista de chats, pedido, reenvio y resultado."""
from __future__ import annotations

import asyncio
import logging
import sys
import time

from reenviador.asistente import eleccion_chats, inicio_sesion, pedido, resultado, ui
from reenviador.infraestructura.configuracion import validar_configuracion
from reenviador.infraestructura.logs import setup_logger
from reenviador.reenvio.modelo import Estadisticas
from reenviador.reenvio.reenviar_archivos import ejecutar_reenvio

logger = logging.getLogger("telegram_bot")


def ejecutar() -> None:
    """Flujo completo de consola: sesion, asistente de configuracion y reenvio."""
    try:
        api_id, api_hash = inicio_sesion.iniciar_sesion()
    except KeyboardInterrupt:
        ui.aviso("Inicio de sesion cancelado.")
        return
    except Exception as exc:
        ui.aviso(f"No se pudo iniciar sesion: {exc}")
        return

    # El log se crea recien con la sesion iniciada: sin login el proyecto queda limpio.
    setup_logger()
    sesion = inicio_sesion.SESION.nombre

    stats = Estadisticas()
    inicio: float | None = None
    try:
        catalogo = eleccion_chats.cargar_lista_de_chats(api_id, api_hash, sesion)
        pedido_de_reenvio = pedido.pedir_pedido(catalogo)
        if pedido_de_reenvio is None:
            sys.exit(0)

        validar_configuracion(channel_mappings_override=pedido_de_reenvio.pares)

        logger.info("Iniciando bot de reenvio de Telegram")
        inicio = time.monotonic()
        asyncio.run(
            ejecutar_reenvio(
                api_id,
                api_hash,
                sesion,
                pedido_de_reenvio,
                confirmar_envio=resultado.confirmador(catalogo),
                stats=stats,
            )
        )
        logger.info("Bot finalizado correctamente")
        resultado.mostrar_resultado(stats, time.monotonic() - inicio)
    except KeyboardInterrupt:
        logger.info("Proceso interrumpido por el usuario.")
        logger.info("El progreso ha sido guardado. Puedes reanudar mas tarde.")
        if inicio is not None:
            resultado.mostrar_resultado(stats, time.monotonic() - inicio, interrumpido=True)
    except Exception as exc:
        logger.critical("Error critico: %s", exc, exc_info=True)
