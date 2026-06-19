# RETO final — Construye un "LO QUE UD QUIERA de Conversación" (nivel producción)

Este reto junta TODO el curso: prompting estructurado (clase 1), chaining
(clase 2), routing (clase 3), evaluator-optimizer (clase 4) y ReAct con
herramientas (clase 5). El objetivo no es solo que "funcione", sino que escribas
codigo que cualquier equipo aceptaria en producción: modular, tipado, validado,
probado y a prueba de fallos.

Trabaja en una carpeta nueva (`reto/`), con su propio `pyproject.toml` y
`langgraph.json`, igual que las clases.


Fecha de entrega: AL acabarlo, no se presione, simplemente hagalo pensandolo!!!
---

## El escenario

Eres responsable de un agente que ayuda a una persona a redactar el PRIMER
mensaje para alguien que acaba de conocer. El agente debe:

1. Entender a quien va dirigido (analizar el perfil).
2. Elegir el enfoque adecuado segun la intencion (reconciliacion / casual /
   romantico) — esto es routing.
3. Redactar un mensaje con herramientas de apoyo (ReAct).
4. Evaluar su propia salida con una rubrica y mejorarla si no llega al umbral
   (evaluator-optimizer).
5. Nunca enviar algo irrespetuoso o invasivo (guardrails).

---

## Requisitos funcionales (lo que debe HACER)

1. **Router de intencion.** Un nodo clasifica la peticion en una de tres
   intenciones con salida estructurada (Pydantic). Cada intencion ajusta el tono
   del agente.
2. **Agente ReAct con minimo 4 herramientas tipadas**, por ejemplo:
   - `analizar_perfil(perfil) -> Insights` (devuelve un objeto Pydantic, no texto).
   - `sugerir_plan(interes) -> str` con un catalogo real (>= 8 entradas).
   - `auditar_respeto(mensaje) -> Auditoria` (Pydantic: `aprobado: bool`, `motivos: list[str]`).
   - `estimar_longitud(mensaje) -> int` (palabras) para controlar la brevedad.
   - (Opcional) una tool que consulte una "agenda" simulada para proponer dia.
3. **Bucle evaluator-optimizer** envolviendo al agente: tras producir el mensaje,
   un evaluador (LLM-as-judge con rubrica de 4 criterios, 0-10) lo puntua. Si el
   promedio < umbral, el agente reescribe usando el feedback. Maximo N vueltas.
4. **Guardrails duros (en codigo, no solo en el prompt).** Aunque el modelo diga
   que el mensaje es bueno, tu codigo debe RECHAZAR y forzar reintento si
   `auditar_respeto` devuelve `aprobado=False`. La seguridad no se delega al LLM.
5. **Trazabilidad.** El estado debe guardar el historial de iteraciones (usa un
   reducer) para poder explicar como se llego al resultado final.

---

## Requisitos tecnicos (COMO debe estar escrito)

Aqui es donde subes de nivel como programador. Se evaluara:

- **Modularidad estricta.** Separa responsabilidades en archivos: `tools.py`,
  `prompts.py`, `schemas.py`, `graph.py`, `settings.py`, `main.py`. Ningun
  archivo debe mezclar prompts, logica de grafo y definicion de tools.
- **Typing completo.** Todas las funciones con anotaciones de tipos. Nada de
  `Any` salvo que sea inevitable y justificado con un comentario.
- **Pydantic para TODO contrato de datos.** Entradas de la CLI, salidas del
  router, del evaluador y de las tools que devuelven estructura. Usa `Field` con
  descripciones y validaciones (`ge`, `le`, longitudes).
- **Manejo de errores.** Las tools pueden fallar (entrada no valida, clave
  inexistente). Manejalo con mensajes claros que el agente pueda interpretar; no
  dejes que una excepcion tumbe el grafo.
- **Cortafuegos.** `recursion_limit` en la invocacion y un tope de iteraciones
  del evaluator-optimizer. Justifica los numeros que elijas.
- **Tests.** Minimo:
  - Tests unitarios de las tools deterministas (sin llamar al LLM).
  - Un test del guardrail: un mensaje irrespetuoso debe ser rechazado SIEMPRE.
  - Un test de que el grafo compila y expone los nodos esperados.
  Usa `pytest`. Los tests del grafo no deben gastar tokens (mockea el LLM o
  prueba solo la estructura).
- **Reproducibilidad.** `uv sync` y `uv run langgraph dev` deben funcionar sin
  tocar nada mas. Incluye un `README.md` con el diagrama del grafo y como correrlo.
- **Sin emojis** en codigo ni documentacion.

---

## Entregables

1. Carpeta `reto/` autonoma con todo el codigo y `pyproject.toml` + `langgraph.json`.
2. `README.md` con: diagrama del grafo, decisiones de diseno y como ejecutarlo.
3. `tests/` con los tests descritos, en verde (`uv run pytest`).
4. Un parrafo corto: que parte fue la mas dificil y como la resolviste.

---

## Rubrica de evaluacion (100 puntos)

| Area | Puntos | Que se mira |
| ---- | ------ | ----------- |
| Funciona end-to-end (`langgraph dev` + CLI) | 20 | Produce un mensaje aprobado por los guardrails |
| Arquitectura y modularidad | 20 | Separacion limpia, sin acoplamientos raros |
| Typing y Pydantic | 15 | Contratos claros, validaciones reales |
| Guardrails en codigo | 15 | La seguridad NO depende del prompt |
| Evaluator-optimizer | 15 | El bucle mejora de verdad y converge |
| Tests | 10 | Cubren tools, guardrail y compilacion |
| Manejo de errores y cortafuegos | 5 | El grafo no se cae ante entradas raras |

Aprueba con 70. Para "excelente" (90+) tu codigo debe poder leerse de corrido y
entenderse sin que te lo expliquen.

---

## Pistas (no mires hasta intentarlo)

- Empieza por los `schemas.py`: si defines bien los contratos, el resto del
  codigo casi se escribe solo.
- El guardrail duro vive en una arista condicional: tras `auditar_respeto`,
  decides en codigo si vas a `END` o vuelves al agente con el motivo del rechazo.
- Para el evaluator-optimizer reutiliza la idea de la clase 4: nodo `evaluador`
  con `with_structured_output`, promedio calculado en codigo, y una funcion
  `decidir` que cierra el ciclo por umbral o por iteraciones.
- Para combinar ReAct con el bucle de evaluacion, piensa en dos niveles: el
  agente ReAct produce un borrador (sub-grafo o nodo), y por fuera el evaluador
  decide si ese borrador se acepta o se pide otro.
- Mockea el LLM en los tests con un objeto que devuelva una respuesta fija; asi
  pruebas tu logica sin depender de la red ni gastar tokens.

---

## Extensiones opcionales (para los que quieran ir mas alla)

- Anade memoria con un `checkpointer` y un `thread_id`, y permite continuar una
  conversacion en varias vueltas.
- Sustituye una tool simulada por una real (por ejemplo, busqueda web con Tavily,
  cuya clave ya esta en el `.env` del curso).
- Mide el coste: cuenta tokens por ejecucion y reportalo al final.
