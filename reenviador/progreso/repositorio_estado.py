"""Repositorio de estado para multiples pares origen-destino."""
from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Dict

logger = logging.getLogger("telegram_bot")


class ChannelStateRepository:
    """Gestiona el estado de multiples pares origen-destino."""

    def __init__(self, archivo_estado: str = "channel_states.json"):
        self.archivo_path = Path(archivo_estado)
        self.archivo_path.parent.mkdir(parents=True, exist_ok=True)
        self._states: Dict[str, int] = {}
        self._dirty = False
        self._legacy_last_id = 0
        self._load_into_memory()

    def _get_key(self, canal_origen: str, canal_destino: str) -> str:
        """Genera una clave estable para un par origen-destino."""
        return f"{canal_origen}->{canal_destino}"

    def leer_ultimo_id(self, canal_origen: str, canal_destino: str) -> int:
        """Lee el ultimo mensaje procesado para un par origen-destino."""
        key = self._get_key(canal_origen, canal_destino)
        ultimo_id = int(self._states.get(key, 0))

        # Migra automaticamente estado legado de formato "entero unico".
        if ultimo_id == 0 and self._legacy_last_id > 0:
            ultimo_id = self._legacy_last_id
            self._states[key] = ultimo_id
            self._legacy_last_id = 0
            self._dirty = True

        if ultimo_id > 0:
            logger.info(
                "Estado encontrado para %s: reanudando desde mensaje ID %s",
                key,
                ultimo_id,
            )
        else:
            logger.info("No hay estado para %s. Empezando desde el principio.", key)

        return ultimo_id

    def guardar_ultimo_id(
        self,
        canal_origen: str,
        canal_destino: str,
        message_id: int,
        flush: bool = True,
    ) -> None:
        """
        Guarda el ultimo ID procesado.

        Si el nuevo ID es menor o igual al guardado, se ignora para evitar
        retrocesos cuando hay procesamiento concurrente.
        """
        key = self._get_key(canal_origen, canal_destino)
        actual = int(self._states.get(key, 0))
        nuevo_id = int(message_id)

        if nuevo_id <= actual:
            return

        self._states[key] = nuevo_id
        self._dirty = True

        if flush:
            self.flush()

    def flush(self) -> None:
        """Persiste el estado en disco solo si hubo cambios."""
        if not self._dirty:
            return

        self._save_states(self._states)
        self._dirty = False

    def get_all_states(self) -> Dict[str, int]:
        """Retorna una copia de todos los estados cargados en memoria."""
        return dict(self._states)

    def _load_into_memory(self) -> None:
        """Carga estados desde disco a memoria."""
        if not self.archivo_path.exists():
            self.archivo_path.write_text("{}", encoding="utf-8")
            self._states = {}
            return

        try:
            content = self.archivo_path.read_text(encoding="utf-8").strip()
            if not content:
                self._states = {}
                return

            raw_data = json.loads(content)

            if isinstance(raw_data, dict):
                # Sanitiza valores para trabajar solo con enteros validos.
                self._states = {
                    str(key): int(value)
                    for key, value in raw_data.items()
                    if isinstance(value, (int, str)) and str(value).lstrip("-").isdigit()
                }
                return

            if isinstance(raw_data, int):
                self._legacy_last_id = max(0, int(raw_data))
                self._states = {}
                return

            self._states = {}
        except Exception as exc:
            content = self.archivo_path.read_text(encoding="utf-8").strip()
            if content.lstrip("-").isdigit():
                self._legacy_last_id = max(0, int(content))
                self._states = {}
                return

            logger.error("Error al leer estados: %s. Se usara estado vacio.", exc)
            self._states = {}

    def _save_states(self, states: Dict[str, int]) -> None:
        """Guarda todos los estados en archivo JSON."""
        try:
            self.archivo_path.write_text(
                json.dumps(states, indent=2, ensure_ascii=False),
                encoding="utf-8",
            )
        except Exception as exc:
            logger.error("Error al guardar estados: %s", exc)
