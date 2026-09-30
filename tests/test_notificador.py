"""Tests para los mensajes de notificacion."""
from __future__ import annotations

import unittest

from reenviador.notificaciones.notificador import TelegramNotifier


class MensajeDeCompletadoTestCase(unittest.TestCase):
    def test_habla_de_archivos_y_omite_lo_que_no_aplica(self) -> None:
        mensaje = TelegramNotifier._format_completion_message(
            copiados=10, omitidos=2, fallidos=0, canales_procesados=1
        )

        self.assertIn("Archivos copiados: 10", mensaje)
        self.assertIn("Archivos omitidos: 2", mensaje)
        self.assertNotIn("fallidos", mensaje)
        self.assertNotIn("Canales procesados", mensaje)
        self.assertNotIn("Videos", mensaje)

    def test_muestra_fallidos_y_canales_cuando_hay(self) -> None:
        mensaje = TelegramNotifier._format_completion_message(
            copiados=10, omitidos=2, fallidos=3, canales_procesados=2
        )

        self.assertIn("Archivos fallidos: 3", mensaje)
        self.assertIn("Canales procesados: 2", mensaje)


if __name__ == "__main__":
    unittest.main()
