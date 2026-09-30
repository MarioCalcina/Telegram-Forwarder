"""Utilidades para manipulacion de texto."""
from __future__ import annotations


def truncar_caption_seguro(caption: str | None, max_bytes: int = 1024) -> str:
    """Trunca un caption sin cortar caracteres multibyte."""
    if not caption:
        return ""

    encoded = caption.encode("utf-8")
    if len(encoded) <= max_bytes:
        return caption

    # Truncar por bytes y descodificar ignorando caracteres incompletos.
    truncated = encoded[:max_bytes]
    try:
        return truncated.decode("utf-8", errors="ignore")
    except Exception:
        # Fallback defensivo para escenarios extremos.
        return truncated[: max_bytes - 100].decode("utf-8", errors="ignore")
