"""
CLI de la clase 5 (ReAct).

Caso 1: Aprobación directa
    uv run python main.py -p "RFC: ABC120304XYZ, credito comercial, ingresos: 100000, gastos: 30000, monto: 50000" --traza

Caso 2: Aprobación Ajustada (Capacidad de pago superada)
    uv run python main.py -p "RFC: KLM030415A12, prestamo operativo, ingresos: 40000, gastos: 25000, monto: 150000" --traza

Caso 3: Rechazo (Riesgo Alto)
    uv run python main.py -p "RFC: XYZ987654MNO, credito personal, ingresos: 15000, gastos: 10000, monto: 500000" --traza

Caso langchain:
    uv run langgraph dev

Con --traza ves el ciclo completo: qué herramientas pidió el agente, con qué
argumentos y qué le devolvieron. Es la mejor forma de entender ReAct.cd..
"""

#######################
# ---- libraries ---- #
#######################

from __future__ import annotations

import argparse

from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

from graph import graph
from logger import get_logger
from schemas import ReactConfig

logger = get_logger("main")


#################
# ---- CLI ---- #
#################
def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Clase 5 — Agente ReAct")
    parser.add_argument("--perfil", "-p", required=True, help="RFC, tipo de crédito, ingresos, gastos y monto")
    parser.add_argument(
        "--traza", action="store_true", help="Muestra el ciclo razonar/actuar paso a paso"
    )
    return parser.parse_args()


#####################################################################
# ---- Traza: imprime el recorrido razonar → actuar → observar ---- #
#####################################################################
def _imprimir_traza(mensajes: list) -> None:
    print("\n--- TRAZA ReAct ---")
    for m in mensajes:
        if isinstance(m, AIMessage) and m.tool_calls:
            for tc in m.tool_calls:
                print(f"[ACCIÓN]      {tc['name']}({tc['args']})")
        elif isinstance(m, ToolMessage):
            print(f"[OBSERVACIÓN] {m.content}")
        elif isinstance(m, AIMessage) and m.content:
            print(f"[PENSAMIENTO] {m.content}")


##############################
# ---- Punto de entrada ---- #
##############################
def main() -> None:
    args = parse_args()
    config = ReactConfig(perfil=args.perfil)

    logger.info("Ejecutando el agente ReAct")
    entrada = HumanMessage(content=f"Información del crédito a obtener:\n{config.perfil}")
    # recursion_limit acota el bucle por si el agente se enreda (cinturón de seguridad).
    # Aumenté el iimite de recursion, ya que 25 en las pruebas se quedo corto. ya que cada llamada a las herramientas cuenta y conforme se agregan cosas gasto mas
    resultado = graph.invoke({"messages": [entrada]}, {"recursion_limit": 60})

    if args.traza:
        _imprimir_traza(resultado["messages"])

    logger.success("Agente terminado")  # type: ignore[attr-defined]
    print("\n--- MENSAJE FINAL ---")
    print(resultado["messages"][-1].content)


if __name__ == "__main__":
    main()
