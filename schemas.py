"""
Esquemas Pydantic de la clase 5 (ReAct).

En ReAct, los "contratos" de las herramientas se infieren de sus type hints
(ver tools.py). Aquí solo validamos la entrada de la CLI.
"""

from __future__ import annotations
from enum import Enum
from pydantic import BaseModel, Field
from typing import Annotated
from langgraph.graph import MessagesState

#Variables de apoyo

class TipoCredito(str, Enum):
    CREDITO_COMERCIAL = "credito_comercial"
    PRESTAMO_OPERATIVO = "prestamo_operativo"
    LINEA_REVOLVENTE = "linea_revolvente"

class BuroResponse(BaseModel):
    score: int = Field(
        description="Puntaje de credito del cliente. Rango de 300 (pesimo) a 850 (excelente)",
        ge=300,
        le=850
    )
    impagos_historicos: int = Field(
        description="Cantidad de creditos o pagos vencidos o no liquidados en el historial comercial",
        ge=0
    )
    detalles: str = Field(
        description="Resumen o comentarios generales sobre el comportamiento de pago historico"
    )

class EvaluacionRiesgo(BaseModel):
    nivel_riesgo: str = Field(
        description="Nivel de riesgo del cliente (ej. bajo, medio, alto)",
        pattern="^(bajo|medio|alto)$"
    )
    aprobado_para_oferta: bool = Field(
        description="Indica si el cliente califica para recibir una propuesta de credito segun las politicas de riesgo"
    )
    justificacion_riesgo: str = Field(
        description="Explicacion detallada de los factores de riesgo considerados (buro, deudas, etc.)"
    )

class TasaResponse(BaseModel):
    tasa: float = Field(
        description="Tasa de interes anual simple, en formato porcentual (ej. 14.5 para 14.5%)",
        ge=10,
        le=50
    )
    plazo_meses: int = Field(
        description="Plazo sugerido para el financiamiento en meses (ej. 12, 24, 36)",
        ge=1
    )
    rango_tasa: str = Field(
        description="Rango de tasas asociado a la decision crediticia, o una descripcion cualitativa del nivel de tasa (ej. Competitiva, Alta, Preferencial)"
    )
    explicacion: str = Field(
        description="Tasa determinada con base al perfil de riesgo"
    )

class IntentionResponse(BaseModel):
    intencion: TipoCredito = Field(
        description="Clasificacion del tipo de credito solicitado a partir de los datos ingresados"
    )
    justificacion: str = Field(
        description="Explicacion logica de por que se selecciono este tipo de credito"
    )
    tono: str = Field(
        description="Estilo de redaccion y directrices de tono recomendadas para la propuesta (ej. conservador, flexible, corporativo)"
    )


class EvaluacionPropuesta(BaseModel):
    coherencia_financiera: float = Field(
        description="Calificacion del 0 al 10 de si las condiciones financieras sugeridas son acordes al perfil del cliente",
        ge=0.0,
        le=10.0
    )
    claridad_y_estructura: float = Field(
        description="Calificacion del 0 al 10 de si el mensaje es claro, profesional y estructurado",
        ge=0.0,
        le=10.0
    )
    adecuacion_tono: float = Field(
        description="Calificacion del 0 al 10 de si el tono es el adecuado para la intencion (comercial, operativo, revolvente)",
        ge=0.0,
        le=10.0
    )
    gestion_riesgo: float = Field(
        description="Calificacion del 0 al 10 de si la propuesta mitiga el riesgo del cliente de forma segura",
        ge=0.0,
        le=10.0
    )
    promedio: float = Field(
        description="Promedio matematico de los 4 criterios de calificacion",
        ge=0.0,
        le=10.0
    )
    aprobado: bool = Field(
        description="True si el promedio cumple con el umbral minimo establecido, False en caso contrario"
    )
    feedback: str = Field(
        description="Retroalimentacion constructiva con sugerencias especificas de mejora en caso de no ser aprobado"
    )


def acumular_historial(left: list[dict] | None, right: list[dict] | dict | None) -> list[dict]:
    """Acumula las evaluaciones de cada iteracion en una lista persistente."""
    if left is None:
        left = []
    if right is None:
        return left
    if isinstance(right, list):
        return left + right
    return left + [right]


class State(MessagesState):
    # Datos de la solicitud
    intencion: TipoCredito | None
    tono: str | None
    
    # Datos del cliente obtenidos por las herramientas
    score_buro: int | None
    impagos_historicos: int | None
    ratio_endeudamiento: float | None
    cuota_maxima: float | None
    
    # Datos de la oferta de credito
    tasa_anual: float | None
    plazo_meses: int | None
    
    # Evaluacion de riesgo del cliente
    nivel_riesgo: str | None
    aprobado_riesgo: bool | None
    
    # Control del bucle e historial (trazabilidad)
    iteraciones: int
    borrador_propuesta: str | None
    
    # El uso de Annotated con acumular_historial registra el Reducer en LangGraph
    historial_iteraciones: Annotated[list[dict], acumular_historial]


##########################################
# ---- Entrada del grafo (validada) ---- #
##########################################
class ReactConfig(BaseModel):
    perfil: str = Field(description="Ingresa el RFC del cliente, tipo de credito, ingresos, deudas y monto solicitado")
