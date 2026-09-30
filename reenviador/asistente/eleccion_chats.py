"""Elegir el origen y el destino: de la lista de canales, grupos y temas, o escribiendo el ID."""
from __future__ import annotations

import asyncio
import logging

from reenviador.asistente import ui
from reenviador.chats.catalogo import CatalogoDeChats, Chat, cargar_catalogo, contar
from reenviador.infraestructura.cliente_telegram import TelegramClientWrapper
from reenviador.infraestructura.configuracion import parse_channel_input

logger = logging.getLogger("telegram_bot")

MAX_CHATS_EN_PANTALLA = 30


async def _leer_catalogo(api_id: int, api_hash: str, sesion: str) -> CatalogoDeChats:
    async with TelegramClientWrapper(api_id, api_hash, sesion) as client:
        return await cargar_catalogo(client)


def cargar_lista_de_chats(api_id: int, api_hash: str, sesion: str) -> CatalogoDeChats:
    """Carga los canales, grupos y temas de la cuenta; si falla, se escriben los IDs a mano."""
    ui.titulo("Canales y grupos")
    ui.info("Cargando tus canales, grupos y sus temas...")
    try:
        catalogo = asyncio.run(_leer_catalogo(api_id, api_hash, sesion))
    except Exception as exc:
        logger.warning("No se pudo cargar la lista de canales y grupos: %s", exc)
        ui.aviso("No se pudo cargar la lista: tendras que escribir los IDs a mano.")
        return CatalogoDeChats([])

    ui.ok(f"Cargados {catalogo.resumen()}")
    return catalogo


def _parse_canal_y_tema(raw: str) -> tuple[int | str | None, int | None, str | None]:
    """Parsea canal y topic opcional desde 'canal' o 'canal,topic'."""
    value = raw.strip()
    if not value:
        return None, None, "valor vacio"

    parts = [part.strip() for part in value.split(",") if part.strip()]
    if len(parts) > 2:
        return None, None, "usa formato canal o canal,topic_id"

    canal = parse_channel_input(parts[0])
    if canal is None:
        return None, None, "canal invalido"

    if len(parts) == 1:
        return canal, None, None

    topic_raw = parts[1]
    if not topic_raw.isdigit():
        return None, None, "el topic ID debe ser numerico"

    topic_id = int(topic_raw)
    if topic_id <= 0:
        return None, None, "el topic ID debe ser mayor a 0"

    return canal, topic_id, None


def _pedir_topic_opcional(label: str, default_topic: int | None) -> int | None:
    """Pide topic por separado; permite Enter para default y 0 para quitar topic."""
    while True:
        if default_topic is not None:
            prompt = f"{label} [Enter={default_topic}, 0=sin tema]"
        else:
            prompt = f"{label} [Enter=sin tema]"

        raw = ui.preguntar(prompt)
        if not raw:
            return default_topic

        if raw == "0":
            return None

        if raw.isdigit() and int(raw) > 0:
            return int(raw)

        ui.aviso("Topic invalido. Usa un entero positivo o 0.")


def pedir_canal(label: str) -> tuple[int | str, int | None]:
    """Pide canal y topic escribiendo el ID (cuando no hay lista cargada)."""
    while True:
        raw = ui.preguntar(f"{label} (ID, @usuario o ID,topic)")
        canal, topic_inline, error = _parse_canal_y_tema(raw)
        if error:
            ui.aviso(f"Entrada invalida: {error}")
            continue

        topic = _pedir_topic_opcional(f"Tema de {label}", topic_inline)
        return canal, topic


def _problema_de(chat: Chat, es_origen: bool) -> tuple[str, str] | None:
    """(etiqueta corta, explicacion) si el chat no va a funcionar en ese rol."""
    if es_origen and chat.protegido:
        return "protegido", "tiene el contenido protegido: Telegram no deja copiar sus archivos"
    if not es_origen and not chat.puede_publicar:
        return "sin permiso para publicar", "no tienes permiso para publicar archivos ahi"
    return None


def _mostrar_chats(chats: list[Chat], es_origen: bool) -> None:
    """Lista numerada de canales y grupos (solo los primeros, si son muchos)."""
    for numero, chat in enumerate(chats[:MAX_CHATS_EN_PANTALLA], 1):
        detalle = f"foro, {contar(len(chat.temas), 'tema')}" if chat.tipo == "foro" else chat.tipo
        problema = _problema_de(chat, es_origen)
        aviso = f"  ⚠ {problema[0]}" if problema else ""
        print(f"  {numero:>3}) {chat.titulo}  [{detalle}]  {chat.id}{aviso}")

    ocultos = len(chats) - MAX_CHATS_EN_PANTALLA
    if ocultos > 0:
        ui.info(f"... y {ocultos} mas: escribe parte del nombre para buscar")


