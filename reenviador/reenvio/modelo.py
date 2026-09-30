"""Datos que entran y salen del caso de uso de reenvio."""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field


@dataclass(frozen=True)
class PedidoDeReenvio:
    """Que copiar en una corrida (lo arma el asistente de consola)."""

    pares: list[tuple[int | str, int | str]] | None = None  # None: los del .env
    palabras_clave: list[str] = field(default_factory=list)
    tipos_archivo: set[str] = field(default_factory=lambda: {"video"})
    min_duracion_video_minutos: float | None = None  # None: la del .env
    topic_id_origen: int | None = None  # solo aplica con un unico par
    topic_id_destino: int | None = None


@dataclass(frozen=True)
class ParPorCopiar:
    """Lo que se va a copiar en un par origen-destino, para confirmarlo antes de enviar."""

    canal_origen: int | str
    topic_id_origen: int | None
    canal_destino: int | str
    topic_id_destino: int | None
    total: int
    reintentos: int  # incluidos en el total: fallidos de corridas anteriores
    omitidos: int


ConfirmarEnvio = Callable[[ParPorCopiar], bool]


@dataclass
class Estadisticas:
    """Contadores de una corrida; se llenan mientras avanza, asi sirven aunque se interrumpa."""

    copiados: int = 0
    omitidos: int = 0
    fallidos: int = 0
    pares_cancelados: int = 0
    pares_con_error: int = 0
    canales_procesados: int = 0
