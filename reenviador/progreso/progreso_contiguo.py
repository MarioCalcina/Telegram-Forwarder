"""Calculo del progreso que es seguro guardar cuando los envios terminan desordenados."""
from __future__ import annotations


class ProgresoContiguo:
    """
    Calcula hasta que mensaje se puede guardar el progreso.

    Con envios concurrentes los mensajes terminan desordenados; solo es seguro
    guardar el ultimo ID tal que todos los anteriores ya terminaron.
    """

    def __init__(self, ids_ordenados: list[int]):
        self._ids = ids_ordenados
        self._terminados: set[int] = set()
        self._indice = 0

    def marcar_terminado(self, message_id: int) -> int | None:
        """Marca un mensaje como terminado; retorna el nuevo ID guardable si avanzo."""
        self._terminados.add(message_id)
        indice_inicial = self._indice
        while self._indice < len(self._ids) and self._ids[self._indice] in self._terminados:
            self._indice += 1

        if self._indice == indice_inicial:
            return None
        return self._ids[self._indice - 1]
