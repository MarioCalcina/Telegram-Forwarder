"""Tests para utilidades de texto."""
from __future__ import annotations

import unittest

from reenviador.reenvio.caption import truncar_caption_seguro


class TextUtilsTestCase(unittest.TestCase):
    def test_truncar_caption_seguro_retorna_vacio_si_none(self) -> None:
        self.assertEqual(truncar_caption_seguro(None), "")

    def test_truncar_caption_seguro_no_trunca_si_no_supera_maximo(self) -> None:
        self.assertEqual(truncar_caption_seguro("hola", max_bytes=10), "hola")

    def test_truncar_caption_seguro_respeta_limite_de_bytes(self) -> None:
        caption = "\u20ac" * 50
        truncado = truncar_caption_seguro(caption, max_bytes=32)

        self.assertTrue(truncado)
        self.assertLessEqual(len(truncado.encode("utf-8")), 32)


if __name__ == "__main__":
    unittest.main()
