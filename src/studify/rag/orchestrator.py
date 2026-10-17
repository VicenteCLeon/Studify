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

**2. La huella de caché depende de lo que entra al prompt.** Material, texto
de los fragmentos, objetivo, plantillas, tramo del perfil y modelo: si el
docente cura o corrige material, si cambia el prompt o si el perfil cambia de
tramo, la huella cambia sola. La única excepción deliberada son los pesos
`C_*`, que van al prompt pero no a la huella para que el caché se comparta por
tramo (ver `huella`).
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

# Cuánto se le pide al modelo por debajo del máximo duro cuando el objetivo de
# palabras queda pegado al techo. Encontrado el 24-ago-2026 investigando el
# pendiente n.º 15 de AVANCE.md: `vark/rules._palabras_objetivo` interpola
# linealmente entre 150 y 300, y el perfil lector-escritor puro tiene C_texto en
# su máximo (0.75 de 0.75), así que su objetivo cae exactamente en 300 — el
# mismo número que `capsula_max_palabras`. Pedirle al modelo "apunta a 300, no
# pases de 300" no le deja ningún margen para la variación normal de redacción,
# y es justo el perfil que más se pasa: en una corrida de verificación contra el
# modelo real, R falló la validación 3 de 4 veces por exceso de palabras
# mientras V, A y K —cuyo objetivo siempre queda por debajo del máximo— no
# fallaron ninguna. Los demás perfiles no se acercan a este umbral (el segundo
# más alto, el lector-escritor casi puro, ronda 280–290), así que el margen no
# les cambia nada. No se toca `vark/rules.py`: el objetivo persistido en
# `configuracion_contenido.palabras_texto` (tabla 17.4, aprobado por el equipo
# el 06-ago-2026) sigue siendo 150–300 tal cual; esto ajusta solo lo que ve el
# modelo en el prompt.
MARGEN_PALABRAS_OBJETIVO = 30


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
        # Los C_* del cap. 11.2 se muestran redondeados a un decimal: el modelo
        # no hace nada distinto con 22,75 que con 22,8, y la cifra larga invita
        # a que la copie tal cual dentro del texto de la cápsula.
        peso_texto=f"{config.pesos.texto:.1f}",
        peso_visual=f"{config.pesos.visual:.1f}",
        peso_narrativo=f"{config.pesos.narrativo:.1f}",
        peso_practico=f"{config.pesos.practico:.1f}",
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


def _sha(texto: str) -> str:
    return hashlib.sha256(texto.encode("utf-8")).hexdigest()


def _huella_plantillas() -> str:
    """El texto fijo del prompt: reglas, secuencia, esquema, instrucciones y tonos.

    Se calcula en cada llamada a partir de las propias plantillas, y no con un
    número de versión a mano, para que ninguna corrección del prompt dependa
    de que alguien se acuerde de subirlo.
    """
    ajustes = get_settings()
    partes = [
        prompts.SISTEMA,
        prompts.SECUENCIA,
        prompts.ESQUEMA_JSON,
        prompts.CONTEXTO.template,
        prompts.FRAGMENTO.template,
        prompts.PERFIL.template,
        prompts.FORMATO.template,
        prompts.TAREA.template,
        *(f"{k}={v}" for k, v in sorted(prompts.INSTRUCCION_POR_DIRECTIVA.items())),
        *(f"{k}={v}" for k, v in sorted(prompts.DESCRIPCION_TONO.items())),
        f"rango={ajustes.capsula_min_palabras}-{ajustes.capsula_max_palabras}",
    ]
    return _sha("\x1f".join(partes))


def huella(
    config: ConfiguracionGenerada,
    fragmentos: Sequence[FragmentoRecuperado],
    *,
    objetivo: ObjetivoAprendizaje,
    modelo: str,
    palabras_objetivo: int,
) -> str:
    """Clave de caché: todo lo que entra al prompt, salvo los pesos `C_*`.

    El plan §4 la define como «(id_objetivo, hash de configuracion_contenido
    redondeada)». Se le agregan:

    - **los fragmentos con su contenido** —id, tipo, procedencia y texto—, no
      solo sus ids. Material nuevo cambia la cápsula, y también corregir el
      texto de un fragmento ya validado (`curation.editar_texto`): con solo los
      ids se seguía sirviendo la cápsula escrita sobre el texto viejo. Se
      ordenan por id, porque los mismos fragmentos son el mismo material;
    - **el objetivo tal como aparece en la tarea** (asignatura, unidad, tema y
      descripción);
    - **las plantillas del prompt** (`_huella_plantillas`): sin ellas, una
      corrección del prompt no llegaba a ningún tramo que ya tuviera cápsula;
    - **el modelo**: durante el bake-off la misma configuración se corre contra
      tres modelos, que sin esto se pisarían en el caché.

    **La excepción deliberada son los pesos continuos `C_*`.** Sí llegan al
    prompt (bloque «Perfil de representación», H13), pero si entraran a la
    huella casi cada estudiante tendría la suya y el caché compartido por tramo
    dejaría de servir. Dos perfiles con la misma huella reciben el mismo prompt
    salvo esas cuatro cifras (`test_misma_huella_es_el_mismo_prompt_salvo_los_pesos`).
    """
    material = "\x1e".join(
        f"{f.id_fragmento}\x1f{f.tipo}\x1f{f.cita}\x1f{_sha(f.texto.strip())}"
        for f in sorted(fragmentos, key=lambda f: f.id_fragmento)
    )
    partes = [
        f"objetivo={objetivo.id_objetivo}",
        f"tarea={_sha(bloque_tarea(objetivo))}",
        f"modelo={modelo}",
        f"palabras={palabras_objetivo}",
        f"visuales={config.recursos_visuales}",
        f"practicos={config.componentes_practicos}",
        f"tono={config.tono_narrativo}",
        f"directivas={','.join(sorted(config.directivas))}",
        f"fragmentos={_sha(material)}",
        f"plantillas={_huella_plantillas()}",
    ]
    return _sha("|".join(partes))


def construir(
    *,
    objetivo: ObjetivoAprendizaje,
    fragmentos: Sequence[FragmentoRecuperado],
    config: ConfiguracionGenerada,
    modelo: str,
) -> PromptMaestro:
    """Arma el prompt maestro completo para un objetivo y un perfil."""
    ajustes = get_settings()
    palabras_objetivo = max(
        ajustes.capsula_min_palabras,
        min(
            _redondear_palabras(config.palabras_texto),
            ajustes.capsula_max_palabras - MARGEN_PALABRAS_OBJETIVO,
        ),
    )

    usuario = "\n\n".join(
        [
            bloque_tarea(objetivo),
            bloque_contexto(fragmentos),
            # La secuencia va antes del perfil: primero qué construir (los siete
            # pasos, iguales para todos), después cómo adaptarlo a este
            # estudiante. Al revés, las instrucciones de perfil quedarían sin
            # referente porque el modelo aún no sabe qué secciones existen.
            prompts.SECUENCIA,
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
            objetivo=objetivo,
            modelo=modelo,
            palabras_objetivo=palabras_objetivo,
        ),
    )
