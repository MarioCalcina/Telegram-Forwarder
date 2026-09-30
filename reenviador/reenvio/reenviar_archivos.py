"""Caso de uso principal: reenviar archivos entre canales de Telegram."""
from __future__ import annotations

import asyncio
import contextlib
import logging
import sys
from typing import Any

from telethon.tl.types import MessageService
from tqdm import tqdm
from tqdm.contrib.logging import logging_redirect_tqdm

from reenviador.fallidos.cola_fallidos import DeadLetterQueue
from reenviador.fallidos.recuperacion import recolectar_fallidos
from reenviador.infraestructura.cliente_telegram import TelegramClientWrapper
from reenviador.infraestructura.configuracion import (
    ARCHIVO_ESTADO,
    DELAY_ENTRE_MENSAJES,
    ENABLE_NOTIFICATIONS,
    EVITAR_DUPLICADOS,
    MAX_CONCURRENT_VIDEOS,
    MAX_RETRIES,
    MIN_DURACION_VIDEO_MINUTOS,
    NOTIFICATION_CHAT_ID,
    RETRY_BASE_DELAY,
    get_channel_mappings,
)
from reenviador.notificaciones.notificador import TelegramNotifier
from reenviador.progreso.progreso_contiguo import ProgresoContiguo
from reenviador.progreso.repositorio_estado import ChannelStateRepository
from reenviador.reenvio.enviador import MessageSender
from reenviador.reenvio.modelo import ConfirmarEnvio, Estadisticas, ParPorCopiar, PedidoDeReenvio
from reenviador.seleccion.duplicados import obtener_medios_existentes
from reenviador.seleccion.filtros import SelectorDeMensajes, normalizar_palabras_clave
from reenviador.seleccion.tipos_de_medio import normalizar_tipos_archivo

logger = logging.getLogger("telegram_bot")
STATE_FLUSH_BATCH_SIZE = 10


def _log_sobre_la_barra() -> contextlib.AbstractContextManager[Any]:
    """Imprime los avisos del log por encima de la barra de progreso en vez de cortarla."""
    a_consola = any(
        isinstance(handler, logging.StreamHandler) and handler.stream in (sys.stdout, sys.stderr)
        for handler in logger.handlers
    )
    # logging_redirect_tqdm agrega su propia salida a consola: si el log no escribia
    # en consola (por ejemplo, en los tests), no debe empezar a hacerlo.
    return logging_redirect_tqdm(loggers=[logger]) if a_consola else contextlib.nullcontext()


async def ejecutar_reenvio(
    api_id: int,
    api_hash: str,
    sesion: str,
    pedido: PedidoDeReenvio,
    confirmar_envio: ConfirmarEnvio | None = None,
    stats: Estadisticas | None = None,
) -> None:
    """
    Ejecuta el caso de uso completo de reenvio de archivos.

    ``confirmar_envio`` se consulta antes de enviar cada par (sin el, se envia directo).
    ``stats`` se va llenando durante la corrida, asi quien llama puede mostrar un
    resumen aunque se interrumpa con Ctrl+C.
    """
    logger.info("Iniciando proceso de reenvio")

    channel_mappings = pedido.pares or get_channel_mappings()
    if not channel_mappings:
        logger.error("No hay canales configurados para procesar")
        return

    palabras_clave = normalizar_palabras_clave(pedido.palabras_clave)
    tipos_normalizados = normalizar_tipos_archivo(pedido.tipos_archivo)
    min_duracion_video_minutos = (
        float(MIN_DURACION_VIDEO_MINUTOS)
        if pedido.min_duracion_video_minutos is None
        else max(0.0, float(pedido.min_duracion_video_minutos))
    )

    if palabras_clave:
        logger.info("Filtro por palabras clave activo: %s", ", ".join(sorted(palabras_clave)))

    logger.info("Tipos de archivo seleccionados: %s", ", ".join(sorted(tipos_normalizados)))
    logger.info("Canales a procesar: %s par(es) origen-destino", len(channel_mappings))

    state_repo = ChannelStateRepository(ARCHIVO_ESTADO)
    dlq = DeadLetterQueue()
    min_duracion_segundos = min_duracion_video_minutos * 60

    if stats is None:
        stats = Estadisticas()
    stats.canales_procesados = len(channel_mappings)

    # Reutiliza IDs de medios analizados cuando varios mappings apuntan al mismo destino.
    medios_destino_cache: dict[str, set[str]] = {}

    async with TelegramClientWrapper(api_id, api_hash, sesion) as client:
        notifier = TelegramNotifier(client.client, NOTIFICATION_CHAT_ID, ENABLE_NOTIFICATIONS)
        sender = MessageSender(
            client,
            max_retries=MAX_RETRIES,
            retry_base_delay=RETRY_BASE_DELAY,
            dead_letter_queue=dlq,
        )

        try:
            for canal_origen, canal_destino in channel_mappings:
                un_solo_par = len(channel_mappings) == 1
                await procesar_par_canales(
                    client=client,
                    sender=sender,
                    state_repo=state_repo,
                    dlq=dlq,
                    canal_origen=canal_origen,
                    canal_destino=canal_destino,
                    min_duracion_segundos=min_duracion_segundos,
                    min_duracion_video_minutos=min_duracion_video_minutos,
                    stats=stats,
                    medios_destino_cache=medios_destino_cache,
                    palabras_clave=palabras_clave,
                    tipos_archivo=tipos_normalizados,
                    topic_id_origen=pedido.topic_id_origen if un_solo_par else None,
                    topic_id_destino=pedido.topic_id_destino if un_solo_par else None,
                    confirmar_envio=confirmar_envio,
                )

            logger.info("Proceso completado")
            logger.info("Archivos copiados: %s", stats.copiados)
            logger.info("Archivos omitidos: %s", stats.omitidos)

            if stats.fallidos > 0:
                logger.warning("Archivos fallidos: %s (revisa failed_videos.json)", stats.fallidos)

            await notifier.notify_completion(
                copiados=stats.copiados,
                omitidos=stats.omitidos,
                fallidos=stats.fallidos,
                canales_procesados=stats.canales_procesados,
            )

        except ValueError as exc:
            logger.error("Error al acceder a los canales: %s", exc)
            logger.error("Verifica tus IDs de canal en el archivo .env")

        except Exception as exc:
            logger.error("Error inesperado: %s", exc, exc_info=True)
            await notifier.notify_error(str(exc), "Error critico durante ejecucion")

        finally:
            # Tambien se guarda al interrumpir con Ctrl+C.
            state_repo.flush()


