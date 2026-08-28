"""Simulador VARK del docente: la cápsula de un perfil puro (Fase 5).

Movido desde `web/routers/teacher.py` en la migración a React. La única
diferencia con el original es que acá **no se preparan los bloques para la
plantilla**: la columna devuelve la `Microcapsula` tal cual, y cada transporte
(Jinja o JSON) la adapta a lo suyo. Así el cálculo no arrastra decisiones de
presentación.
"""

from decimal import Decimal

from sqlalchemy.orm import Session

from studify.config import get_settings
from studify.db.models import ObjetivoAprendizaje
from studify.generation.generator import ClienteLLM, ErrorGeneracion, generar
from studify.rag import orchestrator, retriever
from studify.vark.rules import aplicar_reglas
from studify.vark.scoring import CANALES, PerfilVark
from studify.web import textos


def perfil_puro(canal_vark: str) -> PerfilVark:
    """Perfil VARK sintético: 100% en un canal, 0% en los otros tres.

    Es una simplificación deliberada del simulador (ninguno de los 43
    diagnósticos reales tiene este vector): sirve para forzar al máximo la
    directiva de un solo canal y ver si el prompt la traduce en algo distinto
    en la cápsula, no para reproducir un perfil real de estudiante.
    """
    porcentajes = {c: Decimal(100 if c == canal_vark else 0) for c in CANALES}
    return PerfilVark(
        v=porcentajes["V"], a=porcentajes["A"], r=porcentajes["R"], k=porcentajes["K"]
    )


def generar_capsula_pura(
    db: Session,
    objetivo: ObjetivoAprendizaje,
    canal_vark: str,
    cliente: ClienteLLM,
) -> dict:
    """Una columna del simulador: la cápsula para un perfil puro, o el motivo del fallo.

    Se usa tanto para generar un canal suelto como para comparar los cuatro,
    para que ambas rutas produzcan exactamente la misma cápsula ante el mismo
    canal — si divergieran, la comparación de a cuatro podría mostrar algo
    distinto de lo que el docente ya vio al probar un canal suelto.
    """
    perfil = perfil_puro(canal_vark)
    config = aplicar_reglas(perfil)

    fragmentos = retriever.recuperar(
        db,
        id_objetivo=objetivo.id_objetivo,
        canal_primario=config.jerarquia.canal_primario,
    )

    try:
        prompt = orchestrator.construir(
            objetivo=objetivo,
            fragmentos=fragmentos,
            config=config,
            modelo=get_settings().llm_model,
        )
        resultado = generar(prompt, cliente=cliente)
    except orchestrator.ErrorPrompt as exc:
        return columna_error(canal_vark, f"Error de material: {exc}")
    except ErrorGeneracion as exc:
        return columna_error(canal_vark, f"Falló la generación: {exc}")

    capsula = resultado.capsula
    return {
        "canal": canal_vark,
        "nombre_canal": textos.NOMBRE_CANAL[canal_vark],
        "color_canal": textos.COLOR_CANAL[canal_vark],
        "capsula": capsula,
        "palabras": capsula.palabras_contenido(),
        "error": None,
    }


def columna_error(canal_vark: str, mensaje: str) -> dict:
    """Misma forma que una columna exitosa, para que quien la consuma no tenga
    que distinguir dos estructuras distintas — solo revisa `error`."""
    return {
        "canal": canal_vark,
        "nombre_canal": textos.NOMBRE_CANAL[canal_vark],
        "color_canal": textos.COLOR_CANAL[canal_vark],
        "capsula": None,
        "palabras": None,
        "error": mensaje,
    }
