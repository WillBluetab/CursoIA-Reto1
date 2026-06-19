"""
Herramientas (tools) de la clase 5 (ReAct).

Una herramienta es una función que el modelo puede DECIDIR llamar. La clave es
que cada tool tiene un contrato claro: tipos de entrada/salida y un docstring que
el modelo lee para saber cuándo y cómo usarla.

Diseñamos tools DETERMINISTAS (sin LLM dentro): hacen cosas que el modelo no
debería inventar (validar reglas, consultar un catálogo). Esa es justo la gracia
de ReAct: el modelo razona, pero delega los hechos en herramientas fiables.
"""

from __future__ import annotations

from langchain_core.tools import tool

###############################################################################
# ---- Datos de apoyo (en un proyecto real vendrían de una BD o una API) ---- #
###############################################################################
# Catálogo mínimo: interés -> plan concreto sugerido.
_CATALOGO_TEMAS: dict[str, str] = {
    "mexico": "Visita Teotihuacan, un mercado de artesanías o disfruta la gastronomía local.",
    "miami": "visita la playa, South Beach o el distrito Art Déco",
    "paris": "ve a la torre Eiffel y el museo del Louvre",
    "europa": "un tour por museos, monumentos y ruinas",
    "china": "visita la murralla china, explora templos antiguos o saborea la gastronomía local.",
    "tokio": "visita el barrio de Shibuya, los templos de Asakusa o disfruta del sushi local.",
    "nueva york": "camina por Central Park, sube al Empire State o ve un show en Broadway.",
    "roma": "explora el Coliseo, la Fontana di Trevi y el Vaticano.",
    "londres": "ve el Big Ben, visita el Museo Británico o pasea junto al río Támesis.",
    "madrid": "camina por la Gran Vía, visita el Museo del Prado y come tapas en la Plaza Mayor.",
    "barcelona": "admira la Sagrada Familia, pasea por Las Ramblas o relájate en la playa de la Barceloneta.",
    "buenos aires": "disfruta un show de tango en San Telmo, camina por La Boca o come un asado tradicional.",
    "rio de janeiro": "sube al Cristo Redentor, visita el Pan de Azúcar o relájate en Copacabana.",
    "bogota": "sube al cerro de Monserrate, visita el Museo del Oro o camina por La Candelaria.",
    "lima": "explora el centro histórico, pasea por Miraflores o disfruta de su gastronomía marina.",
    "cuzco": "visita la Plaza de Armas, los templos incas o prepárate para ir a Machu Picchu.",
    "santiago": "sube al cerro San Cristóbal, visita el Palacio de La Moneda o recorre los viñedos cercanos.",
    "berlin": "ve los restos del Muro, cruza la Puerta de Brandeburgo y explora la Isla de los Museos.",
    "amsterdam": "recorre los canales en bote, visita el Museo Van Gogh o pasea en bicicleta.",
    "viena": "visita el Palacio de Schönbrunn, asiste a un concierto de ópera o prueba el pastel Sacher.",
    "praga": "cruza el Puente de Carlos, visita el Castillo y camina por la Plaza de la Ciudad Vieja.",
    "venecia": "da un paseo en góndola por el Gran Canal y visita la Plaza de San Marcos.",
    "florencia": "admira el Duomo, el David de Miguel Ángel y camina por el Ponte Vecchio.",
    "atenas": "explora la Acrópolis, el Partenón y camina por el animado barrio de Plaka.",
    "estambul": "visita la Mezquita Azul, el palacio de Topkapi y regatea en el Gran Bazar.",
    "el cairo": "admira las pirámides de Giza, la Esfinge y explora el Gran Museo Egipcio.",
    "kioto": "camina por el bosque de bambú de Arashiyama y visita los santuarios sintoístas.",
    "seul": "visita el palacio Gyeongbokgung, el barrio de Gangnam o compra en Myeongdong.",
    "bangkok": "explora el Gran Palacio, el templo Wat Arun y recorre los mercados flotantes.",
    "singapur": "visita los jardines Marina Bay Sands, la isla Sentosa o el jardín botánico.",
    "sidney": "haz una foto de la Ópera, cruza el puente de la bahía o relájate en Bondi Beach.",
    "orlando": "disfruta de los parques de Disney, Universal Studios o ve de compras a los outlets.",
    "las vegas": "recorre la Strip, ve un espectáculo nocturno o visita los casinos temáticos.",
    "los angeles": "camina por el Paseo de la Fama, visita Santa Mónica o el observatorio Griffith.",
    "san francisco": "cruza el Golden Gate, visita la isla de Alcatraz o sube a los tranvías históricos.",
    "toronto": "sube a la Torre CN, visita las islas de Toronto o haz una excursión a las cataratas del Niágara.",
    "montreal": "explora el Viejo Montreal, la basílica de Notre-Dame o disfruta de la gastronomía francófona.",
    "vancouver": "pasea por Stanley Park, cruza el puente colgante de Capilano o disfruta de la naturaleza.",
    "cancun": "disfruta de las playas caribeñas, los clubes nocturnos o visita una zona arqueológica cercana.",
    "oaxaca": "visita el templo de Santo Domingo, la zona de Monte Albán o prueba el mole local.",
    "medellin": "sube al Metrocable, visita la Plaza Botero o recorre la vibrante Comuna 13.",
    "cartagena": "camina por la ciudad amurallada, visita el castillo de San Felipe o relájate en sus islas.",
    "la habana": "pasea por el Malecón en un auto clásico y recorre las calles de La Habana Vieja.",
    "san jose": "visita el Teatro Nacional, los museos del centro o explora los volcanes cercanos.",
    "panama": "observa el tránsito de barcos en el Canal, visita el Casco Antiguo o ve de compras.",
    "lisboa": "sube al tranvía 28, visita la Torre de Belém y prueba los pasteles tradicionales.",
    "dublin": "visita el Trinity College, la fábrica de Guinness y disfruta la música en Temple Bar.",
    "edimburgo": "explora el Castillo de Edimburgo, camina por la Royal Mile o sube a Arthur's Seat.",
    "reikiavik": "busca auroras boreales, relájate en la Laguna Azul o haz la ruta del Círculo de Oro.",
    "marruecos": "explora los zocos de Marrakech, pasa una noche en el desierto o visita Fez.",
    "ciudad del cabo": "sube a la montaña de la Mesa, visita la isla Robben o ve los pingüinos en Boulders Beach.",
    "dubai": "sube al Burj Khalifa, visita el centro comercial Dubai Mall o haz un safari por el desierto.",
    "nueva zelanda": "explora los paisajes de El Señor de los Anillos, los fiordos o vive la cultura maorí.",
    "bali": "relájate en sus playas, visita los arrozales de Ubud o explora sus templos sagrados.",
    "hawai": "haz surf en las playas de Oahu, visita Pearl Harbor o explora los parques nacionales volcánicos."    
}