async def procesar_par_canales(
    client: TelegramClientWrapper,
    sender: MessageSender,
    state_repo: ChannelStateRepository,
    dlq: DeadLetterQueue,
    canal_origen: int | str,
    canal_destino: int | str,
    min_duracion_segundos: float,
    min_duracion_video_minutos: float,
    stats: Estadisticas,
    medios_destino_cache: dict[str, set[str]],
    palabras_clave: set[str],
    tipos_archivo: set[str],
    topic_id_origen: int | None,
    topic_id_destino: int | None,
    confirmar_envio: ConfirmarEnvio | None = None,
) -> None:
    """Procesa un par origen-destino."""
    topic_details: list[str] = []
    if topic_id_origen:
        topic_details.append(f"origen tema {topic_id_origen}")
    if topic_id_destino:
        topic_details.append(f"destino tema {topic_id_destino}")
    extra = f" ({', '.join(topic_details)})" if topic_details else ""
    logger.info("Procesando %s -> %s%s", canal_origen, canal_destino, extra)

    try:
        entidad_origen = await client.get_entity(canal_origen)
        entidad_destino = await client.get_entity(canal_destino)

        origen_key = (
            f"{canal_origen},{topic_id_origen}" if topic_id_origen else str(canal_origen)
        )
        destino_key = (
            f"{canal_destino},{topic_id_destino}" if topic_id_destino else str(canal_destino)
        )
        ultimo_id_procesado = state_repo.leer_ultimo_id(origen_key, destino_key)

        if min_duracion_video_minutos > 0 and "video" in tipos_archivo:
            logger.info("Filtro de video activo: %s minutos o mas", min_duracion_video_minutos)

        medios_existentes = (
            await obtener_medios_existentes(
                client,
                entidad_destino,
                destino_key,
                medios_destino_cache,
                tipos_archivo,
            )
            if EVITAR_DUPLICADOS
            else set()
        )

        logger.info("Recolectando mensajes a procesar")
        selector = SelectorDeMensajes(
            tipos_archivo=tipos_archivo,
            min_duracion_segundos=min_duracion_segundos,
            palabras_clave=palabras_clave,
            medios_existentes=medios_existentes,
            evitar_duplicados=EVITAR_DUPLICADOS,
        )

        # Primero se reintentan los mensajes que fallaron en corridas anteriores.
        mensajes_a_procesar = await recolectar_fallidos(
            client,
            entidad_origen,
            dlq,
            origen_key,
            destino_key,
            selector,
        )
        ids_reintento = {mensaje.id for mensaje, _ in mensajes_a_procesar}

        async for mensaje in client.get_messages(
            entidad_origen,
            ultimo_id_procesado,
            topic_id=topic_id_origen,
        ):
            if isinstance(mensaje, MessageService):
                continue

            if mensaje.id in ids_reintento:
                # Ya esta en la lista como reintento de la DLQ: pasa si la corrida anterior se
                # corto antes de guardar el progreso. Sin esto se enviaria dos veces.
                continue

            keys_seleccionadas = selector.seleccionar(mensaje)
            if keys_seleccionadas:
                mensajes_a_procesar.append((mensaje, keys_seleccionadas))

        stats.omitidos += selector.omitidos
        total_a_copiar = len(mensajes_a_procesar)
        logger.info("Total de archivos a copiar: %s", total_a_copiar)

        if total_a_copiar == 0:
            logger.info("No hay nuevos archivos para copiar")
            return

        if confirmar_envio is not None:
            par = ParPorCopiar(
                canal_origen=canal_origen,
                topic_id_origen=topic_id_origen,
                canal_destino=canal_destino,
                topic_id_destino=topic_id_destino,
                total=total_a_copiar,
                reintentos=len(ids_reintento),
                omitidos=selector.omitidos,
            )
            if not confirmar_envio(par):
                # Sin enviar nada, el progreso no avanza: la proxima corrida los vuelve a ofrecer.
                logger.info("Copia cancelada por el usuario: %s -> %s", canal_origen, canal_destino)
                stats.pares_cancelados += 1
                return

        await procesar_mensajes_paralelo(
            mensajes=mensajes_a_procesar,
            sender=sender,
            entidad_destino=entidad_destino,
            state_repo=state_repo,
            dlq=dlq,
            medios_existentes=medios_existentes,
            canal_origen=origen_key,
            canal_destino=destino_key,
            stats=stats,
            topic_id_destino=topic_id_destino,
            ids_reintento=ids_reintento,
        )

    except Exception as exc:
        logger.error("Error procesando %s -> %s: %s", canal_origen, canal_destino, exc)
        stats.pares_con_error += 1


