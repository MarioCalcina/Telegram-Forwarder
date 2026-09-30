"""Confirmacion antes de enviar y resultado final de la corrida."""
from __future__ import annotations

from reenviador.asistente import eleccion_chats, ui
from reenviador.chats.catalogo import CatalogoDeChats, contar
from reenviador.fallidos.cola_fallidos import ARCHIVO_FALLIDOS
from reenviador.infraestructura.logs import ARCHIVO_LOG
from reenviador.reenvio.modelo import ConfirmarEnvio, Estadisticas, ParPorCopiar


def confirmador(catalogo: CatalogoDeChats) -> ConfirmarEnvio:
    """Pregunta antes de enviar cada par, mostrando cuantos archivos se van a copiar."""

    def confirmar(par: ParPorCopiar) -> bool:
        ui.titulo("Listo para copiar")
        ui.info(f"Origen:  {eleccion_chats.describir_canal(catalogo, par.canal_origen, par.topic_id_origen)}")
        ui.info(f"Destino: {eleccion_chats.describir_canal(catalogo, par.canal_destino, par.topic_id_destino)}")
        reintentos = f" (incluye {par.reintentos} fallidos de corridas anteriores)" if par.reintentos else ""
        ui.info(f"A copiar: {contar(par.total, 'archivo')}{reintentos}")
        if par.omitidos:
            ui.info(f"Omitidos por filtros o duplicados: {par.omitidos}")
        return ui.preguntar_si_no(f"Copiar {contar(par.total, 'archivo')} ahora", default=True)

    return confirmar


def formatear_duracion(segundos: float) -> str:
    """'45 s', '2 min 49 s', '1 h 5 min'."""
    minutos, segundos = divmod(int(round(segundos)), 60)
    horas, minutos = divmod(minutos, 60)
    if horas:
        return f"{horas} h {minutos} min"
    if minutos:
        return f"{minutos} min {segundos} s"
    return f"{segundos} s"


def mostrar_resultado(stats: Estadisticas, segundos: float, interrumpido: bool = False) -> None:
    """Resumen final de la corrida en pantalla."""
    ui.titulo("Resultado (interrumpido)" if interrumpido else "Resultado")
    ui.ok(f"Copiados: {stats.copiados}")
    ui.info(f"Omitidos por filtros o duplicados: {stats.omitidos}")

    if stats.fallidos:
        ui.aviso(f"Fallidos: {stats.fallidos}. Se reintentan solos en la proxima corrida ({ARCHIVO_FALLIDOS}).")

    if stats.pares_con_error:
        ui.aviso(f"Pares con errores: {stats.pares_con_error}. Revisa {ARCHIVO_LOG}.")

    if stats.pares_cancelados:
        ui.info(f"Pares que elegiste no copiar: {stats.pares_cancelados}")

    ui.info(f"Tiempo: {formatear_duracion(segundos)}")
    if interrumpido:
        ui.info("El progreso quedo guardado: la proxima corrida sigue desde aqui.")
