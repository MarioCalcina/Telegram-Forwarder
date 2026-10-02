"""Tests para agrupar los mensajes de un album en lotes."""
from __future__ import annotations

import unittest
from types import SimpleNamespace

from reenviador.reenvio.albumes import MAX_ARCHIVOS_POR_ALBUM, agrupar_en_lotes


def _items(*grupos: int | None) -> list[tuple[SimpleNamespace, set[str]]]:
    """Un mensaje por grupo dado (None = no es parte de un album), con IDs 1, 2, 3..."""
    return [(SimpleNamespace(id=i, grouped_id=grupo), set()) for i, grupo in enumerate(grupos, 1)]


def _ids(lotes: list) -> list[list[int]]:
    return [[mensaje.id for mensaje, _ in lote] for lote in lotes]


class AgruparEnLotesTestCase(unittest.TestCase):
    def test_sin_albumes_cada_mensaje_va_solo(self) -> None:
        self.assertEqual(_ids(agrupar_en_lotes(_items(None, None, None))), [[1], [2], [3]])

    def test_albumes_seguidos_se_juntan_sin_mezclarse(self) -> None:
        lotes = agrupar_en_lotes(_items(None, 7, 7, 8, 8, None))

        self.assertEqual(_ids(lotes), [[1], [2, 3], [4, 5], [6]])

    def test_album_de_mas_de_10_se_parte(self) -> None:
        lotes = agrupar_en_lotes(_items(*[7] * (MAX_ARCHIVOS_POR_ALBUM + 2)))

        self.assertEqual([len(lote) for lote in lotes], [MAX_ARCHIVOS_POR_ALBUM, 2])


if __name__ == "__main__":
    unittest.main()
