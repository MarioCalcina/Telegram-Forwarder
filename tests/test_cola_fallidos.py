"""Tests para la Dead Letter Queue."""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from reenviador.fallidos.cola_fallidos import DeadLetterQueue


class DeadLetterQueueTestCase(unittest.TestCase):
    def setUp(self) -> None:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.dlq = DeadLetterQueue(str(Path(tmp.name) / "failed.json"))

    def test_mismo_mensaje_fallido_dos_veces_no_se_duplica(self) -> None:
        self.dlq.add_failed_video(5, 500, "o", "d", "error 1")
        self.dlq.add_failed_video(5, 500, "o", "d", "error 2")

        fallidos = self.dlq.get_failed_videos()
        self.assertEqual(len(fallidos), 1)
        self.assertEqual(fallidos[0]["error"], "error 2")

    def test_ids_fallidos_filtra_por_par_y_ordena(self) -> None:
        self.dlq.add_failed_video(9, 900, "o", "d", "e")
        self.dlq.add_failed_video(3, 300, "o", "d", "e")
        self.dlq.add_failed_video(4, 400, "otro", "d", "e")

        self.assertEqual(self.dlq.get_failed_message_ids("o", "d"), [3, 9])

    def test_remove_quita_solo_ese_mensaje(self) -> None:
        self.dlq.add_failed_video(3, 300, "o", "d", "e")
        self.dlq.add_failed_video(9, 900, "o", "d", "e")

        self.dlq.remove(3, "o", "d")

        self.assertEqual(self.dlq.get_failed_message_ids("o", "d"), [9])


if __name__ == "__main__":
    unittest.main()
