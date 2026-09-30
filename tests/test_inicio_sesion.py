"""Tests para el inicio de sesion por consola: credenciales, sesion guardada y cierre."""
from __future__ import annotations

import contextlib
import io
import tempfile
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

from telethon.errors.rpcerrorlist import ApiIdInvalidError

from reenviador.asistente import inicio_sesion, ui
from reenviador.sesion.sesion_guardada import SesionGuardada

HASH_VALIDO = "0123456789abcdef0123456789abcdef"
OTRO_HASH = "fedcba9876543210fedcba9876543210"


class CredencialesConsolaTestCase(unittest.TestCase):
    def setUp(self) -> None:
        # Oculta lo que imprime el asistente para que no ensucie la salida de los tests.
        salida = contextlib.redirect_stdout(io.StringIO())
        salida.__enter__()
        self.addCleanup(salida.__exit__, None, None, None)

    def test_api_id_sin_valor_por_defecto_reintenta_hasta_ser_valido(self) -> None:
        # Enter vacio no usa ningun valor guardado: no existe ninguno.
        with patch("builtins.input", side_effect=["", "abc", "0", "456"]) as entrada:
            self.assertEqual(inicio_sesion._pedir_api_id(), 456)
        self.assertEqual(entrada.call_count, 4)

    def test_api_hash_se_pide_oculto_y_reintenta_hasta_ser_valido(self) -> None:
        with patch.object(ui, "preguntar_oculto", side_effect=["", "corto", HASH_VALIDO]) as oculto:
            self.assertEqual(inicio_sesion._pedir_api_hash(), HASH_VALIDO)
        self.assertEqual(oculto.call_count, 3)

    def test_telefono_invalido_se_vuelve_a_pedir(self) -> None:
        with patch("builtins.input", side_effect=["", "abc", "+51 987 654 321"]) as entrada:
            self.assertEqual(inicio_sesion._pedir_telefono(), "+51 987 654 321")
        self.assertEqual(entrada.call_count, 3)


