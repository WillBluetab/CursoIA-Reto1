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
from schemas import TipoCredito
from schemas import BuroResponse
from typing import Any
from langchain_core.tools import tool
from schemas import *


###############################################################################
# ---- Datos de apoyo (en un proyecto real vendrían de una BD o una API) ---- #
###############################################################################

_CATALOGO_TASAS: dict[TipoCredito, dict[str, Any]] = {
    TipoCredito.CREDITO_COMERCIAL:{
        "bajo": 10.0,
        "medio": 15.0,
        "alto": 20.0
    },
    TipoCredito.PRESTAMO_OPERATIVO:{
        "bajo": 15.0,
        "medio": 22.0,
        "alto": 30.0
    },
    TipoCredito.LINEA_REVOLVENTE:{
        "bajo": 25.0,
        "medio": 35.0,
        "alto": 50.0
    }    
}


_CATALOGO_PLAZOS: dict[TipoCredito, dict[str, Any]] = {
    TipoCredito.CREDITO_COMERCIAL:{
    "plazo": 12
    },
    TipoCredito.PRESTAMO_OPERATIVO:{
    "plazo": 24
    },
    TipoCredito.LINEA_REVOLVENTE:{
    "plazo":36
    }    
}
    

# Palabras que activan el rechazo automático por invasión de privacidad o presión
_PALABRAS_PROHIBIDAS = ("password", "contraseña", "nip", "clave secreta", "obligado", "amenaza")

_CATALOGO_BURO: dict[str, dict[str, Any]] = {
    # Perfiles con Score Excelente (Aprobación rápida, bajo riesgo)
    "ABC120304XYZ": {
        "score": 820,
        "impagos_historicos": 0,
        "detalles": "Comportamiento de pago sobresaliente, sin retrasos registrados en los ultimos cinco anos."
    },
    "ASD920505MN3": {
        "score": 780,
        "impagos_historicos": 0,
        "detalles": "Historial solido, bajo nivel de endeudamiento y excelente puntualidad en sus compromisos."
    },
    # Perfiles con Score Bueno / Medio (Riesgo bajo o moderado, requiere revisión)
    "DFG950821M89": {
        "score": 710,
        "impagos_historicos": 0,
        "detalles": "Historial crediticio consistente y al corriente en todas sus lineas de financiamiento activas."
    },
    "KLM030415A12": {
        "score": 670,
        "impagos_historicos": 1,
        "detalles": "Buen perfil de pago, reporta un unico retraso menor a quince dias a principios de ano."
    },
    "POU871115ZX2": {
        "score": 630,
        "impagos_historicos": 1,
        "detalles": "Perfil de riesgo moderado, cuenta activa con saldo alto pero al corriente en amortizaciones."
    },
    # Perfiles con Score Regular (Riesgo medio, tasas más altas)
    "QWE880912TY4": {
        "score": 580,
        "impagos_historicos": 2,
        "detalles": "Historial regular, reporta dos cuentas con atrasos recurrentes de entre quince y treinta dias."
    },
    "UIO9912319A0": {
        "score": 520,
        "impagos_historicos": 3,
        "detalles": "Riesgo medio alto, comportamiento de pago inestable con retrasos habituales en el ultimo trimestre."
    },
    # Perfiles con Score Deficiente (Rechazo inmediato por Guardrail Duro de Buró < 500)
    "ZXC010101QW1": {
        "score": 480,
        "impagos_historicos": 4,
        "detalles": "Historial deficiente, multiples cuentas comerciales con atrasos superiores a sesenta dias."
    },
    "VBN850630TY9": {
        "score": 410,
        "impagos_historicos": 6,
        "detalles": "Alto riesgo, cuenta con demandas de cobro mercantil activas reportadas por sus acreedores."
    },
    "RTY901010HJK": {
        "score": 320,
        "impagos_historicos": 9,
        "detalles": "Riesgo critico, historial con cartera vencida recurrente y suspension de lineas por impago."
    }
}

#############################################################################
# Funciones internas
#############################################################################

def tipo_de_credito(mensaje: str) -> TipoCredito:
    """Valida que tipo de credito se adapta al mensaje.

    Args:
        mensaje: El texto del mensaje final a revisar.

    Returns:
        tipocredito: El tipo de credito adaptado al mensaje.
    """
    texto = mensaje.lower()
    if "comercial" in texto or "credito comercial" in texto or "credito_comercial" in texto:
        return TipoCredito.CREDITO_COMERCIAL
    elif "operativo" in texto or "prestamo operativo" in texto or "prestamo_operativo" in texto:
        return TipoCredito.PRESTAMO_OPERATIVO
    elif "revolvente" in texto or "linea revolvente" in texto or "linea_revolvente" in texto:
        return TipoCredito.LINEA_REVOLVENTE
    else:
        raise ValueError("No se pudo determinar el tipo de credito")

