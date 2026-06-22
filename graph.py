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
import re

from langchain_core.messages import SystemMessage, AIMessage, HumanMessage, ToolMessage
from langgraph.graph import END, START, MessagesState, StateGraph
from langgraph.prebuilt import ToolNode

from logger import get_logger
from settings import get_llm

from prompts import SYSTEM_AGENTE, SYSTEM_ROUTER, SYSTEM_EVALUADOR
from schemas import State, TipoCredito, ClasificacionCredito, EvaluacionPropuesta



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
# ---- clasificar_tipo_credito ---- #
##############################
#Clasificamos el tipo de crédito utilizando el primer mensaje del cliente

def clasificar_tipo_credito(state: State) -> dict:
    logger.info("Router — Clasificando tipo de crédito y tono")
    
    # Configuramos el LLM para que retorne obligatoriamente el esquema de Pydantic
    llm = get_llm(temperature=0.1).with_structured_output(ClasificacionCredito)
    
    # Tomamos el primer mensaje del usuario (el perfil del cliente)
    mensaje_usuario = state["messages"][0].content
    
    # Armamos la consulta al modelo
    mensajes = [
        SystemMessage(content=SYSTEM_ROUTER),
        HumanMessage(content=f"Perfil del cliente a analizar:\n{mensaje_usuario}")
    ]
    
    respuesta = llm.invoke(mensajes)
    
    # Retornamos el diccionario que actualizará los campos 'tipo_credito' y 'tono' en el State
    return {
        "tipo_credito": respuesta.tipo_credito,
        "tono": respuesta.tono
    }



###############################################
# ---- Modelo con herramientas enlazadas ---- #
###############################################
# temperature baja: usar herramientas con fiabilidad pesa más que la creatividad.


def _llm_con_tools():
    return get_llm(temperature=0.2).bind_tools(TOOLS)


##########################################################################
# ---- Nodo agente: razona y, si hace falta, pide llamar a una tool ---- #
# Cambie la forma en que hacemos el agente, para que al momento de pintar me de mas información
##########################################################################
def agente(state: State) -> dict:
    # 1. Determinar un log dinámico según el último mensaje recibido
    if not state["messages"]:
        detalle = "iniciando análisis del caso"
    else:
        ultimo = state["messages"][-1]
        if isinstance(ultimo, ToolMessage):
            # Muestra sobre qué herramienta acaba de recibir datos
            detalle = f"analizando resultado de la herramienta '{ultimo.name}'"
        elif isinstance(ultimo, HumanMessage):
            # Si el último mensaje contiene la palabra 'Retroalimentación', está en refinamiento
            if "Retroalimentación" in ultimo.content:
                detalle = f"optimizando propuesta (Iteración {state.get('iteraciones', 0) + 1})"
            else:
                detalle = "iniciando evaluación del perfil del cliente"
        else:
            detalle = "razonando sobre el siguiente paso"

    logger.info(f"Agente — {detalle}")
    
    # 2. Flujo normal de ejecución
    tipo_credito = state.get("tipo_credito")
    tono = state.get("tono")
    
    contexto_adicional = f"\n\n[CONTEXTO DE LA EVALUACIÓN]\n- Tipo de crédito clasificado: {tipo_credito}\n- Tono asignado para la redacción: {tono}\nAsegúrate de utilizar estas especificaciones en tu análisis y redacción final."
    
    mensajes = [SystemMessage(content=SYSTEM_AGENTE + contexto_adicional)] + state["messages"]
    respuesta = _llm_con_tools().invoke(mensajes)
    return {"messages": [respuesta]}




######################################################
# ---- Enrutador de herramientas individualizado ---- #
######################################################
def route_tools(state: State):
    """Revisa el último mensaje y decide a qué nodo de herramienta ir, o si pasa a verificación de políticas."""
    ultimo_mensaje = state["messages"][-1]
    
    # Verificamos que sea un mensaje de la IA y que tenga llamadas a herramientas
    if not isinstance(ultimo_mensaje, AIMessage) or not ultimo_mensaje.tool_calls:
        return "verificar_politicas"
        
    # Enrutamos al nodo que coincide con el nombre de la herramienta solicitada
    return ultimo_mensaje.tool_calls[0]["name"]



