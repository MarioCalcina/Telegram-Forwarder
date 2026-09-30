"""Dead Letter Queue para gestionar videos fallidos."""
from __future__ import annotations

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any

logger = logging.getLogger("telegram_bot")

ARCHIVO_FALLIDOS = "failed_videos.json"


class DeadLetterQueue:
    """Gestiona videos que fallaron despues de todos los reintentos."""

    def __init__(self, archivo: str = ARCHIVO_FALLIDOS) -> None:
        self.archivo_path = Path(archivo)
        self.archivo_path.parent.mkdir(parents=True, exist_ok=True)
        self._ensure_file_exists()

    def _ensure_file_exists(self) -> None:
        """Crea el archivo si no existe."""
        if not self.archivo_path.exists():
            self.archivo_path.write_text("[]", encoding="utf-8")

    def add_failed_video(
        self,
        mensaje_id: int,
        video_id: int,
        canal_origen: str,
        canal_destino: str,
        error: str,
        retry_count: int = 0,
    ) -> None:
        """Agrega un video fallido a la cola (reemplaza la entrada previa del mismo mensaje)."""
        try:
            failed_videos = [
                item
                for item in self._load_failed_videos()
                if not self._es_mismo_mensaje(item, mensaje_id, canal_origen, canal_destino)
            ]
            failed_video = {
                "mensaje_id": mensaje_id,
                "video_id": video_id,
                "canal_origen": str(canal_origen),
                "canal_destino": str(canal_destino),
                "error": str(error),
                "retry_count": retry_count,
                "timestamp": datetime.now().isoformat(),
            }

            failed_videos.append(failed_video)
            self._save_failed_videos(failed_videos)

            logger.warning(
                "Video agregado a Dead Letter Queue: mensaje_id=%s, error=%s",
                mensaje_id,
                error,
            )
        except Exception as exc:
            logger.error("Error al agregar video a DLQ: %s", exc)

    def get_failed_message_ids(self, canal_origen: str, canal_destino: str) -> list[int]:
        """Retorna los IDs de mensajes fallidos de un par origen-destino, en orden ascendente."""
        ids: set[int] = set()
        for item in self._load_failed_videos():
            if not isinstance(item, dict):
                continue
            if item.get("canal_origen") != str(canal_origen) or item.get("canal_destino") != str(canal_destino):
                continue
            try:
                ids.add(int(item["mensaje_id"]))
            except (KeyError, TypeError, ValueError):
                continue
        return sorted(ids)

    def remove(self, mensaje_id: int, canal_origen: str, canal_destino: str) -> None:
        """Quita de la cola un mensaje que ya se envio o que ya no hace falta reintentar."""
        failed_videos = self._load_failed_videos()
        restantes = [
            item
            for item in failed_videos
            if not self._es_mismo_mensaje(item, mensaje_id, canal_origen, canal_destino)
        ]
        if len(restantes) != len(failed_videos):
            self._save_failed_videos(restantes)

    @staticmethod
    def _es_mismo_mensaje(item: Any, mensaje_id: int, canal_origen: str, canal_destino: str) -> bool:
        return (
            isinstance(item, dict)
            and str(item.get("mensaje_id")) == str(mensaje_id)
            and item.get("canal_origen") == str(canal_origen)
            and item.get("canal_destino") == str(canal_destino)
        )

    def _load_failed_videos(self) -> list[dict[str, Any]]:
        """Carga la lista de videos fallidos."""
        try:
            content = self.archivo_path.read_text(encoding="utf-8")
            return json.loads(content) if content.strip() else []
        except Exception as exc:
            logger.error("Error al leer DLQ: %s", exc)
            return []

    def _save_failed_videos(self, failed_videos: list[dict[str, Any]]) -> None:
        """Guarda la lista de videos fallidos."""
        try:
            self.archivo_path.write_text(
                json.dumps(failed_videos, indent=2, ensure_ascii=False),
                encoding="utf-8",
            )
        except Exception as exc:
            logger.error("Error al guardar DLQ: %s", exc)

    def get_failed_videos(self) -> list[dict[str, Any]]:
        """Obtiene la lista de videos fallidos."""
        return self._load_failed_videos()

    def get_count(self) -> int:
        """Obtiene el numero de videos en la cola."""
        return len(self._load_failed_videos())

    def clear(self) -> None:
        """Limpia todos los videos fallidos de la cola."""
        try:
            self.archivo_path.write_text("[]", encoding="utf-8")
            logger.info("Dead Letter Queue limpiada")
        except Exception as exc:
            logger.error("Error al limpiar DLQ: %s", exc)