class SesionGuardadaFlujoTestCase(unittest.TestCase):
    """El login se recuerda entre corridas (con el API ID/hash) y se puede cerrar."""

    def setUp(self) -> None:
        salida = contextlib.redirect_stdout(io.StringIO())
        salida.__enter__()
        self.addCleanup(salida.__exit__, None, None, None)

        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.carpeta = Path(tmp.name)
        self.sesion = SesionGuardada(str(self.carpeta / "sesion"))

        self.login = AsyncMock(side_effect=self._login_exitoso)
        self.cuenta = AsyncMock(return_value="Mario (@mario)")
        self.pedir_credenciales = MagicMock(return_value=(1, HASH_VALIDO))
        self.cliente = MagicMock()
        self.cliente.return_value.cerrar_sesion = AsyncMock(return_value=True)
        # Mock obligatorio: la version real borraria el progreso y el log reales del proyecto.
        self.borrar_datos_locales = MagicMock()
        for nombre, valor in {
            "SESION": self.sesion,
            "_login": self.login,
            "_cuenta_de_sesion": self.cuenta,
            "_pedir_credenciales": self.pedir_credenciales,
            "TelegramClientWrapper": self.cliente,
            "borrar_datos_locales": self.borrar_datos_locales,
        }.items():
            patcher = patch.object(inicio_sesion, nombre, valor)
            patcher.start()
            self.addCleanup(patcher.stop)

    async def _login_exitoso(self, *_: object) -> None:
        """Como Telethon: al iniciar sesion queda el archivo .session."""
        Path(f"{self.sesion.nombre}.session").touch()

    def _sesion_en_disco(self, con_credenciales: bool = True) -> None:
        Path(f"{self.sesion.nombre}.session").touch()
        if con_credenciales:
            self.sesion.guardar_credenciales(7, OTRO_HASH)

    def test_primera_vez_pide_credenciales_y_las_guarda_en_la_sesion(self) -> None:
        self.assertEqual(inicio_sesion.iniciar_sesion(), (1, HASH_VALIDO))
        self.login.assert_awaited_once_with(1, HASH_VALIDO)
        self.assertEqual(self.sesion.leer_credenciales(), (1, HASH_VALIDO))
        # Sin archivos aparte: todo queda dentro del .session.
        self.assertEqual([archivo.name for archivo in self.carpeta.iterdir()], ["sesion.session"])

    def test_credenciales_rechazadas_se_vuelven_a_pedir(self) -> None:
        self.pedir_credenciales.side_effect = [(1, HASH_VALIDO), (2, OTRO_HASH)]
        respuestas = iter([ApiIdInvalidError(request=None), None])

        async def login(*args: object) -> None:
            error = next(respuestas)
            if error:
                raise error
            await self._login_exitoso()

        self.login.side_effect = login

        self.assertEqual(inicio_sesion.iniciar_sesion(), (2, OTRO_HASH))
        self.assertEqual(self.sesion.leer_credenciales(), (2, OTRO_HASH))

    def test_login_interrumpido_no_deja_sesion_a_medias(self) -> None:
        async def login_a_medias(*_: object) -> None:
            Path(f"{self.sesion.nombre}.session").touch()
            raise KeyboardInterrupt

        self.login.side_effect = login_a_medias

        with self.assertRaises(KeyboardInterrupt):
            inicio_sesion.iniciar_sesion()
        self.assertFalse(self.sesion.existe())

    def test_con_sesion_iniciada_no_pide_ningun_dato(self) -> None:
        self._sesion_en_disco()

        with patch("builtins.input", side_effect=[""]):  # Enter: continuar con la cuenta
            self.assertEqual(inicio_sesion.iniciar_sesion(), (7, OTRO_HASH))
        self.pedir_credenciales.assert_not_called()
        self.login.assert_not_awaited()

    def test_sesion_de_version_anterior_pide_credenciales_una_sola_vez(self) -> None:
        self._sesion_en_disco(con_credenciales=False)

        for _ in range(2):
            with patch("builtins.input", side_effect=[""]):
                self.assertEqual(inicio_sesion.iniciar_sesion(), (1, HASH_VALIDO))
        self.pedir_credenciales.assert_called_once()

    def test_api_mal_escrita_no_borra_una_sesion_valida(self) -> None:
        self._sesion_en_disco(con_credenciales=False)
        self.pedir_credenciales.side_effect = [(1, HASH_VALIDO), (2, OTRO_HASH)]
        self.cuenta.side_effect = [ApiIdInvalidError(request=None), "Mario (@mario)"]

        with patch("builtins.input", side_effect=[""]):
            self.assertEqual(inicio_sesion.iniciar_sesion(), (2, OTRO_HASH))
        self.assertTrue(self.sesion.existe())
        self.assertEqual(self.sesion.leer_credenciales(), (2, OTRO_HASH))

    def test_credenciales_guardadas_rechazadas_se_vuelven_a_pedir(self) -> None:
        self._sesion_en_disco()
        self.cuenta.side_effect = [ApiIdInvalidError(request=None), "Mario (@mario)"]

        with patch("builtins.input", side_effect=[""]):
            self.assertEqual(inicio_sesion.iniciar_sesion(), (1, HASH_VALIDO))
        self.pedir_credenciales.assert_called_once()
        self.assertEqual(self.sesion.leer_credenciales(), (1, HASH_VALIDO))

    def test_cerrar_sesion_borra_las_credenciales_y_deja_el_proyecto_limpio(self) -> None:
        self._sesion_en_disco()

        with patch("builtins.input", side_effect=["2", "s", "n"]), self.assertRaises(SystemExit):
            inicio_sesion.iniciar_sesion()

        self.cliente.return_value.cerrar_sesion.assert_awaited_once()
        self.assertFalse(self.sesion.existe())
        self.assertIsNone(self.sesion.leer_credenciales())
        self.assertEqual(list(self.carpeta.iterdir()), [])
        self.borrar_datos_locales.assert_called_once()

    def test_cerrar_sesion_pide_confirmacion(self) -> None:
        self._sesion_en_disco()

        # Elige cerrar, no confirma, y vuelve al menu para continuar.
        with patch("builtins.input", side_effect=["2", "n", ""]):
            self.assertEqual(inicio_sesion.iniciar_sesion(), (7, OTRO_HASH))
        self.cliente.return_value.cerrar_sesion.assert_not_called()
        self.borrar_datos_locales.assert_not_called()
        self.assertTrue(self.sesion.existe())

    def test_cerrar_sesion_y_entrar_con_otra_cuenta(self) -> None:
        self._sesion_en_disco()

        with patch("builtins.input", side_effect=["2", "s", "s"]):
            self.assertEqual(inicio_sesion.iniciar_sesion(), (7, OTRO_HASH))
        self.login.assert_awaited_once_with(7, OTRO_HASH)
        self.assertEqual(self.sesion.leer_credenciales(), (7, OTRO_HASH))

    def test_sesion_vencida_se_borra_pero_conserva_el_progreso(self) -> None:
        self._sesion_en_disco()
        self.cuenta.return_value = None

        self.assertEqual(inicio_sesion.iniciar_sesion(), (7, OTRO_HASH))
        self.login.assert_awaited_once()
        self.borrar_datos_locales.assert_not_called()
        self.assertEqual(self.sesion.leer_credenciales(), (7, OTRO_HASH))


if __name__ == "__main__":
    unittest.main()
