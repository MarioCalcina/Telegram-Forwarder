"""Indice guardado de los medios que ya hay en cada canal destino."""
from __future__ import annotations

import json
import logging
from pathlib import Path

logger = logging.getLogger("telegram_bot")

ARCHIVO_INDICE_DESTINOS = "indice_destinos.json"


class IndiceDeDestinos:
    """
    Recuerda, por canal destino, sus medios y hasta que mensaje se reviso.

    Asi cada corrida solo revisa los mensajes nuevos del destino en vez de
    recorrerlo entero. Para forzar una revision completa basta con borrar el archivo.
    """

    def __init__(self, archivo: str = ARCHIVO_INDICE_DESTINOS):
        self._archivo = Path(archivo)
        self._ultimo_id: dict[str, int] = {}
        self._medios: dict[str, set[str]] = {}
        self._cargar()

    def ultimo_id(self, canal: str) -> int:
        """Ultimo mensaje revisado del canal; 0 si nunca se reviso."""
        return self._ultimo_id.get(canal, 0)

    def medios(self, canal: str) -> set[str]:
        """Medios conocidos del canal. Siempre es el mismo set: lo que se agregue queda en el indice."""
        return self._medios.setdefault(canal, set())

    def avanzar(self, canal: str, ultimo_id: int) -> None:
        """Marca el canal como revisado hasta ese mensaje (nunca retrocede)."""
        self._ultimo_id[canal] = max(self.ultimo_id(canal), ultimo_id)

    def guardar(self) -> None:
        datos = {
            canal: {"ultimo_id": self.ultimo_id(canal), "medios": sorted(self.medios(canal))}
            for canal in sorted(set(self._ultimo_id) | set(self._medios))
        }
        try:
            self._archivo.write_text(json.dumps(datos, ensure_ascii=False), encoding="utf-8")
        except OSError as exc:
            logger.error("No se pudo guardar el indice de destinos: %s", exc)

    def _cargar(self) -> None:
        if not self._archivo.exists():
            return

        try:
            datos = json.loads(self._archivo.read_text(encoding="utf-8"))
            for canal, entrada in datos.items():
                self._ultimo_id[str(canal)] = int(entrada["ultimo_id"])
                self._medios[str(canal)] = {str(medio) for medio in entrada["medios"]}
        except (OSError, ValueError, TypeError, KeyError, AttributeError) as exc:
            # Indice danado: se descarta y el destino se revisa completo, como la primera vez.
            logger.warning("Indice de destinos ilegible (%s); se revisaran los destinos completos.", exc)
            self._ultimo_id.clear()
            self._medios.clear()
