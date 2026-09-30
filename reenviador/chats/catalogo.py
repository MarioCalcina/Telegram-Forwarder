"""Catalogo de los canales, grupos y temas a los que tiene acceso la cuenta."""
from __future__ import annotations

import logging
import unicodedata
from collections.abc import Iterator
from dataclasses import dataclass

from telethon.tl import types

from reenviador.infraestructura.cliente_telegram import TelegramClientWrapper

logger = logging.getLogger("telegram_bot")

# El tema "General" de un foro no tiene mensaje raiz: no sirve para filtrar ni para
# responder, asi que equivale a no elegir tema.
ID_TEMA_GENERAL = 1


@dataclass(frozen=True)
class Tema:
    id: int
    titulo: str
    cerrado: bool = False


@dataclass(frozen=True)
class Chat:
    id: int  # ID con marca, el mismo que se usa en el .env (-100... en canales y supergrupos)
    titulo: str
    tipo: str  # "canal", "grupo" o "foro"
    temas: tuple[Tema, ...] = ()
    protegido: bool = False  # contenido protegido: Telegram no deja copiar sus archivos
    puede_publicar: bool = True  # False solo si es seguro que la cuenta no puede enviar archivos

    def tema(self, tema_id: int) -> Tema | None:
        return next((tema for tema in self.temas if tema.id == tema_id), None)


def _normalizar(texto: str) -> str:
    """Minusculas y sin tildes, para que 'peliculas' encuentre 'Películas'."""
    sin_tildes = unicodedata.normalize("NFKD", texto)
    return "".join(c for c in sin_tildes if not unicodedata.combining(c)).lower()


class CatalogoDeChats:
    """Canales y grupos en el mismo orden que en Telegram (actividad reciente primero)."""

    def __init__(self, chats: list[Chat]):
        self._chats = list(chats)

    def __len__(self) -> int:
        return len(self._chats)

    def __iter__(self) -> Iterator[Chat]:
        return iter(self._chats)

    def buscar(self, texto: str) -> list[Chat]:
        """Chats cuyo titulo contiene el texto, sin distinguir mayusculas ni tildes."""
        buscado = _normalizar(texto.strip())
        return [chat for chat in self._chats if buscado in _normalizar(chat.titulo)]

    def por_id(self, chat_id: int | str) -> Chat | None:
        return next((chat for chat in self._chats if chat.id == chat_id), None)

    def resumen(self) -> str:
        foros = [chat for chat in self._chats if chat.tipo == "foro"]
        texto = f"{len(self._chats)} canales y grupos"
        if foros:
            temas = sum(len(foro.temas) for foro in foros)
            texto += f" ({contar(len(foros), 'foro')} con {contar(temas, 'tema')})"
        return texto


def contar(cantidad: int, palabra: str) -> str:
    """'1 tema', '2 temas'."""
    return f"{cantidad} {palabra}" if cantidad == 1 else f"{cantidad} {palabra}s"


def _tipo_de(entidad: object) -> str | None:
    """Clasifica la entidad de un dialogo; None si no es un canal ni un grupo."""
    if isinstance(entidad, types.Channel):
        if entidad.broadcast:
            return "canal"
        return "foro" if entidad.forum else "grupo"

    if isinstance(entidad, types.Chat) and not entidad.deactivated:
        return "grupo"  # grupo basico (los migrados a supergrupo quedan desactivados)

    return None  # usuarios, bots y chats de los que ya no eres miembro


def _puede_publicar(entidad: object) -> bool:
    """False solo cuando es seguro que la cuenta no puede enviar archivos al chat."""
    if getattr(entidad, "creator", False):
        return True

    admin = getattr(entidad, "admin_rights", None)
    if isinstance(entidad, types.Channel) and entidad.broadcast:
        # En un canal solo publican los administradores con ese permiso.
        return bool(admin and admin.post_messages)

    if admin:
        return True  # a los administradores de un grupo no les aplican las restricciones

    # Restricciones propias de la cuenta y las generales del grupo.
    for restricciones in (
        getattr(entidad, "banned_rights", None),
        getattr(entidad, "default_banned_rights", None),
    ):
        if restricciones and (restricciones.send_messages or restricciones.send_media):
            return False
    return True


async def cargar_catalogo(client: TelegramClientWrapper) -> CatalogoDeChats:
    """Recorre los chats de la cuenta y, en los foros, sus temas."""
    chats: list[Chat] = []

    async for dialogo in client.iter_dialogs():
        tipo = _tipo_de(dialogo.entity)
        if tipo is None:
            continue

        temas: tuple[Tema, ...] = ()
        if tipo == "foro":
            try:
                temas = tuple(
                    Tema(tema.id, tema.title, bool(tema.closed))
                    for tema in await client.get_forum_topics(dialogo.entity)
                    if tema.id != ID_TEMA_GENERAL
                )
            except Exception as exc:
                # Un foro sin temas cargados se puede elegir igual escribiendo el ID del tema.
                logger.warning("No se pudieron cargar los temas de %s: %s", dialogo.name, exc)

        chats.append(
            Chat(
                dialogo.id,
                dialogo.name,
                tipo,
                temas,
                protegido=bool(getattr(dialogo.entity, "noforwards", False)),
                puede_publicar=_puede_publicar(dialogo.entity),
            )
        )

    return CatalogoDeChats(chats)
