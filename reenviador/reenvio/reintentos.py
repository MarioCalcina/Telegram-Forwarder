"""Sistema de reintentos con backoff exponencial."""
from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable
from typing import Any, TypeVar

logger = logging.getLogger("telegram_bot")

T = TypeVar("T")


class RetryManager:
    """Gestiona reintentos de operaciones con backoff exponencial."""

    def __init__(self, max_retries: int = 3, base_delay: float = 1.0):
        self.max_retries = max_retries
        self.base_delay = base_delay

    async def execute_with_retry(
        self,
        func: Callable[..., Awaitable[T]],
        *args: Any,
        error_types: tuple[type[BaseException], ...] = (Exception,),
        **kwargs: Any,
    ) -> T:
        """Ejecuta una funcion async con reintentos automaticos."""
        last_exception: BaseException | None = None

        for attempt in range(self.max_retries + 1):
            try:
                result = await func(*args, **kwargs)

                if attempt > 0:
                    logger.info(
                        "Operacion exitosa en intento %s/%s",
                        attempt + 1,
                        self.max_retries + 1,
                    )

                return result
            except error_types as exc:
                last_exception = exc

                if attempt < self.max_retries:
                    delay = self.base_delay * (2**attempt)
                    logger.warning(
                        "Intento %s/%s fallo: %s. Reintentando en %ss...",
                        attempt + 1,
                        self.max_retries + 1,
                        exc,
                        delay,
                    )
                    await asyncio.sleep(delay)
                else:
                    logger.error(
                        "Todos los reintentos agotados (%s intentos). Ultimo error: %s",
                        self.max_retries + 1,
                        exc,
                    )

        if last_exception is None:
            raise RuntimeError("No se ejecuto ningun intento")
        raise last_exception
