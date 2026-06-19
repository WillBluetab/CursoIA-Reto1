"""
Logger con colores para las clases de AI Engineering.

Reutilizamos un único handler compartido para que cada módulo pida su logger
con get_logger("nombre") sin duplicar salidas. Es el mismo patrón que usamos
en el resto del curso: simple, sin dependencias externas y legible en consola.
"""

from __future__ import annotations

import logging
import sys
from typing import Any

###################################
# ---- Códigos ANSI de color ---- #
###################################
_RESET = "\033[0m"

_COLOURS = {
    "DEBUG": "\033[2;37m",  # blanco tenue
    "INFO": "\033[36m",  # cian
    "SUCCESS": "\033[32m",  # verde
    "WARNING": "\033[33m",  # amarillo
    "ERROR": "\033[31m",  # rojo
    "CRITICAL": "\033[1;31m",  # rojo brillante en negrita
}

###########################################################################
# ---- Nivel SUCCESS personalizado (25 — entre INFO=20 y WARNING=30) ---- #
###########################################################################
SUCCESS = 25
logging.addLevelName(SUCCESS, "SUCCESS")


def _success(self: logging.Logger, message: str, *args: Any, **kwargs: Any) -> None:
    if self.isEnabledFor(SUCCESS):
        self._log(SUCCESS, message, args, **kwargs)


logging.Logger.success = _success  # type: ignore[attr-defined]


###################################
# ---- Formateador con color ---- #
###################################
class _ColouredFormatter(logging.Formatter):
    """Añade color ANSI alrededor del nombre del nivel y lo resetea después."""

    _FMT = "%(asctime)s  {colour}%(levelname)-8s{reset}  %(name)s  —  %(message)s"
    _DATE_FMT = "%H:%M:%S"

    def __init__(self, *, use_colour: bool = True) -> None:
        super().__init__(datefmt=self._DATE_FMT)
        self._use_colour = use_colour

    def format(self, record: logging.LogRecord) -> str:
        level = record.levelname
        if self._use_colour:
            colour = _COLOURS.get(level, "")
            reset = _RESET
        else:
            colour = reset = ""

        formatter = logging.Formatter(
            fmt=self._FMT.format(colour=colour, reset=reset),
            datefmt=self._DATE_FMT,
        )
        return formatter.format(record)


#############################
# ---- Factory pública ---- #
#############################
_handler: logging.StreamHandler | None = None  # handler compartido único


def _get_handler(stream=sys.stdout) -> logging.StreamHandler:
    global _handler
    if _handler is None:
        _handler = logging.StreamHandler(stream)
        _handler.setFormatter(_ColouredFormatter(use_colour=stream.isatty()))
    return _handler


def get_logger(name: str, level: int = logging.INFO) -> logging.Logger:
    """Devuelve (o crea) un logger con color identificado por ``name``.

    Cada ``name`` recibe su propia instancia con el handler compartido adjunto
    una sola vez — es seguro llamarla múltiples veces.
    """
    logger = logging.getLogger(name)
    if not logger.handlers:
        logger.addHandler(_get_handler())
        logger.propagate = False
    logger.setLevel(level)
    return logger
