"""
Esquemas Pydantic de la clase 5 (ReAct).

En ReAct, los "contratos" de las herramientas se infieren de sus type hints
(ver tools.py). Aquí solo validamos la entrada de la CLI.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

##########################################
# ---- Entrada del grafo (validada) ---- #
##########################################
class ReactConfig(BaseModel):
    perfil: str = Field(description="Descripción de la persona y la situación")