# Palabras que delatan presión o falta de respeto (guardrail).
_PALABRAS_PROHIBIDAS = ("sin dinero", "bajo presupuesto", "no tiene dinero", "dinero")

_CATALOGO_LUGAR: dict[str, str] = {
    "playa": "miami, hawai, cancun, rio de janeiro, cartagena, bali, barcelona, sidney",
    "montaña": "cuzco, vancouver, santiago",
    "naturaleza": "reikiavik, san jose, nueva zelanda, ciudad del cabo, kioto",
    "cultura": "mexico, china, roma, paris, atenas, el cairo, oaxaca, praga, florencia, marruecos, europa",
    "ciudad": "tokio, nueva york, londres, madrid, buenos aires, bogota, berlin, seul, toronto, los angeles, san francisco, medellin, lima, panama, dublin, edimburgo",
    "descanso": "amsterdam, venecia, viena, lisboa, la habana, montreal",
    "entretenimiento": "orlando, las vegas, dubai, singapur, bangkok, estambul"
}

########################################
# ---- Tool 0: analizar el lugar ---- #
########################################
@tool
def analizar_lugar(lugar: str) -> str:
    """Extrae las señales clave de un tipo de lugar para personalizar el mensaje.

    Args:
        lugar: Texto libre que describe a la persona y el lugar al que quiere ir

    Returns:
        Un resumen con los intereses detectados y un tono sugerido.
    """
    texto = lugar.lower()
    intereses = [tema for tema in _CATALOGO_LUGAR if tema in texto]
    #si no hay intereses damos por hecho que busco un lugar, y regresamos exactamente el mismo texto
    
    if not intereses:
        return  texto
    
    # Obtenemos los valores (los destinos recomendados) asociados a las categorías encontradas
    destinos_encontrados = [_CATALOGO_LUGAR[tema] for tema in intereses]
    return f"Categorías de viaje detectadas: {', '.join(intereses)}. Destinos sugeridos para estas categorías: {', '.join(destinos_encontrados)}."


