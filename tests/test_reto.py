import pytest
from langchain_core.messages import HumanMessage, ToolMessage
from schemas import State, TipoCredito
from tools import capacidad_de_pago, calcula_renta, calcular_monto_maximo_aprobado, auditar_respeto
from graph import graph, verificar_politicas

# ---- Tests for Deterministic Tools ----

def test_capacidad_de_pago():
    # Caso 1: Ingresos menores o iguales a gastos
    assert capacidad_de_pago.invoke({"ingresos": 10000, "gastos": 10000}) == 0
    assert capacidad_de_pago.invoke({"ingresos": 5000, "gastos": 10000}) == 0
    
    # Caso 2: Cálculo del 35% de la diferencia
    # (100,000 - 30,000) * 0.35 = 70,000 * 0.35 = 24,500
    assert capacidad_de_pago.invoke({"ingresos": 100000, "gastos": 30000}) == 24500.0
    
    # (40,000 - 25,000) * 0.35 = 15,000 * 0.35 = 5,250
    assert capacidad_de_pago.invoke({"ingresos": 40000, "gastos": 25000}) == 5250.0


def test_calcula_renta():
    # Amortización francesa para $50,000, tasa 10% anual, 12 meses
    renta = calcula_renta.invoke({"monto": 50000, "tasa": 10, "plazo": 12})
    assert abs(renta - 4395.79) < 0.05


def test_calcular_monto_maximo_aprobado():
    # Para capacidad de pago = 5,250, tasa 22%, plazo 24 meses
    # El valor presente de la anualidad redondeado hacia abajo al mil más cercano
    monto = calcular_monto_maximo_aprobado.invoke({"capacidad_pago": 5250, "tasa": 22, "plazo": 24})
    assert monto == 101000.0


def test_auditar_respeto_prohibido():
    # Caso 1: Palabras prohibidas
    resultado = auditar_respeto.invoke({
        "mensaje": "Por favor introduzca su password para continuar.",
        "capacidad_pago": 5000,
        "renta_mensual": 4000
    })
    assert resultado.aprobado is False
    assert any("palabras no autorizadas" in m for m in resultado.motivos)


def test_auditar_respeto_capacidad():
    # Caso 2: Renta supera capacidad
    resultado = auditar_respeto.invoke({
        "mensaje": "Mensaje respetuoso y corto.",
        "capacidad_pago": 3000,
        "renta_mensual": 4000
    })
    assert resultado.aprobado is False
    assert any("supera la capacidad maxima" in m for m in resultado.motivos)


def test_auditar_respeto_exceso_palabras():
    # Caso 3: Mensaje demasiado largo
    largo_mensaje = "hola " * 350
    resultado = auditar_respeto.invoke({
        "mensaje": largo_mensaje,
        "capacidad_pago": 5000,
        "renta_mensual": 4000
    })
    assert resultado.aprobado is False
    assert any("excede el limite de 300 palabras" in m for m in resultado.motivos)


def test_auditar_respeto_exitoso():
    # Caso 4: Todo en orden
    resultado = auditar_respeto.invoke({
        "mensaje": "Estimado cliente, nos complace informarle que su crédito ha sido aprobado.",
        "capacidad_pago": 5000,
        "renta_mensual": 4000
    })
    assert resultado.aprobado is True
    assert len(resultado.motivos) == 0


# ---- Tests for Hard Guardrails (Python Code) ----

def test_guardrail_bajo_score():
    # Simulamos un estado donde el buró tiene score de 480 (insuficiente < 500)
    state = {
        "messages": [
            HumanMessage(content="RFC: ZXC010101QW1, ingresos: 100000, gastos: 30000"),
            ToolMessage(content="score=480 impagos_historicos=4 detalles='Historial deficiente'", name="consultar_buro_de_credito", tool_call_id="1")
        ]
    }
    resultado = verificar_politicas(state)
    assert resultado["aprobado_riesgo"] is False
    assert resultado["score_buro"] == 480


def test_guardrail_alto_endeudamiento():
    # Simulamos un estado con un ratio de endeudamiento de 66.6% (gastos 20k / ingresos 30k)
    state = {
        "messages": [
            HumanMessage(content="RFC: ABC120304XYZ, ingresos: 30000, gastos: 20000"),
            ToolMessage(content="score=820 impagos_historicos=0 detalles='Excelente'", name="consultar_buro_de_credito", tool_call_id="1")
        ]
    }
    resultado = verificar_politicas(state)
    assert resultado["aprobado_riesgo"] is False
    assert resultado["ratio_endeudamiento"] == pytest.approx(0.666, abs=0.01)


def test_guardrail_aprobado():
    # Caso donde se cumplen ambas políticas
    state = {
        "messages": [
            HumanMessage(content="RFC: ABC120304XYZ, ingresos: 100000, gastos: 30000"),
            ToolMessage(content="score=820 impagos_historicos=0 detalles='Excelente'", name="consultar_buro_de_credito", tool_call_id="1")
        ]
    }
    resultado = verificar_politicas(state)
    assert resultado["aprobado_riesgo"] is True
    assert resultado["score_buro"] == 820
    assert resultado["ratio_endeudamiento"] == 0.30


# ---- Test for Graph Compilation ----

def test_graph_compiles_correctly():
    # Verificamos que el grafo tenga los nodos esperados registrados
    nodos_esperados = {
        "clasificar_tipo_credito",
        "agente",
        "evaluador",
        "verificar_politicas",
        "rechazo_politicas",
        "consultar_buro_de_credito",
        "evaluar_riesgo",
        "capacidad_de_pago",
        "calcula_tasa",
        "calcula_renta",
        "calcular_monto_maximo_aprobado",
        "auditar_respeto"
    }
    nodos_reales = set(graph.nodes.keys())
    for nodo in nodos_esperados:
        assert nodo in nodos_reales
