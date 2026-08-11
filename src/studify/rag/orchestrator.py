"""Ensamblado del prompt maestro (Fase 3 del plan).

Junta las tres piezas que el sistema ya tenía por separado —el material curado
que devuelve `rag/retriever.py`, la configuración que produce `vark/rules.py` y
el objetivo curricular— en el único texto que ve el modelo.

Dos invariantes que este módulo existe para sostener:

**1. El prompt y la validación miran exactamente el mismo conjunto de
fragmentos.** `PromptMaestro` se lleva consigo los fragmentos que embebió, en
vez de que el llamador los pase por su cuenta al validador. Si fueran dos
listas distintas, la regla 5 («ningún `id_fragmento` citado fuera de los
inyectados») podría rechazar una cita legítima o —peor— dejar pasar una
inventada, y el proyecto entero se apoya en que esa comprobación sea exacta.

**2. La huella de caché depende de todo lo que cambia la salida, y de nada
más.** Está construida sobre los mismos valores que entran al prompt, así que
dos peticiones con la misma huella habrían producido el mismo prompt. Si el
docente cura material nuevo o el perfil cambia de tramo, la huella cambia sola.
"""

import hashlib
from collections.abc import Sequence
from dataclasses import dataclass

from studify.config import get_settings
from studify.db.models import ObjetivoAprendizaje
from studify.rag import prompts
from studify.rag.retriever import FragmentoRecuperado
from studify.vark.rules import ConfiguracionGenerada

# Tramo al que se redondea `palabras_texto` antes de entrar al prompt. Pedir
# «aproximadamente 247 palabras» y «aproximadamente 250» produce cápsulas
# indistinguibles, pero como la huella de caché se calcula sobre este valor, sin
# redondear casi cada estudiante tendría su propio tramo y el caché no serviría
# de nada: en una cohorte de 43 se pagarían 43 generaciones para el mismo tema.
TRAMO_PALABRAS = 10


class ErrorPrompt(Exception):
    """No se puede construir un prompt maestro con los datos entregados."""


@dataclass(frozen=True, slots=True)
class PromptMaestro:
    """El prompt listo, junto con todo lo necesario para validar su respuesta."""

    sistema: str
    usuario: str
    fragmentos: tuple[FragmentoRecuperado, ...]
    palabras_objetivo: int
    huella: str


def _redondear_palabras(palabras: int) -> int:
    return round(palabras / TRAMO_PALABRAS) * TRAMO_PALABRAS


def bloque_contexto(fragmentos: Sequence[FragmentoRecuperado]) -> str:
    """Los fragmentos curados, cada uno rotulado con el id que hay que citar."""
    if not fragmentos:
        raise ErrorPrompt(
            "no hay fragmentos validados para este objetivo: generar una cápsula "
            "sin material sería pedirle al modelo que responda de memoria, que es "
            "lo que el RAG estructurado existe para impedir"
        )

    partes = [
        prompts.FRAGMENTO.format(
            id_fragmento=f.id_fragmento,
            cita=f.cita,
            tipo=f.tipo,
            texto=f.texto.strip(),
        )
        for f in fragmentos
    ]
    return prompts.CONTEXTO.format(fragmentos="\n".join(partes))


