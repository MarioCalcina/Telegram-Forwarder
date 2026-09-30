"""Sesion de Telegram guardada en disco para no iniciar sesion en cada corrida."""
from __future__ import annotations

import logging
import sqlite3
from contextlib import closing
from pathlib import Path

from reenviador.infraestructura.configuracion import api_hash_valido, parse_api_id

logger = logging.getLogger("telegram_bot")

# Tabla propia dentro de la base SQLite del .session. Telethon solo usa y migra sus
# propias tablas, y al cerrar sesion borra el archivo entero, credenciales incluidas.
TABLA_CREDENCIALES = "reenviador_credenciales_api"


class SesionGuardada:
    """
    Archivo ``<nombre>.session`` de Telethon, que recuerda el inicio de sesion.

    Da acceso total a la cuenta. Guarda tambien el API ID y el API hash con los que se
    creo (Telethon los necesita para reabrirla): existen solo mientras hay sesion.
    """

    def __init__(self, nombre: str):
        self.nombre = nombre
        self._archivo_sesion = Path(f"{nombre}.session")
        self._archivo_journal = Path(f"{nombre}.session-journal")

    def existe(self) -> bool:
        """Indica si hay una sesion guardada en disco."""
        return self._archivo_sesion.exists()

    def leer_credenciales(self) -> tuple[int, str] | None:
        """API ID y hash guardados en la sesion; None si no hay sesion o no los tiene."""
        if not self.existe():
            return None

        # Solo lectura: nunca crea el archivo ni lo modifica.
        uri = f"{self._archivo_sesion.resolve().as_uri()}?mode=ro"
        try:
            with closing(sqlite3.connect(uri, uri=True)) as conexion:
                fila = conexion.execute(
                    f"SELECT api_id, api_hash FROM {TABLA_CREDENCIALES} LIMIT 1"
                ).fetchone()
        except sqlite3.Error:
            return None  # sesion de una version anterior (sin la tabla) o archivo danado

        if fila is None:
            return None

        api_id, api_hash = parse_api_id(fila[0]), fila[1]
        if api_id is None or not api_hash_valido(api_hash):
            return None
        return api_id, api_hash

    def guardar_credenciales(self, api_id: int, api_hash: str) -> None:
        """Guarda el API ID y hash dentro de la sesion, para no volver a pedirlos."""
        if not self.existe():
            # sqlite3 crearia un archivo nuevo: sin sesion no hay donde guardarlas.
            logger.warning("No hay sesion guardada donde guardar las credenciales")
            return

        with closing(sqlite3.connect(self._archivo_sesion)) as conexion, conexion:
            conexion.execute(
                f"CREATE TABLE IF NOT EXISTS {TABLA_CREDENCIALES} "
                "(api_id INTEGER NOT NULL, api_hash TEXT NOT NULL)"
            )
            conexion.execute(f"DELETE FROM {TABLA_CREDENCIALES}")
            conexion.execute(
                f"INSERT INTO {TABLA_CREDENCIALES} (api_id, api_hash) VALUES (?, ?)",
                (api_id, api_hash),
            )

    def borrar(self) -> None:
        """Borra la sesion (y con ella las credenciales) de este equipo."""
        for archivo in (self._archivo_sesion, self._archivo_journal):
            try:
                archivo.unlink(missing_ok=True)
            except OSError as exc:
                logger.error("No se pudo borrar %s: %s", archivo, exc)
