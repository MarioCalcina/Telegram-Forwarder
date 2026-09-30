"""Tests para helpers de configuracion."""
from __future__ import annotations

import unittest

from reenviador.infraestructura.configuracion import (
    api_hash_valido,
    parse_api_id,
    parse_channel_input,
    str_to_bool,
)


class ConfigHelpersTestCase(unittest.TestCase):
    def test_str_to_bool_true_values(self) -> None:
        for value in ("true", "1", "yes", "si", "s", True):
            with self.subTest(value=value):
                self.assertTrue(str_to_bool(value))

    def test_str_to_bool_false_values(self) -> None:
        for value in ("false", "0", "no", "", None, False):
            with self.subTest(value=value):
                self.assertFalse(str_to_bool(value))

    def test_parse_channel_input_numeric_id(self) -> None:
        self.assertEqual(parse_channel_input("-100123"), -100123)

    def test_parse_channel_input_username(self) -> None:
        self.assertEqual(parse_channel_input("@mi_canal"), "@mi_canal")

    def test_parse_channel_input_empty_returns_none(self) -> None:
        self.assertIsNone(parse_channel_input("   "))

    def test_parse_api_id_valido(self) -> None:
        self.assertEqual(parse_api_id("12345678"), 12345678)

    def test_parse_api_id_invalido_retorna_none(self) -> None:
        for value in ("", "abc", "0", "-5", "12.5", None):
            with self.subTest(value=value):
                self.assertIsNone(parse_api_id(value))

    def test_api_hash_valido(self) -> None:
        self.assertTrue(api_hash_valido("0123456789abcdef0123456789ABCDEF"))

    def test_api_hash_invalido(self) -> None:
        for value in ("", "your_api_hash_here", "0123456789abcdef", "g" * 32, None):
            with self.subTest(value=value):
                self.assertFalse(api_hash_valido(value))


if __name__ == "__main__":
    unittest.main()
