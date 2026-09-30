"""Filtros que deciden si un mensaje se copia: tipo, duracion, palabras clave y duplicados."""
from __future__ import annotations

from typing import Any

from telethon.tl.types import DocumentAttributeVideo

from reenviador.seleccion.tipos_de_medio import keys_por_tipos


def normalizar_palabras_clave(palabras_clave: list[str] | None) -> set[str]:
    """Normaliza y limpia las palabras clave recibidas por consola."""
    if not palabras_clave:
        return set()

    return {palabra.strip().lower() for palabra in palabras_clave if palabra and palabra.strip()}


def mensaje_contiene_palabra_clave(mensaje: Any, palabras_clave: set[str]) -> bool:
    """Valida si el texto/caption del mensaje contiene al menos una palabra clave."""
    if not palabras_clave:
        return True

    texto = (getattr(mensaje, "text", "") or "").lower()
    if not texto:
        return False

    return any(palabra in texto for palabra in palabras_clave)


def video_duration_seconds(mensaje: Any) -> int:
    """Extrae la duracion de video en segundos desde atributos de Telegram."""
    if not getattr(mensaje, "video", None):
        return 0

    for attr in mensaje.video.attributes:
        if isinstance(attr, DocumentAttributeVideo):
            return int(attr.duration)

    return 0


class SelectorDeMensajes:
    """Aplica todos los filtros de una corrida a los mensajes de un par origen-destino."""

    def __init__(
        self,
        tipos_archivo: set[str],
        min_duracion_segundos: float,
        palabras_clave: set[str],
        medios_existentes: set[str],
        evitar_duplicados: bool,
    ):
        self._tipos_archivo = tipos_archivo
        self._min_duracion_segundos = min_duracion_segundos
        self._palabras_clave = palabras_clave
        self._medios_existentes = medios_existentes
        self._evitar_duplicados = evitar_duplicados
        self._medios_vistos_en_origen: set[str] = set()
        # Mensajes del tipo pedido descartados por duracion, palabras clave o duplicados.
        self.omitidos = 0

    def seleccionar(self, mensaje: Any) -> set[str] | None:
        """Aplica filtros de tipo, duracion, palabras clave y duplicados; retorna las claves a copiar."""
        keys_seleccionadas = keys_por_tipos(mensaje, self._tipos_archivo)
        if not keys_seleccionadas:
            return None

        if "video" in self._tipos_archivo and any(key.startswith("video:") for key in keys_seleccionadas):
            if (
                self._min_duracion_segundos > 0
                and video_duration_seconds(mensaje) < self._min_duracion_segundos
            ):
                self.omitidos += 1
                return None

        if self._palabras_clave and not mensaje_contiene_palabra_clave(mensaje, self._palabras_clave):
            self.omitidos += 1
            return None

        if self._evitar_duplicados:
            if any(
                key in self._medios_existentes or key in self._medios_vistos_en_origen
                for key in keys_seleccionadas
            ):
                self.omitidos += 1
                return None
            self._medios_vistos_en_origen.update(keys_seleccionadas)

        return keys_seleccionadas

    def ya_esta_en_destino(self, mensaje: Any) -> bool:
        """Indica si algun medio del mensaje ya existe en el canal destino."""
        return self._evitar_duplicados and bool(
            keys_por_tipos(mensaje, self._tipos_archivo) & self._medios_existentes
        )