########################################
# ---- Tool 0: Buro de Credito ---- #
########################################
@tool
def consultar_buro_de_credito(rfc: str) -> BuroResponse:
    """Extrae el buro de credito de un cliente.

    Args:
        rfc: rfc del cliente

    Returns:
        El buro del cliente, si no lo encuentra, se supondría que no tiene buro, y regresamos una pesima calificación para simular un alto riesgo y negar el credito
    """
    texto = rfc.upper()
    if texto in _CATALOGO_BURO:
        datos=_CATALOGO_BURO[texto]
        return BuroResponse(
            score=datos["score"],
            impagos_historicos=datos["impagos_historicos"],
            detalles=datos["detalles"]
        )
    return BuroResponse(
        score=300,
        impagos_historicos=10,
        detalles="El cliente no cuenta con historial crediticio"
    )
    

########################################
# ---- Tool 1: Evalua el riesgo del cliente ---- #
########################################
@tool
def evaluar_riesgo(buro:BuroResponse) -> EvaluacionRiesgo:
    """Con lo obtenido del buro, se calcula un riesgo.

    Args:
        buro: Resultados del buro de credito

    Returns:
        Evaluación del riesgo, voy a establecer 3 niveles, 
        bajo corta en 680 puntos y sin ningun impago
        medio corta en 500 y maximo 3 impagos
        alto de ahi para abajo en score y si hay mas de 3 impagos 
    """
    score=buro.score
    impagos=buro.impagos_historicos
    
    if score>=680 and impagos==0:
        return EvaluacionRiesgo(
            nivel_riesgo="bajo",
            aprobado_para_oferta=True,
            justificacion_riesgo="El cliente cuenta con un puntaje de credito excelente y sin impagos, lo que indica un bajo riesgo crediticio."
        )
    elif score>=500 and impagos<=3:
        return EvaluacionRiesgo(
            nivel_riesgo="medio",
            aprobado_para_oferta=True,
            justificacion_riesgo="El cliente cuenta con un puntaje de credito moderado y pocos impagos, lo que indica un riesgo moderado."
        )
    else:
        return EvaluacionRiesgo(
            nivel_riesgo="alto",
            aprobado_para_oferta=False,
            justificacion_riesgo="El cliente cuenta con un puntaje de credito bajo y muchos impagos, lo que indica un alto riesgo crediticio."
        )       



############################################################
# ---- Tool 2: calcular la capacidad de pago ---- #
############################################################
@tool
def capacidad_de_pago(ingresos: float, gastos: float) -> float:
    """Calcula el maxmo de pago mensual.

    Args:
        ingresos: Ingresos mensuales
        gastos: Gastos mensuales

    Returns:
        El maximo de pago mensual.
    """
    if (ingresos-gastos)<=0:
        return 0
    #Se toma el 35% de los ingresos menos gastos.
    capacidad= round((ingresos-gastos)*0.35, 2)
    return capacidad


#############################################################################
# ---- Tool 4: Calcula Tasa ---- #
#############################################################################
@tool
def calcula_tasa(tipo_credito:TipoCredito, riesgo:EvaluacionRiesgo) -> TasaResponse:
    """Calcula las opciones de tasas de interes para el tipo de credito solicitado
    
    Args:
        tipo_credito: El tipo de credito solicitado.
        riesgo: El nivel de riesgo del cliente, obtenido por el buro de credito
        
    Returns:
        Un diccionario con la tasa de interes anual simple y el rango de tasa.
    """

    tasa_final=1000 #Tasa de protección en caso de error
    explicacion="Tasa no determinada"
    plazo_final=1 #Plazo de protección en caso de error

    #saco las tasas (las 3, baja, medio y alto) y el plazo para el tipo de credito solicitado

    plazo=_CATALOGO_PLAZOS[tipo_credito]
    tasa=_CATALOGO_TASAS[tipo_credito]
    #como ya tengo el buro, puedo calcular su nivel de riesgo y seleccionar entre las 3 tasas
    
    
    #Determinamos la tasa final
    if riesgo.nivel_riesgo=="bajo":
        tasa_final=tasa["bajo"]
        explicacion="Tasa muy competitiva, ideal para clientes con buen historial crediticio."
    elif riesgo.nivel_riesgo=="medio":
        tasa_final=tasa["medio"]
        explicacion="Tasa estandar, adecuada para clientes con un historial crediticio promedio."
    elif riesgo.nivel_riesgo=="alto":
        tasa_final=tasa["alto"]
        explicacion="Tasa alta, recomendada para clientes con un historial crediticio regular."
    return TasaResponse(
        tasa=tasa_final,
        plazo_meses=plazo["plazo"],
        explicacion=explicacion
    )
    