def bloque_perfil(config: ConfiguracionGenerada, *, palabras_objetivo: int) -> str:
    """Qué construir, derivado de `configuracion_contenido` (nunca de la etiqueta)."""
    instrucciones = []
    for directiva in config.directivas:
        instruccion = prompts.INSTRUCCION_POR_DIRECTIVA.get(directiva)
        if instruccion is None:
            # Se levanta en vez de omitirla: una directiva sin instrucción es un
            # elemento del perfil que desaparece de la cápsula sin dejar rastro,
            # y el estudiante recibiría contenido menos adaptado sin que nadie
            # se entere. `tests/test_prompt_maestro.py` lo detecta antes.
            raise ErrorPrompt(
                f"la directiva '{directiva}' de vark/rules.py no tiene "
                f"instrucción en rag/prompts/maestro.py: la cápsula saldría sin "
                f"ese elemento y sin error visible"
            )
        instrucciones.append(instruccion)

    tono = prompts.DESCRIPCION_TONO.get(config.tono_narrativo, config.tono_narrativo)

    ajustes = get_settings()
    return prompts.PERFIL.format(
        palabras_texto=palabras_objetivo,
        palabras_min=ajustes.capsula_min_palabras,
        palabras_max=ajustes.capsula_max_palabras,
        recursos_visuales=config.recursos_visuales,
        componentes_practicos=config.componentes_practicos,
        tono=tono,
        directivas="\n".join(f"{i}. {t}" for i, t in enumerate(instrucciones, start=1)),
    )


def bloque_formato() -> str:
    """Esquema JSON, extensión y obligación de responder en español."""
    ajustes = get_settings()
    return prompts.FORMATO.format(
        esquema_json=prompts.ESQUEMA_JSON,
        palabras_min=ajustes.capsula_min_palabras,
        palabras_max=ajustes.capsula_max_palabras,
    )


def bloque_tarea(objetivo: ObjetivoAprendizaje) -> str:
    return prompts.TAREA.format(
        asignatura=objetivo.asignatura,
        unidad=objetivo.unidad,
        tema=objetivo.tema,
        descripcion=f"Descripción: {objetivo.descripcion}" if objetivo.descripcion else "",
    )


def huella(
    config: ConfiguracionGenerada,
    fragmentos: Sequence[FragmentoRecuperado],
    *,
    id_objetivo: int,
    modelo: str,
    palabras_objetivo: int,
) -> str:
    """Clave de caché: todo lo que cambia la cápsula, y nada más.

    El plan §4 la define como «(id_objetivo, hash de configuracion_contenido
    redondeada)». Se le agregan los fragmentos y el modelo porque ambos también
    cambian la salida: si el docente valida material nuevo, la cápsula cacheada
    dejó de reflejar el material disponible; y durante el bake-off la misma
    configuración se corre contra tres modelos distintos, que sin esto se
    pisarían entre sí en el caché.

    Los pesos continuos `C_*` **no** entran: no llegan al prompt, solo lo hacen
    los enteros que se derivan de ellos. Incluirlos daría una huella distinta
    para dos perfiles que producen exactamente el mismo prompt.
    """
    ids = ",".join(str(i) for i in sorted(f.id_fragmento for f in fragmentos))
    partes = [
        f"objetivo={id_objetivo}",
        f"modelo={modelo}",
        f"palabras={palabras_objetivo}",
        f"visuales={config.recursos_visuales}",
        f"practicos={config.componentes_practicos}",
        f"tono={config.tono_narrativo}",
        f"directivas={','.join(sorted(config.directivas))}",
        f"fragmentos={ids}",
    ]
    return hashlib.sha256("|".join(partes).encode("utf-8")).hexdigest()


def construir(
    *,
    objetivo: ObjetivoAprendizaje,
    fragmentos: Sequence[FragmentoRecuperado],
    config: ConfiguracionGenerada,
    modelo: str,
) -> PromptMaestro:
    """Arma el prompt maestro completo para un objetivo y un perfil."""
    palabras_objetivo = _redondear_palabras(config.palabras_texto)

    usuario = "\n\n".join(
        [
            bloque_tarea(objetivo),
            bloque_contexto(fragmentos),
            bloque_perfil(config, palabras_objetivo=palabras_objetivo),
            bloque_formato(),
        ]
    )

    return PromptMaestro(
        sistema=prompts.SISTEMA,
        usuario=usuario,
        fragmentos=tuple(fragmentos),
        palabras_objetivo=palabras_objetivo,
        huella=huella(
            config,
            fragmentos,
            id_objetivo=objetivo.id_objetivo,
            modelo=modelo,
            palabras_objetivo=palabras_objetivo,
        ),
    )
