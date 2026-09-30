"""Wrapper del cliente de Telegram."""
from __future__ import annotations

import logging
from collections.abc import Callable
from typing import Any, AsyncIterator

from telethon import TelegramClient, functions, types
from telethon.sessions import Session

logger = logging.getLogger("telegram_bot")

TEMAS_POR_PAGINA = 100


class TelegramClientWrapper:
    """Wrapper para el cliente de Telegram con operaciones comunes."""

    def __init__(
        self,
        api_id: int,
        api_hash: str,
        sesion: str | Session,
        pedir_telefono: Callable[[], str] | None = None,
        pedir_codigo: Callable[[], str] | None = None,
        pedir_password: Callable[[], str] | None = None,
    ):
        # "sesion" es el nombre del archivo .session (sin extension) o una Session de Telethon.
        self.client = TelegramClient(sesion, api_id, api_hash)
        opciones_login = {
            "phone": pedir_telefono,
            "code_callback": pedir_codigo,
            "password": pedir_password,
        }
        self._opciones_login = {clave: valor for clave, valor in opciones_login.items() if valor}

    async def __aenter__(self) -> "TelegramClientWrapper":
        try:
            await self.client.start(**self._opciones_login)
        except BaseException:
            # Si start() falla, __aexit__ no se ejecuta: hay que cerrar la conexion aqui.
            await self.client.disconnect()
            raise

        logger.info("Cliente conectado exitosamente")
        return self

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        await self.client.disconnect()

    async def cuenta_autorizada(self) -> str | None:
        """Sin pedir nada por consola: describe la cuenta de la sesion, o None si ya no es valida."""
        await self.client.connect()
        try:
            # get_me() retorna None si la sesion vencio o se cerro desde otro dispositivo,
            # pero deja pasar ApiIdInvalidError (is_user_authorized() lo ocultaria).
            yo = await self.client.get_me()
        finally:
            await self.client.disconnect()

        if yo is None:
            return None

        nombre = " ".join(parte for parte in (yo.first_name, yo.last_name) if parte) or str(yo.id)
        return f"{nombre} (@{yo.username})" if yo.username else nombre

    async def cerrar_sesion(self) -> bool:
        """Cierra la sesion en Telegram para que no quede activa en la cuenta."""
        await self.client.connect()
        try:
            return await self.client.log_out()
        finally:
            await self.client.disconnect()

    async def get_entity(self, channel_id: int | str) -> Any:
        """Obtiene la entidad de un canal."""
        try:
            return await self.client.get_input_entity(channel_id)
        except ValueError:
            # Una sesion recien iniciada aun no conoce los canales por ID numerico;
            # cargar los chats los agrega al cache de la sesion.
            await self.client.get_dialogs()
            return await self.client.get_input_entity(channel_id)

    async def get_messages(
        self,
        entidad: Any,
        min_id: int = 0,
        topic_id: int | None = None,
    ) -> AsyncIterator[Any]:
        """Itera mensajes de forma ascendente desde un min_id (opcionalmente por tema)."""
        kwargs: dict[str, Any] = {"min_id": min_id, "reverse": True}
        if topic_id:
            kwargs["reply_to"] = topic_id

        async for mensaje in self.client.iter_messages(entidad, **kwargs):
            yield mensaje

    async def get_messages_by_ids(self, entidad: Any, ids: list[int]) -> list[Any]:
        """Obtiene mensajes por ID; los que ya no existen vienen como None."""
        return list(await self.client.get_messages(entidad, ids=ids))

    async def iter_dialogs(self) -> AsyncIterator[Any]:
        """Itera los chats de la cuenta, en el mismo orden que la app de Telegram."""
        async for dialogo in self.client.iter_dialogs():
            yield dialogo

    async def get_forum_topics(self, entidad: Any) -> list[Any]:
        """Todos los temas de un grupo tipo foro (Telegram los entrega por paginas)."""
        temas: list[Any] = []
        offset_date, offset_id, offset_topic = None, 0, 0

        while True:
            pagina = await self.client(
                functions.messages.GetForumTopicsRequest(
                    peer=entidad,
                    offset_date=offset_date,
                    offset_id=offset_id,
                    offset_topic=offset_topic,
                    limit=TEMAS_POR_PAGINA,
                )
            )
            nuevos = [tema for tema in pagina.topics if not isinstance(tema, types.ForumTopicDeleted)]
            temas.extend(nuevos)

            if len(pagina.topics) < TEMAS_POR_PAGINA or not nuevos or len(temas) >= pagina.count:
                return temas

            # La siguiente pagina empieza despues del ultimo tema de esta.
            ultimo = nuevos[-1]
            mensajes = {mensaje.id: mensaje for mensaje in pagina.messages}
            ultimo_mensaje = mensajes.get(ultimo.top_message)
            offset_date = ultimo_mensaje.date if ultimo_mensaje else ultimo.date
            offset_id, offset_topic = ultimo.top_message, ultimo.id
