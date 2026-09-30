"""Configuracion del bot de Telegram basada en variables de entorno."""
from __future__ import annotations

import json
import os
import re
import sys
from typing import Any

from dotenv import load_dotenv

load_dotenv()


def str_to_bool(value: Any) -> bool:
    """Convierte diferentes representaciones a booleano."""
    if isinstance(value, bool):
        return value

    if value is None:
        return False

    return str(value).strip().lower() in {"true", "1", "yes", "si", "s"}


def _parse_int(value: Any, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _parse_float(value: Any, default: float) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _parse_channel(value: Any) -> int | str | None:
    if value is None:
        return None

    text = str(value).strip()
    if not text:
        return None

    if text.lstrip("-").isdigit():
        return int(text)

    return text


def parse_channel_input(value: Any) -> int | str | None:
    """Parser publico para IDs/usernames ingresados por consola."""
    return _parse_channel(value)


def parse_api_id(value: Any) -> int | None:
    """Retorna el API ID si es un entero mayor a 0; si no, None."""
    api_id = _parse_int(value, 0)
    return api_id if api_id > 0 else None


def api_hash_valido(value: Any) -> bool:
    """El API hash de my.telegram.org son 32 caracteres hexadecimales."""
    return isinstance(value, str) and re.fullmatch(r"[0-9a-fA-F]{32}", value) is not None


# El API ID y el API hash no se leen del .env ni se guardan: se piden por consola.
TELEGRAM_SESSION_NAME = os.getenv("TELEGRAM_SESSION_NAME", "mi_sesion_telegram")

CHANNEL_ORIGEN_ID = _parse_channel(os.getenv("CHANNEL_ORIGEN_ID"))
CHANNEL_DESTINO_ID = _parse_channel(os.getenv("CHANNEL_DESTINO_ID"))
CHANNEL_MAPPINGS = os.getenv("CHANNEL_MAPPINGS", "").strip()

ARCHIVO_ESTADO = os.getenv("ARCHIVO_ESTADO", "channel_states.json")
MIN_DURACION_VIDEO_MINUTOS = max(0, _parse_int(os.getenv("MIN_DURACION_VIDEO_MINUTOS"), 5))
EVITAR_DUPLICADOS = str_to_bool(os.getenv("EVITAR_DUPLICADOS", "True"))
DELAY_ENTRE_MENSAJES = max(0.0, _parse_float(os.getenv("DELAY_ENTRE_MENSAJES"), 1.5))

MAX_RETRIES = max(0, _parse_int(os.getenv("MAX_RETRIES"), 3))
RETRY_BASE_DELAY = max(0.0, _parse_float(os.getenv("RETRY_BASE_DELAY"), 1.0))
MAX_CONCURRENT_VIDEOS = max(1, _parse_int(os.getenv("MAX_CONCURRENT_VIDEOS"), 1))

ENABLE_NOTIFICATIONS = str_to_bool(os.getenv("ENABLE_NOTIFICATIONS", "False"))
NOTIFICATION_CHAT_ID = _parse_channel(os.getenv("NOTIFICATION_CHAT_ID"))
if isinstance(NOTIFICATION_CHAT_ID, str) and NOTIFICATION_CHAT_ID.lstrip("-").isdigit():
    NOTIFICATION_CHAT_ID = int(NOTIFICATION_CHAT_ID)
elif isinstance(NOTIFICATION_CHAT_ID, str):
    NOTIFICATION_CHAT_ID = None


def _print_validation_error(message: str) -> None:
    print(f"ERROR: {message}")


def validar_configuracion(
    channel_mappings_override: list[tuple[int | str, int | str]] | None = None,
) -> None:
    """Valida que haya al menos un par origen-destino configurado."""
    mappings = channel_mappings_override or get_channel_mappings()
    if not mappings:
        _print_validation_error(
            "Debes configurar CHANNEL_ORIGEN_ID + CHANNEL_DESTINO_ID, o un CHANNEL_MAPPINGS valido"
        )
        print("\nRevisa tu archivo .env (puedes basarte en .env.example).")
        sys.exit(1)


def get_channel_mappings() -> list[tuple[int | str, int | str]]:
    """Retorna la lista de pares (origen, destino)."""
    if CHANNEL_MAPPINGS:
        try:
            mappings_data = json.loads(CHANNEL_MAPPINGS)
            if not isinstance(mappings_data, list):
                raise ValueError("CHANNEL_MAPPINGS debe ser una lista JSON")

            result: list[tuple[int | str, int | str]] = []
            for mapping in mappings_data:
                if not isinstance(mapping, dict):
                    continue

                origen = _parse_channel(mapping.get("origen"))
                destino = _parse_channel(mapping.get("destino"))

                if origen is None or destino is None:
                    continue

                result.append((origen, destino))

            if result:
                return result
        except (json.JSONDecodeError, ValueError, TypeError):
            pass

    if CHANNEL_ORIGEN_ID is not None and CHANNEL_DESTINO_ID is not None:
        return [(CHANNEL_ORIGEN_ID, CHANNEL_DESTINO_ID)]

    return []
