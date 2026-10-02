"""Archivos que el bot genera en el proyecto, para dejarlo limpio al cerrar sesion."""
from __future__ import annotations

import logging
from pathlib import Path

from reenviador.fallidos.cola_fallidos import ARCHIVO_FALLIDOS
from reenviador.infraestructura.configuracion import ARCHIVO_ESTADO
from reenviador.infraestructura.logs import ARCHIVO_LOG
from reenviador.seleccion.indice_destinos import ARCHIVO_INDICE_DESTINOS

logger = logging.getLogger("telegram_bot")

# La sesion no esta aqui: la borra SesionGuardada.
ARCHIVOS_GENERADOS = (
    Path(ARCHIVO_ESTADO),
    Path(ARCHIVO_FALLIDOS),
    Path(ARCHIVO_INDICE_DESTINOS),
    Path(ARCHIVO_LOG),
)


def borrar_datos_locales() -> None:
    """Borra el progreso, los mensajes fallidos, el indice de destinos y el log de este equipo."""
    for archivo in ARCHIVOS_GENERADOS:
        try:
            archivo.unlink(missing_ok=True)
        except OSError as exc:
            logger.error("No se pudo borrar %s: %s", archivo, exc)
