"""Sistema de notificaciones a Telegram."""
from __future__ import annotations

import logging

from telethon import TelegramClient

logger = logging.getLogger("telegram_bot")


class TelegramNotifier:
    """Envia notificaciones a Telegram sobre el estado del bot."""

    def __init__(
        self,
        client: TelegramClient,
        chat_id: int | None = None,
        enabled: bool = True,
    ) -> None:
        self.client = client
        self.chat_id = chat_id
        self.enabled = enabled and chat_id is not None

    async def notify_completion(
        self,
        copiados: int,
        omitidos: int,
        fallidos: int,
        canales_procesados: int,
    ) -> None:
        """Notifica que el proceso completo."""
        if not self.enabled:
            return

        try:
            mensaje = self._format_completion_message(copiados, omitidos, fallidos, canales_procesados)
            await self.client.send_message(self.chat_id, mensaje)
            logger.info("Notificacion de completado enviada")
        except Exception as exc:
            logger.error("Error al enviar notificacion de completado: %s", exc)

    async def notify_error(self, error: str, context: str = "") -> None:
        """Notifica un error critico."""
        if not self.enabled:
            return

        try:
            mensaje = "**Error critico en el reenviador de Telegram**\n\n"
            mensaje += f"**Error:** {error}\n"
            if context:
                mensaje += f"**Contexto:** {context}\n"

            await self.client.send_message(self.chat_id, mensaje)
            logger.info("Notificacion de error enviada")
        except Exception as exc:
            logger.error("Error al enviar notificacion de error: %s", exc)

    @staticmethod
    def _format_completion_message(
        copiados: int,
        omitidos: int,
        fallidos: int,
        canales_procesados: int,
    ) -> str:
        """Formatea el mensaje de completado."""
        mensaje = "**Reenviador de Telegram - Proceso completado**\n\n"
        mensaje += "**Estadisticas:**\n"
        mensaje += f"- Archivos copiados: {copiados}\n"
        mensaje += f"- Archivos omitidos: {omitidos}\n"

        if fallidos > 0:
            mensaje += f"- Archivos fallidos: {fallidos}\n"

        if canales_procesados > 1:
            mensaje += f"- Canales procesados: {canales_procesados}\n"

        return mensaje