def _aceptar_chat(chat: Chat, es_origen: bool) -> bool:
    """Si el chat elegido no va a funcionar, lo avisa y pregunta si usarlo igual."""
    problema = _problema_de(chat, es_origen)
    if problema is None:
        return True

    ui.aviso(f"{chat.titulo} {problema[1]}.")
    return ui.preguntar_si_no("Elegirlo igual", default=False)


def _elegir_tema(chat: Chat, label: str, es_origen: bool) -> int | None:
    """Elige un tema del foro; 0 es todo el grupo (en origen) o el tema General (en destino)."""
    if not chat.temas:
        # Foro cuyos temas no se pudieron cargar: se puede escribir el ID del tema a mano.
        return _pedir_topic_opcional(f"Tema de {label}", None)

    print(f"    0) {'Todo el grupo (todos los temas)' if es_origen else 'General'}")
    for numero, tema in enumerate(chat.temas, 1):
        cerrado = " (cerrado)" if tema.cerrado else ""
        print(f"  {numero:>3}) {tema.titulo}{cerrado}")

    while True:
        raw = ui.preguntar(f"Tema de {label} [Enter=0]")
        if raw in {"", "0"}:
            return None
        if raw.isdigit() and 1 <= int(raw) <= len(chat.temas):
            return chat.temas[int(raw) - 1].id

        ui.aviso(f"Opcion invalida. Escribe un numero del 0 al {len(chat.temas)}.")


def elegir_chat(
    label: str,
    catalogo: CatalogoDeChats,
    es_origen: bool,
) -> tuple[int | str, int | None]:
    """Elige un canal o grupo de la lista (o escribe su ID) y, si es un foro, su tema."""
    ui.titulo(f"Elige el {label.lower()}")
    visibles = list(catalogo)
    mostrar_lista = True

    while True:
        if mostrar_lista:
            _mostrar_chats(visibles, es_origen)
            mostrar_lista = False

        raw = ui.preguntar(f"{label}: numero, texto para buscar o ID/@usuario [*=ver todos]")

        if raw.isdigit():
            if not 1 <= int(raw) <= len(visibles):
                ui.aviso(f"Numero fuera de la lista (1 a {len(visibles)}).")
                continue

            chat = visibles[int(raw) - 1]
            if not _aceptar_chat(chat, es_origen):
                mostrar_lista = True
                continue
            tema = _elegir_tema(chat, label, es_origen) if chat.tipo == "foro" else None
            return chat.id, tema

        if raw.startswith(("-", "@")):
            # ID o @usuario escrito a mano, como antes (tambien acepta ID,tema).
            canal, topic_inline, error = _parse_canal_y_tema(raw)
            if error:
                ui.aviso(f"Entrada invalida: {error}")
                continue

            chat = catalogo.por_id(canal)
            if chat is not None and not _aceptar_chat(chat, es_origen):
                mostrar_lista = True
                continue
            if chat is not None and topic_inline is None:
                return canal, _elegir_tema(chat, label, es_origen) if chat.tipo == "foro" else None
            return canal, _pedir_topic_opcional(f"Tema de {label}", topic_inline)

        if raw == "*":
            visibles, mostrar_lista = list(catalogo), True
            continue

        if not raw:
            ui.aviso("Escribe un numero de la lista, parte del nombre o un ID.")
            continue

        encontrados = catalogo.buscar(raw)
        if not encontrados:
            ui.aviso(f"Ningun canal o grupo coincide con '{raw}'.")
            continue

        ui.info(f"{len(encontrados)} resultado(s) para '{raw}'")
        visibles, mostrar_lista = encontrados, True


def describir_canal(catalogo: CatalogoDeChats, canal: int | str, topic_id: int | None) -> str:
    """Nombre legible de un canal (y su tema) para los resumenes."""
    chat = catalogo.por_id(canal)
    texto = f"{chat.titulo} ({canal})" if chat else str(canal)
    if topic_id:
        tema = chat.tema(topic_id) if chat else None
        texto += f", tema {tema.titulo}" if tema else f", tema {topic_id}"
    return texto
