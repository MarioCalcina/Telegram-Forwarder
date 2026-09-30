"""Armar el pedido de reenvio: canales, palabras clave, tipos de archivo y duracion minima."""
from __future__ import annotations

from reenviador.asistente import eleccion_chats, ui
from reenviador.chats.catalogo import CatalogoDeChats
from reenviador.infraestructura.configuracion import MIN_DURACION_VIDEO_MINUTOS, get_channel_mappings
from reenviador.reenvio.modelo import PedidoDeReenvio
from reenviador.seleccion.tipos_de_medio import TIPOS_ARCHIVO_VALIDOS

TIPOS_DISPONIBLES: dict[str, str] = {
    "1": "video",
    "2": "photo",
    "3": "audio",
    "4": "document",
    "5": "voice",
    "6": "gif",
    "7": "sticker",
    "8": "all",
}

TIPOS_LABELS: dict[str, str] = {
    "video": "Videos",
    "photo": "Fotos",
    "audio": "Audios",
    "document": "Documentos",
    "voice": "Notas de voz",
    "gif": "GIFs",
    "sticker": "Stickers",
}

TIPOS_ICONOS: dict[str, str] = {
    "video": "◉",
    "photo": "◌",
    "audio": "◍",
    "document": "◧",
    "voice": "◐",
    "gif": "◎",
    "sticker": "◈",
}

TIPOS_ALIAS: dict[str, str] = {
    "video": "video",
    "videos": "video",
    "foto": "photo",
    "fotos": "photo",
    "photo": "photo",
    "photos": "photo",
    "audio": "audio",
    "audios": "audio",
    "documento": "document",
    "documentos": "document",
    "document": "document",
    "voice": "voice",
    "nota": "voice",
    "nota_de_voz": "voice",
    "voz": "voice",
    "gif": "gif",
    "gifs": "gif",
    "sticker": "sticker",
    "stickers": "sticker",
    "todo": "all",
    "todos": "all",
    "all": "all",
}


def _separar_palabras_clave(raw: str) -> list[str]:
    """Convierte un texto separado por comas en una lista de palabras clave limpia."""
    return [palabra.strip() for palabra in raw.split(",") if palabra.strip()]


def _mostrar_menu_tipos() -> None:
    print("\n  Tipos de archivo a reenviar")
    print("  " + "─" * 32)
    print("  1) ◉ Videos")
    print("  2) ◌ Fotos")
    print("  3) ◍ Audios")
    print("  4) ◧ Documentos")
    print("  5) ◐ Notas de voz")
    print("  6) ◎ GIFs")
    print("  7) ◈ Stickers")
    print("  8) ◍ Todos")


def _pedir_tipos_archivo() -> set[str]:
    """Solicita por consola los tipos de archivo a reenviar."""
    while True:
        _mostrar_menu_tipos()
        raw = ui.preguntar("Selecciona uno o varios (ej: 1,2,4 o videos,gifs) [default 1]")
        if not raw:
            return {"video"}

        tokens = [token.strip().lower() for token in raw.split(",") if token.strip()]
        if not tokens:
            return {"video"}

        tipos: set[str] = set()
        invalidos: list[str] = []

        for token in tokens:
            value = TIPOS_DISPONIBLES.get(token) or TIPOS_ALIAS.get(token)
            if not value:
                invalidos.append(token)
                continue

            if value == "all":
                return set(TIPOS_ARCHIVO_VALIDOS)

            tipos.add(value)

        if invalidos:
            ui.aviso(f"Opciones invalidas: {', '.join(invalidos)}")
            continue

        return tipos or {"video"}