async def procesar_mensajes_paralelo(
    mensajes: list[tuple[Any, set[str]]],
    sender: MessageSender,
    entidad_destino: Any,
    state_repo: ChannelStateRepository,
    dlq: DeadLetterQueue,
    medios_existentes: set[str],
    canal_origen: str,
    canal_destino: str,
    stats: Estadisticas,
    topic_id_destino: int | None,
    ids_reintento: set[int] | None = None,
) -> None:
    """Procesa mensajes en paralelo con limite de concurrencia."""
    max_concurrent = max(1, MAX_CONCURRENT_VIDEOS)
    pending: set[asyncio.Task[None]] = set()
    ids_reintento = ids_reintento or set()

    # Los reintentos de la DLQ son anteriores al estado guardado: no lo mueven.
    progreso = ProgresoContiguo(
        [mensaje.id for mensaje, _ in mensajes if mensaje.id not in ids_reintento]
    )
    guardados_desde_flush = 0
    procesados = 0
    total = len(mensajes)

    async def procesar_archivo(item: tuple[Any, set[str]], pbar: tqdm[Any]) -> None:
        nonlocal guardados_desde_flush, procesados
        mensaje, keys_seleccionadas = item

        exito = await sender.enviar_con_reintentos(
            entidad_destino,
            mensaje,
            canal_origen=canal_origen,
            canal_destino=canal_destino,
            topic_id=topic_id_destino,
        )

        if exito:
            if EVITAR_DUPLICADOS:
                medios_existentes.update(keys_seleccionadas)

            if mensaje.id in ids_reintento:
                dlq.remove(mensaje.id, canal_origen, canal_destino)

            stats.copiados += 1
        else:
            stats.fallidos += 1

        # Un fallo tambien cuenta como terminado: queda en la DLQ y se reintenta
        # al inicio de la proxima corrida.
        ultimo_contiguo = progreso.marcar_terminado(mensaje.id)
        if ultimo_contiguo is not None:
            state_repo.guardar_ultimo_id(canal_origen, canal_destino, ultimo_contiguo, flush=False)
            guardados_desde_flush += 1

            if guardados_desde_flush >= STATE_FLUSH_BATCH_SIZE:
                state_repo.flush()
                guardados_desde_flush = 0

        procesados += 1
        pbar.update(1)

        if procesados % 10 == 0 or procesados == total:
            pbar.set_postfix(
                {"copiados": stats.copiados, "omitidos": stats.omitidos, "fallidos": stats.fallidos}
            )

        if max_concurrent == 1 and DELAY_ENTRE_MENSAJES > 0:
            await asyncio.sleep(DELAY_ENTRE_MENSAJES)

    try:
        with _log_sobre_la_barra(), tqdm(total=total, desc="Procesando archivos", unit="archivo") as pbar:
            for item in mensajes:
                pending.add(asyncio.create_task(procesar_archivo(item, pbar)))

                if len(pending) >= max_concurrent:
                    done, pending = await asyncio.wait(pending, return_when=asyncio.FIRST_COMPLETED)
                    for task in done:
                        task.result()

            if pending:
                await asyncio.gather(*pending)
    finally:
        # Tambien se guarda al interrumpir con Ctrl+C o ante un error inesperado.
        state_repo.flush()
