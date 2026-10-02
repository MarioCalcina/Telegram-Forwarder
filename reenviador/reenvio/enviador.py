"""Manejo del envio de mensajes con reintentos y manejo de errores."""
from __future__ import annotations

import asyncio
import logging
from typing import Any

from telethon.errors import ServerError, TimedOutError
from telethon.errors.rpcerrorlist import FloodWaitError, MediaCaptionTooLongError

from reenviador.fallidos.cola_fallidos import DeadLetterQueue
from reenviador.reenvio.caption import truncar_caption_seguro
from reenviador.reenvio.reintentos import RetryManager

logger = logging.getLogger("telegram_bot")

# Solo se reintentan errores pasajeros (servidor, timeout, red). Los errores 400/403
# (caption largo, permisos, contenido protegido) no se resuelven reintentando.
ERRORES_REINTENTABLES: tuple[type[BaseException], ...] = (ServerError, TimedOutError, OSError)


class MessageSender:
    """Envia mensajes de Telegram con manejo robusto de errores."""

    def __init__(
        self,
        client: Any,
        max_retries: int = 3,
        retry_base_delay: float = 1.0,
        dead_letter_queue: DeadLetterQueue | None = None,
    ):
        self.client = client.client
        self.retry_manager = RetryManager(max_retries, retry_base_delay)
        self.dlq = dead_letter_queue or DeadLetterQueue()

    async def enviar_con_reintentos(
        self,
        entidad_destino: Any,
        mensaje: Any,
        canal_origen: str = "",
        canal_destino: str = "",
        topic_id: int | None = None,
    ) -> bool:
        """Envia un mensaje con reintentos y manejo de errores."""
        try:
            await self._ejecutar_con_reintentos(
                self._send_message_internal,
                entidad_destino,
                mensaje,
                topic_id,
            )
            return True

        except MediaCaptionTooLongError:
            return await self._handle_long_caption(
                entidad_destino,
                mensaje,
                canal_origen,
                canal_destino,
                topic_id,
            )

        except Exception as exc:
            self._registrar_fallo(mensaje, canal_origen, canal_destino, exc)
            return False

    async def enviar_album(
        self,
        entidad_destino: Any,
        mensajes: list[Any],
        topic_id: int | None = None,
    ) -> bool:
        """
        Envia juntos los mensajes de un album, con el texto y el formato de cada uno.

        Si falla retorna False sin registrar nada: quien llama los envia de a uno, y ese
        camino ya maneja los captions largos y la DLQ de cada mensaje.
        """
        try:
            await self._ejecutar_con_reintentos(self._send_album_internal, entidad_destino, mensajes, topic_id)
            return True
        except Exception as exc:
            logger.warning("No se pudo enviar el album completo (%s): se envia archivo por archivo.", exc)
            return False

    async def _ejecutar_con_reintentos(self, func: Any, *args: Any) -> None:
        """Ejecuta un envio reintentando errores pasajeros y respetando un FloodWait."""
        try:
            await self.retry_manager.execute_with_retry(func, *args, error_types=ERRORES_REINTENTABLES)
        except FloodWaitError as exc:
            logger.warning("Rate limit alcanzado. Esperando %s segundos...", exc.seconds)
            await asyncio.sleep(exc.seconds)
            await self.retry_manager.execute_with_retry(func, *args, error_types=ERRORES_REINTENTABLES)

    async def _send_message_internal(self, entidad_destino: Any, mensaje: Any, topic_id: int | None) -> None:
        """Envia el mensaje (metodo interno para retry)."""
        kwargs = {"reply_to": topic_id} if topic_id else {}
        await self.client.send_message(entidad_destino, mensaje, **kwargs)

    async def _send_album_internal(
        self,
        entidad_destino: Any,
        mensajes: list[Any],
        topic_id: int | None,
    ) -> None:
        """Envia varios medios como un solo album (metodo interno para retry)."""
        kwargs = {"reply_to": topic_id} if topic_id else {}
        await self.client.send_file(
            entidad_destino,
            [mensaje.media for mensaje in mensajes],
            caption=[mensaje.message or "" for mensaje in mensajes],
            formatting_entities=[mensaje.entities or [] for mensaje in mensajes],
            **kwargs,
        )

    async def _send_file_internal(
        self,
        entidad_destino: Any,
        media: Any,
        caption: str,
        topic_id: int | None,
    ) -> None:
        """Envia un medio con caption propio (metodo interno para retry)."""
        kwargs = {"reply_to": topic_id} if topic_id else {}
        await self.client.send_file(entidad_destino, media, caption=caption, **kwargs)

    async def _handle_long_caption(
        self,
        entidad_destino: Any,
        mensaje: Any,
        canal_origen: str,
        canal_destino: str,
        topic_id: int | None,
    ) -> bool:
        """Maneja captions demasiado largos."""
        logger.warning("Caption demasiado largo, recortando...")

        caption = mensaje.text or ""
        caption_truncado = truncar_caption_seguro(caption)

        try:
            await self._ejecutar_con_reintentos(
                self._send_file_internal,
                entidad_destino,
                mensaje.media,
                caption_truncado,
                topic_id,
            )
            return True
        except Exception as exc:
            self._registrar_fallo(mensaje, canal_origen, canal_destino, exc)
            return False

    def _registrar_fallo(self, mensaje: Any, canal_origen: str, canal_destino: str, exc: Exception) -> None:
        """Registra un envio fallido definitivo en el log y en la DLQ."""
        # Un error reintentable solo llega aqui despues de agotar todos los reintentos.
        reintentos = self.retry_manager.max_retries if isinstance(exc, ERRORES_REINTENTABLES) else 0
        logger.error(
            "Error al enviar mensaje %s tras %s reintento(s): %s",
            mensaje.id,
            reintentos,
            exc,
        )
        self._save_to_dlq(mensaje, canal_origen, canal_destino, str(exc), reintentos)

    @staticmethod
    def _extract_media_id(mensaje: Any) -> int:
        """Extrae un ID representativo del medio para DLQ."""
        for attr in ("video", "photo", "audio", "voice", "gif", "sticker", "document"):
            media = getattr(mensaje, attr, None)
            if media and getattr(media, "id", None):
                return int(media.id)
        return 0

    def _save_to_dlq(
        self,
        mensaje: Any,
        canal_origen: str,
        canal_destino: str,
        error: str,
        retry_count: int,
    ) -> None:
        """Guarda un mensaje fallido en la Dead Letter Queue."""
        media_id = self._extract_media_id(mensaje)
        if media_id == 0:
            return

        self.dlq.add_failed_video(
            mensaje_id=mensaje.id,
            video_id=media_id,
            canal_origen=str(canal_origen),
            canal_destino=str(canal_destino),
            error=error,
            retry_count=retry_count,
        )
