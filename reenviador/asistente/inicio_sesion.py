"""Inicio de sesion por consola: credenciales, telefono y codigo, sesion guardada y cierre."""
from __future__ import annotations

import asyncio
import logging
import sys

from telethon import utils as telethon_utils
from telethon.errors.rpcerrorlist import ApiIdInvalidError

from reenviador.asistente import ui
from reenviador.infraestructura.cliente_telegram import TelegramClientWrapper
from reenviador.infraestructura.configuracion import (
    TELEGRAM_SESSION_NAME,
    api_hash_valido,
    parse_api_id,
)
from reenviador.sesion.datos_locales import borrar_datos_locales
from reenviador.sesion.sesion_guardada import SesionGuardada

logger = logging.getLogger("telegram_bot")

SESION = SesionGuardada(TELEGRAM_SESSION_NAME)


def _pedir_api_id() -> int:
    """Pide el API ID de my.telegram.org."""
    while True:
        api_id = parse_api_id(ui.preguntar("API ID"))
        if api_id is not None:
            return api_id

        ui.aviso("API ID invalido. Debe ser un numero entero mayor a 0.")


def _pedir_api_hash() -> str:
    """Pide el API hash de my.telegram.org sin mostrarlo."""
    while True:
        raw = ui.preguntar_oculto("API hash")
        if api_hash_valido(raw):
            return raw

        ui.aviso("API hash invalido. Debe tener 32 caracteres hexadecimales (0-9, a-f).")


def _pedir_credenciales() -> tuple[int, str]:
    """Pide las credenciales de la API de Telegram para iniciar sesion."""
    ui.info("Credenciales de API: se obtienen en https://my.telegram.org (API development tools)")
    return _pedir_api_id(), _pedir_api_hash()


def _pedir_telefono() -> str:
    """Pide el telefono de la cuenta con la que se inicia sesion."""
    while True:
        raw = ui.preguntar("Telefono de tu cuenta, con codigo de pais (ej: +51987654321)")
        if telethon_utils.parse_phone(raw):
            return raw

        ui.aviso("Telefono invalido. Usa solo numeros, empezando con + y el codigo de pais.")


def _pedir_codigo() -> str:
    """Pide el codigo de inicio de sesion que envia Telegram."""
    while True:
        raw = ui.preguntar("Codigo que te envio Telegram (app o SMS)")
        if raw:
            return raw

        ui.aviso("Escribe el codigo que recibiste.")


def _pedir_password() -> str:
    """Pide la contrasena de verificacion en dos pasos (solo si la cuenta la tiene)."""
    return ui.preguntar_oculto("Contrasena de verificacion en dos pasos")


async def _login(api_id: int, api_hash: str) -> None:
    """Inicia sesion pidiendo telefono, codigo y 2FA por consola; queda guardada en disco."""
    async with TelegramClientWrapper(
        api_id,
        api_hash,
        SESION.nombre,
        pedir_telefono=_pedir_telefono,
        pedir_codigo=_pedir_codigo,
        pedir_password=_pedir_password,
    ):
        pass


async def _cuenta_de_sesion(api_id: int, api_hash: str) -> str | None:
    """Describe la cuenta de la sesion guardada, o None si ya no es valida."""
    return await TelegramClientWrapper(api_id, api_hash, SESION.nombre).cuenta_autorizada()


def _login_nuevo(api_id: int, api_hash: str) -> None:
    """Inicia sesion de cero; si no se completa, no deja nada en disco."""
    try:
        asyncio.run(_login(api_id, api_hash))
    except BaseException:
        # Credenciales rechazadas, Ctrl+C o error: la sesion a medias se borra.
        SESION.borrar()
        raise

    ui.ok("Sesion iniciada y guardada: la proxima vez no tendras que ingresar ningun dato")


def _elegir_continuar_con(cuenta: str) -> bool:
    """Muestra la cuenta guardada y pregunta si continuar con ella o cerrar sesion."""
    ui.ok(f"Sesion guardada: {cuenta}")
    print("  1) Continuar con esta cuenta")
    print("  2) Cerrar sesion")

    while True:
        opcion = ui.preguntar("Elige una opcion [Enter=1]")
        if opcion in {"", "1"}:
            return True
        if opcion == "2":
            ui.info("Cerrar sesion deja el proyecto limpio: borra la sesion y tu API ID/hash, el")
            ui.info("progreso, los mensajes fallidos, el indice de duplicados y el log de este equipo.")
            if ui.preguntar_si_no("Confirmas cerrar sesion", default=False):
                return False
            continue

        ui.aviso("Opcion invalida. Escribe 1 o 2.")


def _cerrar_sesion(api_id: int, api_hash: str) -> None:
    """Cierra la sesion en Telegram y borra de este equipo todo lo que genero el bot."""
    try:
        cerrada = asyncio.run(TelegramClientWrapper(api_id, api_hash, SESION.nombre).cerrar_sesion())
    except Exception as exc:
        logger.warning("No se pudo cerrar la sesion de Telegram: %s", exc)
        cerrada = False

    SESION.borrar()
    borrar_datos_locales()
    if cerrada:
        ui.ok("Sesion cerrada en Telegram y proyecto limpio")
    else:
        ui.aviso(
            "Se limpio el proyecto, pero Telegram no confirmo el cierre de sesion; "
            "revisala en Telegram > Ajustes > Dispositivos."
        )


def _usar_sesion_guardada(api_id: int, api_hash: str) -> bool:
    """True si se continua con la sesion guardada; False si hay que iniciar una nueva."""
    if not SESION.existe():
        return False

    # Si el API ID / hash estan mal, ApiIdInvalidError sube y la sesion no se toca.
    cuenta = asyncio.run(_cuenta_de_sesion(api_id, api_hash))
    if cuenta is None:
        ui.aviso("La sesion guardada ya no es valida (vencio o se cerro desde otro dispositivo).")
        SESION.borrar()
        return False

    if _elegir_continuar_con(cuenta):
        return True

    _cerrar_sesion(api_id, api_hash)
    if not ui.preguntar_si_no("Iniciar sesion con otra cuenta", default=True):
        sys.exit(0)
    return False


def iniciar_sesion() -> tuple[int, str]:
    """Usa la sesion guardada (con opcion de cerrarla) o inicia una nueva."""
    ui.titulo("Sesion de Telegram")

    # Con una sesion iniciada, el API ID y el hash vienen guardados en ella: no se piden.
    credenciales = SESION.leer_credenciales()
    while True:
        if credenciales is None:
            credenciales = _pedir_credenciales()

        api_id, api_hash = credenciales
        try:
            if not _usar_sesion_guardada(api_id, api_hash):
                _login_nuevo(api_id, api_hash)
        except ApiIdInvalidError:
            ui.aviso("Telegram rechazo el API ID / API hash. Revisalos en my.telegram.org.")
            credenciales = None
            continue

        # Tambien completa las sesiones de versiones anteriores, que no las tenian.
        SESION.guardar_credenciales(api_id, api_hash)
        return api_id, api_hash