########################################
# ---- Tool 1: analizar el perfil ---- #
########################################
@tool
def analizar_destino(destino: str) -> str:
    """Extrae las señales clave de un destino para personalizar el mensaje.

    Args:
        destino: Texto libre que describe a la persona y el lugar al que quiere ir

    Returns:
        Un resumen con los intereses detectados y un tono sugerido.
    """
    texto = destino.lower()
    intereses = [tema for tema in _CATALOGO_TEMAS if tema in texto]
    if not intereses:
        return "No se detectaron intereses claros; propon un lugar y posibles actividades."
    return f"Lugares detectados: {', '.join(intereses)}. Propón actividades para cada lugar."


############################################################
# ---- Tool 2: sugerir un lugar a partir de un interés ---- #
############################################################
@tool
def sugerir_plan(interes: str) -> str:
    """Propone un plan concreto para un interés dado.

    Args:
        interes: Una de los lugares a los que quiere ir.

    Returns:
        La descripción de un plan, o un aviso si el interés no está en el catálogo.
    """
    interes_limpio = (
        interes.strip()
        .lower()
        .replace("á", "a")
        .replace("é", "e")
        .replace("í", "i")
        .replace("ó", "o")
        .replace("ú", "u")
        .replace("ü", "u")
    )
    plan = _CATALOGO_TEMAS.get(interes_limpio)
    if plan is None:
        disponibles = ", ".join(_CATALOGO_TEMAS)
        return f"No tengo un plan para '{interes}'. Lugares disponibles: {disponibles}."
    return f"Lugar sugerido: {plan}."


#############################################################################
# ---- Tool 3: auditar el respeto del mensaje (guardrail determinista) ---- #
#############################################################################
@tool
def auditar_respeto(mensaje: str) -> str:
    """Valida que haya un lugar y que tenga presupuesto indicado.

    Args:
        mensaje: El texto del mensaje final a revisar.

    Returns:
        "APROBADO" si es seguro, o "RECHAZADO: ..." con el motivo concreto.
    """
    texto = mensaje.lower()
    encontradas = [p for p in _PALABRAS_PROHIBIDAS if p in texto]
    if encontradas:
        return f"RECHAZADO: no se cuenta con presupuesto suficiente ({', '.join(encontradas)})."
    if len(mensaje.split()) > 100:
        return f"RECHAZADO: el mensaje es demasiado largo ({len(mensaje.split())} palabras). El límite es de 100 palabras en total. Redacta una versión más breve y concisa."
    return "APROBADO"


# Lista que exportamos al grafo. Añadir una tool nueva es solo: definirla aquí
# y agregarla a esta lista.
TOOLS = [analizar_lugar, analizar_destino, sugerir_plan, auditar_respeto]
