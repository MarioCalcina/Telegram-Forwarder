"""Tests para la clasificacion de medios por tipo."""
from __future__ import annotations

import unittest

from telegram_fakes import mensaje_gif, mensaje_sticker_video, mensaje_video

from reenviador.seleccion.tipos_de_medio import get_media_keys_for_message, keys_por_tipos


class MediaKeysTestCase(unittest.TestCase):
    def test_video_normal_es_video(self) -> None:
        keys = get_media_keys_for_message(mensaje_video(1))
        self.assertEqual(keys, {"video:100"})

    def test_gif_no_cuenta_como_video(self) -> None:
        keys = get_media_keys_for_message(mensaje_gif(1))
        self.assertEqual(keys, {"gif:100"})

    def test_sticker_animado_no_cuenta_como_video(self) -> None:
        keys = get_media_keys_for_message(mensaje_sticker_video(1))
        self.assertEqual(keys, {"sticker:100"})

    def test_solo_videos_no_selecciona_gifs(self) -> None:
        self.assertEqual(keys_por_tipos(mensaje_gif(1), {"video"}), set())

    def test_videos_y_gifs_no_aplica_filtro_de_duracion_al_gif(self) -> None:
        # El filtro de duracion solo se aplica si hay una clave "video:".
        self.assertEqual(keys_por_tipos(mensaje_gif(1), {"video", "gif"}), {"gif:100"})


if __name__ == "__main__":
    unittest.main()