def _pedir_duracion_videos(tipos_archivo: set[str]) -> float | None:
    """Solicita por consola la duracion minima de videos en minutos."""
    if "video" not in tipos_archivo:
        return None

    while True:
        raw = ui.preguntar(
            f"Duracion minima de videos en minutos (0=sin filtro, Enter={MIN_DURACION_VIDEO_MINUTOS})"
        )
        if not raw:
            return float(MIN_DURACION_VIDEO_MINUTOS)

        raw = raw.replace(",", ".")
        try:
            minutos = float(raw)
        except ValueError:
            ui.aviso("Entrada invalida. Usa un numero, por ejemplo 5 o 2.5")
            continue

        if minutos < 0:
            ui.aviso("La duracion minima no puede ser negativa.")
            continue

        return minutos


def _mostrar_resumen(pedido: PedidoDeReenvio, catalogo: CatalogoDeChats) -> None:
    """Muestra un resumen amigable antes de iniciar."""
    ui.titulo("Resumen de Configuracion")

    if pedido.pares:
        origen, destino = pedido.pares[0]
        ui.info(f"Origen:  {eleccion_chats.describir_canal(catalogo, origen, pedido.topic_id_origen)}")
        ui.info(f"Destino: {eleccion_chats.describir_canal(catalogo, destino, pedido.topic_id_destino)}")
    else:
        for origen, destino in get_channel_mappings():
            ui.info(
                f"Desde .env: {eleccion_chats.describir_canal(catalogo, origen, None)}"
                f" -> {eleccion_chats.describir_canal(catalogo, destino, None)}"
            )

    tipos_txt = ", ".join(f"{TIPOS_ICONOS[t]} {TIPOS_LABELS[t]}" for t in sorted(pedido.tipos_archivo))
    ui.info(f"Tipos:   {tipos_txt}")

    if pedido.min_duracion_video_minutos is not None:
        ui.info(f"Video min: {pedido.min_duracion_video_minutos} min")

    if pedido.palabras_clave:
        ui.info(f"Palabras clave: {', '.join(pedido.palabras_clave)}")
    else:
        ui.info("Palabras clave: sin filtro")


def pedir_pedido(catalogo: CatalogoDeChats | None = None) -> PedidoDeReenvio | None:
    """Asistente de consola para armar el pedido; None si el usuario lo cancela."""
    catalogo = catalogo or CatalogoDeChats([])
    ui.titulo("Configuracion de Reenvio")

    if get_channel_mappings():
        usar_env = ui.preguntar_si_no("Quieres usar los canales del archivo .env", default=True)
    else:
        usar_env = False
        ui.info("No hay canales en el .env: escribe el origen y el destino")

    pares: list[tuple[int | str, int | str]] | None = None
    topic_id_origen: int | None = None
    topic_id_destino: int | None = None

    if not usar_env:
        if len(catalogo):
            origen, topic_id_origen = eleccion_chats.elegir_chat("Origen", catalogo, es_origen=True)
            destino, topic_id_destino = eleccion_chats.elegir_chat("Destino", catalogo, es_origen=False)
        else:
            # Sin lista cargada: se escriben los IDs a mano.
            ui.info("Puedes usar formato canal,topic_id (ej: -1001234567890,123)")
            origen, topic_id_origen = eleccion_chats.pedir_canal("Origen")
            destino, topic_id_destino = eleccion_chats.pedir_canal("Destino")
        pares = [(origen, destino)]

    palabras_clave = _separar_palabras_clave(ui.preguntar("Palabras clave (separadas por coma, opcional)"))
    tipos_archivo = _pedir_tipos_archivo()

    pedido = PedidoDeReenvio(
        pares=pares,
        palabras_clave=palabras_clave,
        tipos_archivo=tipos_archivo,
        min_duracion_video_minutos=_pedir_duracion_videos(tipos_archivo),
        topic_id_origen=topic_id_origen,
        topic_id_destino=topic_id_destino,
    )
    _mostrar_resumen(pedido, catalogo)

    if not ui.preguntar_si_no("Iniciar reenvio con esta configuracion", default=True):
        ui.aviso("Operacion cancelada por el usuario.")
        return None

    return pedido