#############################################################################
# ---- Tool 5: Auditora ---- #
#############################################################################
@tool
def auditar_respeto(mensaje: str, capacidad_pago: float, renta_mensual: float) -> Auditoria:
    """Audita de forma estricta que el mensaje cumpla con las normas de respeto, longitud y viabilidad financiera.

    Args:
        mensaje: El texto del mensaje final que redacto el agente para el cliente.
        capacidad_pago: La cuota mensual maxima que puede pagar el cliente (calculada previamente).
        renta_mensual: La cuota mensual calculada para el credito propuesto.
    """
    texto = mensaje.lower()
    motivos = []
    
    # 1. Validar palabras prohibidas
    encontradas = [p for p in _PALABRAS_PROHIBIDAS if p in texto]
    if encontradas:
        motivos.append(f"El mensaje contiene palabras no autorizadas o invasivas: {', '.join(encontradas)}")
        
    # 2. Validar longitud del mensaje (máximo 100 palabras)
    palabras = mensaje.split()
    if len(palabras) > 100:
        motivos.append(f"El mensaje excede el limite de 100 palabras (tiene {len(palabras)} palabras). Redacta una version mas corta.")
        
    # 3. Validar viabilidad financiera (Guardrail de Capacidad)
    if renta_mensual > capacidad_pago:
        motivos.append(
            f"La renta mensual propuesta (${renta_mensual}) supera la capacidad maxima de pago del cliente (${capacidad_pago}). "
            "Debes ajustar el monto a uno menor o ampliar el plazo si esta disponible."
        )
        
    # 4. Determinar aprobación
    aprobado = len(motivos) == 0
    
    return Auditoria(
        aprobado=aprobado,
        motivos=motivos
    )



#############################################################################
# ---- Tool 6: Calcular Renta ---- #
#############################################################################
@tool
def calcula_renta(monto:float,tasa:float,plazo:int) -> float:
    """Calcula la renta mensual de un credito.

    Args:
        monto: Monto del credito.
        tasa: Tasa de interes anual simple.
        plazo: Plazo del credito en meses.

    Returns:
        La renta mensual del credito.
    """
    # 1. Convertir la tasa anual (ej. 10) a decimal y luego a mensual
    r = (tasa / 100) / 12
    
    # 2. Fórmula de amortización francesa (Pagos iguales)
    # M = P * [r * (1 + r)^n] / [(1 + r)^n - 1]
    mensualidad = monto * (r * (1 + r)**plazo) / ((1 + r)**plazo - 1)
    
    return round(mensualidad,2)

#############################################################################
# ---- Tool 7: Calcular Monto Maximo Aprobado ---- #
#En las pruebas fallaba porque al tratar de calcular el monto maximo en iteraciones se loopeaba, gastaba mucho
# y era ineficiente, por lo que se decidio poner la función que calcule en automatico el monto maximo de credito.
#El agente ya no tendrá que calcular el monto maximo de credito, sino que la herramienta lo hará.
#############################################################################
@tool
def calcular_monto_maximo_aprobado(capacidad_pago: float, tasa: float, plazo: int) -> float:
    """Calcula el monto de credito maximo que el cliente puede solicitar segun su capacidad de pago.

    Args:
        capacidad_pago: La cuota mensual maxima que el cliente puede pagar.
        tasa: Tasa de interes anual simple.
        plazo: Plazo del credito en meses.
    """
    if capacidad_pago <= 0 or tasa <= 0 or plazo <= 0:
        return 0.0
        
    r = (tasa / 100) / 12
    
    # Fórmula de valor presente de una anualidad
    monto_maximo = capacidad_pago * (((1 + r)**plazo - 1) / (r * (1 + r)**plazo))
    
    return round(monto_maximo, 2)


#############################################################################
# Herramientasautorizadas que el agente ReAct puede decidir llamar
#############################################################################
TOOLS = [
    consultar_buro_de_credito,
    evaluar_riesgo,
    capacidad_de_pago,
    calcula_tasa,
    calcula_renta,
  calcular_monto_maximo_aprobado,     
    auditar_respeto
]
