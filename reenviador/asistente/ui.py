"""Primitivas de la consola: titulos, mensajes y preguntas."""
from __future__ import annotations

import sys
from getpass import getpass

DIVISOR = "─" * 56


def titulo(texto: str) -> None:
    print(f"\n{DIVISOR}")
    print(f"  ◼ {texto}")
    print(DIVISOR)


def info(texto: str) -> None:
    print(f"  ◦ {texto}")


def ok(texto: str) -> None:
    print(f"  ✓ {texto}")


def aviso(texto: str) -> None:
    print(f"  ⚠ {texto}")


def preguntar(label: str) -> str:
    return input(f"  › {label}: ").strip()


def preguntar_oculto(label: str) -> str:
    """Como preguntar, pero sin mostrar lo que se escribe (para secretos)."""
    if not sys.stdin.isatty():
        # En Windows getpass lee directo de la consola y se cuelga si no hay una
        # (Git Bash, ventanas de "Run" de algunos IDE, entrada por pipe).
        return preguntar(f"{label} (se vera al escribir)")
    return getpass(f"  › {label} (oculto): ").strip()


def preguntar_si_no(pregunta: str, default: bool = True) -> bool:
    """Pregunta de confirmacion con reintento en caso de input invalido."""
    sufijo = "[S/n]" if default else "[s/N]"

    while True:
        raw = preguntar(f"{pregunta} {sufijo}").lower()
        if not raw:
            return default

        if raw in {"s", "si", "y", "yes"}:
            return True

        if raw in {"n", "no"}:
            return False

        aviso("Entrada invalida. Escribe 's' o 'n'.")
