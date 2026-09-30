"""Tests para el wrapper del cliente de Telegram."""
from __future__ import annotations

import asyncio
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock

from telethon.errors.rpcerrorlist import ApiIdInvalidError
from telethon.sessions import StringSession
from telethon.tl import types

from reenviador.infraestructura.cliente_telegram import TelegramClientWrapper

HASH = "0123456789abcdef0123456789abcdef"


def _wrapper(**kwargs) -> TelegramClientWrapper:
    """Crea el wrapper (con sesion en memoria) y los metodos de red reemplazados por mocks."""

    async def crear() -> TelegramClientWrapper:
        wrapper = TelegramClientWrapper(1, HASH, StringSession(), **kwargs)
        for metodo in (
            "start",
            "connect",
            "disconnect",
            "log_out",
            "get_me",
            "get_dialogs",
            "get_input_entity",
        ):
            setattr(wrapper.client, metodo, AsyncMock())
        return wrapper

    return asyncio.run(crear())


async def _entrar_y_salir(wrapper: TelegramClientWrapper) -> None:
    async with wrapper:
        pass


class TelegramClientWrapperTestCase(unittest.TestCase):
    def test_login_usa_las_preguntas_de_la_consola(self) -> None:
        telefono, codigo, password = (lambda: "t"), (lambda: "c"), (lambda: "p")
        wrapper = _wrapper(pedir_telefono=telefono, pedir_codigo=codigo, pedir_password=password)

        asyncio.run(_entrar_y_salir(wrapper))

        wrapper.client.start.assert_awaited_once_with(
            phone=telefono,
            code_callback=codigo,
            password=password,
        )

    def test_si_el_login_falla_se_cierra_la_conexion(self) -> None:
        wrapper = _wrapper()
        wrapper.client.start.side_effect = ApiIdInvalidError(request=None)

        with self.assertRaises(ApiIdInvalidError):
            asyncio.run(_entrar_y_salir(wrapper))
        wrapper.client.disconnect.assert_awaited_once()

    def test_cuenta_autorizada_describe_la_cuenta(self) -> None:
        wrapper = _wrapper()
        wrapper.client.get_me.return_value = SimpleNamespace(
            id=1, first_name="Mario", last_name=None, username="mario"
        )

        self.assertEqual(asyncio.run(wrapper.cuenta_autorizada()), "Mario (@mario)")
        wrapper.client.start.assert_not_awaited()
        wrapper.client.disconnect.assert_awaited_once()

    def test_cuenta_autorizada_none_si_la_sesion_ya_no_vale(self) -> None:
        wrapper = _wrapper()
        wrapper.client.get_me.return_value = None

        self.assertIsNone(asyncio.run(wrapper.cuenta_autorizada()))

    def test_cerrar_sesion_desconecta_aunque_telegram_no_confirme(self) -> None:
        wrapper = _wrapper()
        wrapper.client.log_out.return_value = False

        self.assertFalse(asyncio.run(wrapper.cerrar_sesion()))
        wrapper.client.disconnect.assert_awaited_once()

    def test_temas_del_foro_se_leen_de_todas_las_paginas(self) -> None:
        wrapper = _wrapper()

        def tema(tema_id: int) -> SimpleNamespace:
            return SimpleNamespace(id=tema_id, top_message=tema_id * 10, date=None)

        primera = SimpleNamespace(topics=[tema(i) for i in range(1, 101)], messages=[], count=102)
        segunda = SimpleNamespace(
            topics=[tema(101), types.ForumTopicDeleted(id=102)], messages=[], count=102
        )
        # Las peticiones crudas (await client(request)) pasan por aqui.
        wrapper.client = AsyncMock(side_effect=[primera, segunda])

        temas = asyncio.run(wrapper.get_forum_topics("foro"))

        self.assertEqual([t.id for t in temas], list(range(1, 102)))  # sin el tema borrado
        segunda_peticion = wrapper.client.await_args_list[1].args[0]
        self.assertEqual((segunda_peticion.offset_topic, segunda_peticion.offset_id), (100, 1000))

    def test_canal_desconocido_carga_los_chats_y_reintenta(self) -> None:
        wrapper = _wrapper()
        wrapper.client.get_input_entity.side_effect = [ValueError("no encontrada"), "canal"]

        self.assertEqual(asyncio.run(wrapper.get_entity(-100123)), "canal")
        wrapper.client.get_dialogs.assert_awaited_once()


if __name__ == "__main__":
    unittest.main()
