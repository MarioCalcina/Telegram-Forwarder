"""Configuracion centralizada del logging."""
from __future__ import annotations

import logging
from pathlib import Path

ARCHIVO_LOG = "bot_telegram.log"


def setup_logger(name: str = "telegram_bot", log_file: str = ARCHIVO_LOG) -> logging.Logger:
    """Configura y retorna un logger con formato consistente."""
    logger = logging.getLogger(name)

    # Evitar duplicar handlers si ya esta configurado.
    if logger.handlers:
        return logger

    logger.setLevel(logging.INFO)
    formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")

    log_path = Path(log_file)
    log_path.parent.mkdir(parents=True, exist_ok=True)

    file_handler = logging.FileHandler(log_path, encoding="utf-8")
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    return logger
