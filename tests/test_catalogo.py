"""Tests para el catalogo de canales, grupos y temas."""
from __future__ import annotations

import asyncio
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock

from telethon.tl import types

from reenviador.chats.catalogo import CatalogoDeChats, Chat, Tema, cargar_catalogo

SIN_FOTO = types.ChatPhotoEmpty()


def _canal(channel_id: int, titulo: str, **banderas: object) -> types.Channel:
    return types.Channel(id=channel_id, title=titulo, photo=SIN_FOTO, date=None, **banderas)


def _grupo_basico(chat_id: int, titulo: str, deactivated: bool = False) -> types.Chat:
    return types.Chat(
        id=chat_id,
        title=titulo,
        photo=SIN_FOTO,
        participants_count=3,
        date=None,
        version=1,
        deactivated=deactivated,
    )


class FakeCliente:
    """Imita los dos metodos de TelegramClientWrapper que usa el catalogo."""

    def __init__(self, dialogos: list[SimpleNamespace], temas: dict[str, list] | Exception):
        self._dialogos = dialogos
        self.get_forum_topics = AsyncMock(
            side_effect=temas if isinstance(temas, Exception) else lambda e: temas[e.title]
        )

    async def iter_dialogs(self):
        for dialogo in self._dialogos:
            yield dialogo


def _dialogo(dialogo_id: int, entidad: object) -> SimpleNamespace:
    return SimpleNamespace(id=dialogo_id, name=getattr(entidad, "title", "Usuario"), entity=entidad)


class CargarCatalogoTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.dialogos = [
            _dialogo(-1001, _canal(1, "Peliculas HD", broadcast=True)),
            _dialogo(-1002, _canal(2, "Charla", megagroup=True)),
            _dialogo(-1003, _canal(3, "Series", megagroup=True, forum=True)),
            _dialogo(-4, _grupo_basico(4, "Familia")),
            _dialogo(-5, _grupo_basico(5, "Migrado", deactivated=True)),
            _dialogo(6, types.User(id=6, first_name="Ana")),
        ]
        self.temas_series = [
            SimpleNamespace(id=1, title="General", closed=False),
            SimpleNamespace(id=123, title="Estrenos", closed=False),
            SimpleNamespace(id=4200, title="Archivo", closed=True),
        ]

    def test_clasifica_canales_grupos_y_foros_y_descarta_el_resto(self) -> None:
        catalogo = asyncio.run(cargar_catalogo(FakeCliente(self.dialogos, {"Series": self.temas_series})))

        self.assertEqual(
            [(chat.id, chat.titulo, chat.tipo) for chat in catalogo],
            [
                (-1001, "Peliculas HD", "canal"),
                (-1002, "Charla", "grupo"),
                (-1003, "Series", "foro"),
                (-4, "Familia", "grupo"),
            ],
        )

    def test_carga_los_temas_del_foro_sin_el_general(self) -> None:
        catalogo = asyncio.run(cargar_catalogo(FakeCliente(self.dialogos, {"Series": self.temas_series})))

        self.assertEqual(
            catalogo.por_id(-1003).temas,
            (Tema(123, "Estrenos"), Tema(4200, "Archivo", cerrado=True)),
        )

    def test_si_fallan_los_temas_el_foro_igual_aparece(self) -> None:
        catalogo = asyncio.run(cargar_catalogo(FakeCliente(self.dialogos, ConnectionError("red"))))

        foro = catalogo.por_id(-1003)
        self.assertEqual((foro.tipo, foro.temas), ("foro", ()))


class ChatsQueNoFuncionanTestCase(unittest.TestCase):
    def _chat(self, entidad: object) -> Chat:
        catalogo = asyncio.run(cargar_catalogo(FakeCliente([_dialogo(-1, entidad)], {})))
        return next(iter(catalogo))

    def test_contenido_protegido(self) -> None:
        self.assertTrue(self._chat(_canal(1, "C", broadcast=True, noforwards=True)).protegido)
        self.assertFalse(self._chat(_canal(1, "C", broadcast=True)).protegido)

    def test_canal_solo_publican_los_admins_con_permiso(self) -> None:
        publicar = types.ChatAdminRights(post_messages=True)
        solo_editar = types.ChatAdminRights(edit_messages=True)

        self.assertFalse(self._chat(_canal(1, "C", broadcast=True)).puede_publicar)
        self.assertFalse(self._chat(_canal(1, "C", broadcast=True, admin_rights=solo_editar)).puede_publicar)
        self.assertTrue(self._chat(_canal(1, "C", broadcast=True, admin_rights=publicar)).puede_publicar)
        self.assertTrue(self._chat(_canal(1, "C", broadcast=True, creator=True)).puede_publicar)

    def test_grupo_que_prohibe_enviar_archivos(self) -> None:
        sin_archivos = types.ChatBannedRights(until_date=None, send_media=True)

        self.assertTrue(self._chat(_canal(1, "G", megagroup=True)).puede_publicar)
        self.assertFalse(
            self._chat(_canal(1, "G", megagroup=True, default_banned_rights=sin_archivos)).puede_publicar
        )
        self.assertFalse(self._chat(_canal(1, "G", megagroup=True, banned_rights=sin_archivos)).puede_publicar)
        # A un admin del grupo no le aplican las restricciones generales.
        self.assertTrue(
            self._chat(
                _canal(
                    1,
                    "G",
                    megagroup=True,
                    default_banned_rights=sin_archivos,
                    admin_rights=types.ChatAdminRights(delete_messages=True),
                )
            ).puede_publicar
        )


class CatalogoDeChatsTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.catalogo = CatalogoDeChats(
            [
                Chat(-1001, "Películas HD", "canal"),
                Chat(-1002, "Series", "foro", (Tema(123, "Estrenos"),)),
            ]
        )

    def test_buscar_ignora_mayusculas_y_tildes(self) -> None:
        self.assertEqual([chat.id for chat in self.catalogo.buscar("PELICULAS")], [-1001])

    def test_resumen(self) -> None:
        self.assertEqual(self.catalogo.resumen(), "2 canales y grupos (1 foro con 1 tema)")

    def test_por_id_y_tema(self) -> None:
        self.assertEqual(self.catalogo.por_id(-1002).tema(123).titulo, "Estrenos")
        self.assertIsNone(self.catalogo.por_id(-999))


if __name__ == "__main__":
    unittest.main()
