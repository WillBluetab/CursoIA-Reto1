"""
Grafo de la clase 5: ReAct (Reasoning + Acting).

ReAct = el modelo alterna entre RAZONAR y ACTUAR (llamar herramientas), usando
lo que observa para decidir el siguiente paso, hasta que tiene la respuesta.

    START → agente → ¿pidió usar una tool?
              ↑                │  no → END
              │                │  sí
              └──── tools ◀────┘

Piezas nuevas:
- `bind_tools`: le damos al modelo el "catálogo" de herramientas disponibles.
- `ToolNode`: nodo prefabricado que EJECUTA las tools que el modelo pidió.
- `tools_condition`: función prefabricada que mira el último mensaje y decide si
  hay que ir a ejecutar tools o si ya podemos terminar.

El bucle agente → tools → agente es el corazón del patrón ReAct.
"""

from __future__ import annotations

from langchain_core.messages import SystemMessage
from langgraph.graph import END, START, MessagesState, StateGraph
from langgraph.prebuilt import ToolNode
from langchain_core.messages import SystemMessage, AIMessage

from logger import get_logger
from prompts import SYSTEM_AGENTE
from settings import get_llm

from schemas import State, TipoCredito

from tools import (
    consultar_buro_de_credito, 
    evaluar_riesgo,  
    capacidad_de_pago, 
    calcula_tasa, 
    calcula_renta, 
    calcular_monto_maximo_aprobado, 
    auditar_respeto, 
    TOOLS
)


logger = get_logger("graph")


##############################
# ---- Estado del grafo ---- #
##############################
# Reutilizamos MessagesState (de LangGraph): trae un campo `messages` con el
# reducer add_messages ya configurado, que ACUMULA la conversación (humano,
# IA, llamadas a tools y sus resultados). Es lo estándar para agentes.


###############################################
# ---- Modelo con herramientas enlazadas ---- #
###############################################
# temperature baja: usar herramientas con fiabilidad pesa más que la creatividad.


def _llm_con_tools():
    return get_llm(temperature=0.2).bind_tools(TOOLS)


##########################################################################
# ---- Nodo agente: razona y, si hace falta, pide llamar a una tool ---- #
##########################################################################
def agente(state: State) -> dict:
    logger.info("Agente — razonando sobre el siguiente paso")
    # Anteponemos el system prompt a la conversación acumulada.
    mensajes = [SystemMessage(content=SYSTEM_AGENTE)] + state["messages"]
    respuesta = _llm_con_tools().invoke(mensajes)
    # add_messages añade la respuesta (que puede incluir tool_calls) al estado.
    return {"messages": [respuesta]}


######################################################
# ---- Enrutador de herramientas individualizado ---- #
######################################################
def route_tools(state: State):
    """Revisa el último mensaje y decide a qué nodo de herramienta ir, o si termina."""
    ultimo_mensaje = state["messages"][-1]
    
    # Verificamos que sea un mensaje de la IA y que tenga llamadas a herramientas
    if not isinstance(ultimo_mensaje, AIMessage) or not ultimo_mensaje.tool_calls:
        return END
        
    # Enrutamos al nodo que coincide con el nombre de la herramienta solicitada
    return ultimo_mensaje.tool_calls[0]["name"]



##################################################
# ---- Construcción y compilación del grafo ---- #
##################################################
def build_graph() -> StateGraph:
    workflow = StateGraph(State)

    workflow.add_node("agente", agente)
    
    # Añadimos cada herramienta como un nodo independiente
    workflow.add_node("consultar_buro_de_credito", ToolNode([consultar_buro_de_credito]))
    workflow.add_node("evaluar_riesgo", ToolNode([evaluar_riesgo]))
    workflow.add_node("capacidad_de_pago", ToolNode([capacidad_de_pago]))
    workflow.add_node("calcula_tasa", ToolNode([calcula_tasa]))
    workflow.add_node("calcula_renta", ToolNode([calcula_renta]))
    workflow.add_node("calcular_monto_maximo_aprobado", ToolNode([calcular_monto_maximo_aprobado]))
    workflow.add_node("auditar_respeto", ToolNode([auditar_respeto]))

    workflow.add_edge(START, "agente")

    # Mapeamos la arista condicional para redirigir al nodo correcto de herramienta
    workflow.add_conditional_edges(
        "agente",
        route_tools,
        {
            "consultar_buro_de_credito": "consultar_buro_de_credito",
            "evaluar_riesgo": "evaluar_riesgo",
            "capacidad_de_pago": "capacidad_de_pago",
            "calcula_tasa": "calcula_tasa",
            "calcula_renta": "calcula_renta",
            "calcular_monto_maximo_aprobado": "calcular_monto_maximo_aprobado",
            "auditar_respeto": "auditar_respeto",
            END: END
        }
    )

    # Cada herramienta vuelve al agente tras completarse para que evalúe el resultado
    workflow.add_edge("consultar_buro_de_credito", "agente")
    workflow.add_edge("evaluar_riesgo", "agente")
    workflow.add_edge("capacidad_de_pago", "agente")
    workflow.add_edge("calcula_tasa", "agente")
    workflow.add_edge("calcula_renta", "agente")
    workflow.add_edge("calcular_monto_maximo_aprobado", "agente")
    workflow.add_edge("auditar_respeto", "agente")

    return workflow


graph = build_graph().compile()
