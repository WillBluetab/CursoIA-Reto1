"""
Configuración central de la clase: carga de variables de entorno y fábrica del
modelo (LLM).

Separamos esto del resto del código por dos motivos didácticos:
1. Todo lo que depende de claves/credenciales vive en un solo lugar.
2. El modelo se construye de forma perezosa (lazy) con caché, así el grafo se
   puede *importar* sin tener la API key cargada (importante para `langgraph
   dev`, que importa el módulo antes de inyectar el entorno).
"""

from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from pydantic import BaseModel, Field

from logger import get_logger

logger = get_logger("settings")


##################################################
# ---- Carga de variables de entorno (.env) ---- #
##################################################
# Buscamos el .env primero en la carpeta de la clase y, si no existe, en la
# carpeta del curso (un nivel arriba). Así compartimos una sola API key entre
# todas las clases sin duplicarla.

_THIS_FILE = Path(__file__).resolve()
_ENV_CANDIDATES = (
    _THIS_FILE.parent / ".env",  # course1_prompt_engineering/clase1/.env
    _THIS_FILE.parent.parent / ".env",  # course1_prompt_engineering/.env
)


def _load_env() -> None:
    for candidate in _ENV_CANDIDATES:
        if candidate.exists():
            load_dotenv(candidate, override=False)
            logger.info(f"Variables de entorno cargadas desde {candidate}")
            return
    logger.warning("No se encontró ningún .env; se usará el entorno del sistema")


_load_env()


######################################
# ---- Configuración del modelo ---- #
######################################
class LLMConfig(BaseModel):
    """Parámetros con los que construimos el ChatOpenAI.

    Usamos Pydantic para validar rangos (p. ej. temperatura) en lugar de
    confiar en valores sueltos repartidos por el código.
    """

    model: str = Field(default="gpt-4o-mini")
    temperature: float = Field(default=0.0, ge=0.0, le=2.0)


###################################################
# ---- Fábrica del LLM (perezosa + cacheada) ---- #
###################################################
@lru_cache(maxsize=None)
def get_llm(model: str = "gpt-4o-mini", temperature: float = 0.0) -> ChatOpenAI:
    """Devuelve un ChatOpenAI configurado, reutilizando la misma instancia.

    La caché evita reconstruir el cliente en cada nodo del grafo. La clave de
    la caché es la combinación (model, temperature).
    """
    if not os.getenv("OPENAI_API_KEY"):
        # No abortamos al importar: solo avisamos. El error real (si lo hay)
        # surgirá al invocar, con un mensaje claro de OpenAI.
        logger.warning("OPENAI_API_KEY no está definida en el entorno")

    config = LLMConfig(model=model, temperature=temperature)
    logger.info(f"Creando LLM model={config.model} temperature={config.temperature}")
    return ChatOpenAI(model=config.model, temperature=config.temperature)