##################################################
# ---- Construcción y compilación del grafo ---- #
##################################################
def build_graph() -> StateGraph:
    workflow = StateGraph(State)

    # 1. Registramos el nuevo nodo clasificador y el agente
    workflow.add_node("clasificar_tipo_credito", clasificar_tipo_credito)
    workflow.add_node("agente", agente)
    workflow.add_node("evaluador", evaluador)
    workflow.add_node("verificar_politicas", verificar_politicas)
    workflow.add_node("rechazo_politicas", rechazo_politicas)
    
    # Añadimos cada herramienta como un nodo independiente
    workflow.add_node("consultar_buro_de_credito", ToolNode([consultar_buro_de_credito]))
    workflow.add_node("evaluar_riesgo", ToolNode([evaluar_riesgo]))
    workflow.add_node("capacidad_de_pago", ToolNode([capacidad_de_pago]))
    workflow.add_node("calcula_tasa", ToolNode([calcula_tasa]))
    workflow.add_node("calcula_renta", ToolNode([calcula_renta]))
    workflow.add_node("calcular_monto_maximo_aprobado", ToolNode([calcular_monto_maximo_aprobado]))
    workflow.add_node("auditar_respeto", ToolNode([auditar_respeto]))

    # 2. Modificamos el inicio del flujo
    workflow.add_edge(START, "clasificar_tipo_credito")  # START ahora va al Router
    workflow.add_edge("clasificar_tipo_credito", "agente") # El Router pasa el flujo al agente

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
            "verificar_politicas": "verificar_politicas"
        }
    )

    workflow.add_conditional_edges(
        "verificar_politicas",
        decidir_despues_de_politicas,
        {
            "rechazo_politicas": "rechazo_politicas",
            "evaluador": "evaluador"
        }
    )

    workflow.add_conditional_edges(
        "evaluador",
        decidir_siguiente_paso,
        {
            "agente": "agente",
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
    
    workflow.add_edge("rechazo_politicas", END)

    return workflow

def evaluador(state: State) -> dict:
    logger.info("Evaluador — Evaluando la propuesta generada")
    
    # Configuramos el LLM para retornar obligatoriamente el formato EvaluacionPropuesta
    llm = get_llm(temperature=0.1).with_structured_output(EvaluacionPropuesta)
    
    # Obtenemos el borrador y el perfil inicial del cliente
    propuesta = state["messages"][-1].content
    perfil_cliente = state["messages"][0].content
    
    prompt = f"{SYSTEM_EVALUADOR}\n\nPerfil del Cliente:\n{perfil_cliente}\n\nPropuesta a Evaluar:\n{propuesta}"
    
    respuesta = llm.invoke(prompt)
    
    # Incrementamos el contador de iteraciones
    iteracion_actual = state.get("iteraciones", 0) + 1
    
    # Formamos el diccionario de evaluación para la trazabilidad (reducer)
    eval_dict = {
        "iteracion": iteracion_actual,
        "coherencia_financiera": respuesta.coherencia_financiera,
        "claridad_y_estructura": respuesta.claridad_y_estructura,
        "adecuacion_tono": respuesta.adecuacion_tono,
        "gestion_riesgo": respuesta.gestion_riesgo,
        "promedio": respuesta.promedio,
        "aprobado": respuesta.aprobado,
        "feedback": respuesta.feedback
    }
    
    logger.info(f"Iteración {iteracion_actual} - Calificación: {respuesta.promedio:.2f} (Aprobado: {respuesta.aprobado})")
    
    retorno = {
        "iteraciones": iteracion_actual,
        "historial_iteraciones": [eval_dict]
    }
    
    # Si la propuesta no fue aprobada y no hemos superado las 3 vueltas, inyectamos feedback al agente
    if not respuesta.aprobado and iteracion_actual < 3:
        mensaje_feedback = HumanMessage(
            content=(
                f"La propuesta no fue aprobada por el evaluador (Promedio: {respuesta.promedio:.1f}/10.0).\n"
                f"Retroalimentación a corregir:\n{respuesta.feedback}\n"
                f"Por favor, ajusta la propuesta y redacta una nueva versión."
            )
        )
        retorno["messages"] = [mensaje_feedback]
        
    return retorno


def decidir_siguiente_paso(state: State):
    """Revisa la última evaluación para decidir si volver al agente o terminar."""
    historial = state.get("historial_iteraciones")
    if not historial:
        return END
        
    ultima_eval = historial[-1]
    
    # Si está aprobado o ya se completaron 3 intentos de mejora, terminamos
    if ultima_eval["aprobado"] or state.get("iteraciones", 0) >= 3:
        logger.success("Evaluador — Propuesta aprobada o límite de intentos alcanzado")
        return END
        
    logger.info("Evaluador — Redirigiendo al agente para corrección")
    return "agente"


def verificar_politicas(state: State) -> dict:
    logger.info("Guardrail — Verificando políticas de riesgo (Score y Endeudamiento)")
    
    # 1. Intentamos extraer ingresos y gastos del primer mensaje (perfil)
    mensaje_inicial = state["messages"][0].content
    match_ingresos = re.search(r"ingresos:\s*(\d+)", mensaje_inicial, re.IGNORECASE)
    match_gastos = re.search(r"gastos:\s*(\d+)", mensaje_inicial, re.IGNORECASE)
    
    ingresos = float(match_ingresos.group(1)) if match_ingresos else 1.0
    gastos = float(match_gastos.group(1)) if match_gastos else 0.0
    ratio = gastos / ingresos if ingresos > 0 else 0.0
    
    # 2. Buscamos en el historial de mensajes la respuesta del buró
    score = None
    for msg in state["messages"]:
        if isinstance(msg, ToolMessage) and msg.name == "consultar_buro_de_credito":
            match_score = re.search(r"score=(\d+)", msg.content)
            if match_score:
                score = int(match_score.group(1))
                
    # 3. Guardamos los valores analizados en el estado
    updates = {
        "ratio_endeudamiento": ratio,
        "score_buro": score,
        "aprobado_riesgo": True
    }
    
    # 4. Validamos políticas críticas (Guardrail Duro)
    violaciones = []
    if score is not None and score < 500:
        violaciones.append(f"Score de buró de crédito insuficiente ({score} < 500)")
    if ratio > 0.65:
        violaciones.append(f"Ratio de endeudamiento excesivo ({ratio*100:.1f}% > 65.0%)")
        
    if violaciones:
        logger.warning(f"Políticas de riesgo violadas: {', '.join(violaciones)}")
        updates["aprobado_riesgo"] = False
        
    return updates


def decidir_despues_de_politicas(state: State):
    """Decide si enviar a evaluación o rechazar directamente según las políticas."""
    if state.get("aprobado_riesgo") is False:
        logger.warning("Guardrail Duro activado — Redirigiendo a rechazo automático")
        return "rechazo_politicas"
    
    logger.info("Políticas aprobadas — Pasando a evaluación del borrador")
    return "evaluador"


def rechazo_politicas(state: State) -> dict:
    logger.info("Guardrail — Escribiendo mensaje de rechazo definitivo")
    
    # Redacción fija y segura del rechazo
    mensaje_rechazo = (
        "### Respuesta para el Cliente:\n\n"
        "Estimado cliente,\n\n"
        "Agradecemos sinceramente su confianza al solicitar un financiamiento con nosotros. "
        "Lamentamos informarle que tras evaluar su solicitud, esta ha sido declinada debido a que no cumple "
        "con nuestras políticas internas de riesgo de crédito vigentes.\n\n"
        "Agradecemos su comprensión.\n\n"
        "Atentamente,\n"
        "Comité de Crédito\n\n"
        "---\n\n"
        "### Respuesta para el Ejecutivo:\n\n"
        "La solicitud fue rechazada de forma automática por el sistema debido al incumplimiento de las políticas críticas:\n"
    )
    
    if state.get("score_buro") and state["score_buro"] < 500:
        mensaje_rechazo += f"- Score de buró de crédito por debajo del mínimo requerido ({state['score_buro']} < 500).\n"
    if state.get("ratio_endeudamiento") and state["ratio_endeudamiento"] > 0.65:
        mensaje_rechazo += f"- Ratio de endeudamiento superior al límite del 65% ({state['ratio_endeudamiento']*100:.1f}%).\n"
        
    return {"messages": [AIMessage(content=mensaje_rechazo)]}


graph = build_graph().compile()
