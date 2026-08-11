"""Agrupación de bloques en fragmentos recuperables (tabla 17.7).

Es la decisión de diseño más consecuente de la Fase 2. Hashiyada et al. (2025)
advierten empíricamente que si los documentos inyectados en la base de
conocimiento no están rigurosamente fragmentados, el sistema termina ignorando
el material institucional y alucinando — el riesgo exacto que este proyecto
existe para evitar.

**Qué tamaño debe tener un fragmento.** La microcápsula se genera *a partir*
del fragmento y mide 150–300 palabras (cap. 11.1). De ahí salen los tres
umbrales:

- Un fragmento **demasiado corto** no alcanza a sostener 150 palabras de
  contenido fundamentado, y el LLM rellena inventando: es alucinación por
  falta de contexto, no por exceso.
- Un fragmento **demasiado largo** rompe la correspondencia «un fragmento ↔ un
  objetivo de aprendizaje» del cap. 12, mezcla temas y diluye el foco temático
  que el cap. 11.1 exige.
- El objetivo de ~180 palabras deja al generador margen para reescribir y
  adaptar al perfil VARK sin quedarse sin material ni sobrarle.

**Fronteras duras.** Un encabezado siempre abre fragmento nuevo, aunque el
anterior haya quedado corto: unir dos secciones distintas en un mismo fragmento
es precisamente lo que destruye la trazabilidad temática. Una tabla también va
sola, porque para un perfil visual es el recurso que pide la tabla 11.1 y
mezclarla con prosa la vuelve irrecuperable.
"""

import re
from dataclasses import dataclass

from studify.knowledge.extract import BloqueTexto

# Extensión objetivo de un fragmento, en palabras. Ver docstring del módulo.
OBJETIVO_PALABRAS = 180
MAX_PALABRAS = 350
# Por debajo de este umbral el fragmento no se emite solo: se fusiona con el
# vecino. Un fragmento de 20 palabras ocupa una fila, aparece en la curación y
# no aporta contexto suficiente para generar nada.
MIN_PALABRAS = 40

# `etiqueta_tematica` es VARCHAR(100) en la tabla 17.7.
MAX_LARGO_ETIQUETA = 100

# Corte de oración: punto/interrogación/exclamación seguidos de espacio y
# mayúscula. Se exige la mayúscula para no partir en abreviaturas ("Fig. 3",
# "et al.", "vs.") ni en decimales.
_FIN_ORACION = re.compile(r"(?<=[.!?])\s+(?=[A-ZÁÉÍÓÚÑ¿¡])")


@dataclass(frozen=True, slots=True)
class FragmentoCrudo:
    """Un fragmento listo para persistirse, antes de pasar por curación.

    Nace siempre en `estado_validacion = 'pendiente'` y con `id_objetivo` sin
    asignar: quién decide a qué objetivo pertenece y si el contenido sirve es
    una persona, no el ingestor (cap. 12, «revisión previa de documentos»).
    """

    numero: int
    texto: str
    pagina_inicio: int
    pagina_fin: int
    tipo: str = "texto"
    etiqueta_tematica: str | None = None

    @property
    def palabras(self) -> int:
        return len(self.texto.split())


def _contar(bloques: list[BloqueTexto]) -> int:
    return sum(len(b.texto.split()) for b in bloques)


def _dividir_por_oraciones(texto: str, maximo: int) -> list[str]:
    """Parte un bloque descomunal en trozos de a lo más `maximo` palabras.

    Se corta por oración y nunca a mitad de una: un fragmento que empieza en
    «...y por lo tanto el resultado es» no se puede citar como fuente ni
    verificar contra el documento original.

    Si una sola oración ya excede el máximo (tablas mal extraídas, párrafos sin
    puntuación), se emite igual en vez de trocearla a la fuerza. Es preferible
    un fragmento largo pero íntegro a uno cortado en seco.
    """
    oraciones = _FIN_ORACION.split(texto)
    trozos: list[str] = []
    actual: list[str] = []
    palabras_actual = 0

    for oracion in oraciones:
        n = len(oracion.split())
        if actual and palabras_actual + n > maximo:
            trozos.append(" ".join(actual))
            actual, palabras_actual = [], 0
        actual.append(oracion)
        palabras_actual += n

    if actual:
        trozos.append(" ".join(actual))
    return trozos


def _componer(titulo: str | None, cuerpo: str) -> str:
    """Antepone el encabezado vigente al cuerpo del fragmento.

    El título se guarda además en `etiqueta_tematica`, pero se repite dentro del
    texto a propósito: es contexto que el LLM necesita para saber de qué trata
    el material («Normalización de bases de datos» cambia por completo cómo se
    lee un párrafo sobre "formas"), y además alimenta el full-text search.
    """
    return f"{titulo}\n\n{cuerpo}" if titulo else cuerpo


def fragmentar(
    bloques: list[BloqueTexto],
    *,
    objetivo_palabras: int = OBJETIVO_PALABRAS,
    max_palabras: int = MAX_PALABRAS,
    min_palabras: int = MIN_PALABRAS,
) -> list[FragmentoCrudo]:
    """Bloques extraídos → fragmentos recuperables, numerados en orden."""
    fragmentos: list[FragmentoCrudo] = []
    acumulado: list[BloqueTexto] = []
    titulo_vigente: str | None = None

    def cerrar() -> None:
        """Emite lo acumulado como fragmento (o fragmentos, si excede el máximo)."""
        nonlocal acumulado
        if not acumulado:
            return

        cuerpo = " ".join(b.texto for b in acumulado)
        pagina_inicio = min(b.pagina for b in acumulado)
        pagina_fin = max(b.pagina for b in acumulado)

        for trozo in _dividir_por_oraciones(cuerpo, max_palabras):
            fragmentos.append(
                FragmentoCrudo(
                    numero=len(fragmentos) + 1,
                    texto=_componer(titulo_vigente, trozo),
                    pagina_inicio=pagina_inicio,
                    pagina_fin=pagina_fin,
                    etiqueta_tematica=(
                        titulo_vigente[:MAX_LARGO_ETIQUETA] if titulo_vigente else None
                    ),
                )
            )
        acumulado = []

    for bloque in bloques:
        if bloque.es_titulo:
            # Frontera dura: el encabezado cierra el tema anterior y pasa a ser
            # la etiqueta del siguiente.
            cerrar()
            titulo_vigente = bloque.texto
            continue

        if bloque.tipo != "texto":
            # Tablas y recursos estructurados van solos (ver docstring).
            cerrar()
            fragmentos.append(
                FragmentoCrudo(
                    numero=len(fragmentos) + 1,
                    texto=_componer(titulo_vigente, bloque.texto),
                    pagina_inicio=bloque.pagina,
                    pagina_fin=bloque.pagina,
                    tipo=bloque.tipo,
                    etiqueta_tematica=(
                        titulo_vigente[:MAX_LARGO_ETIQUETA] if titulo_vigente else None
                    ),
                )
            )
            continue

        # Si sumar este bloque desborda el máximo, se cierra antes de agregarlo:
        # así el corte cae en el límite natural entre bloques y no dentro de uno.
        if acumulado and _contar(acumulado) + len(bloque.texto.split()) > max_palabras:
            cerrar()

        acumulado.append(bloque)

        if _contar(acumulado) >= objetivo_palabras:
            cerrar()

    cerrar()
    return _fusionar_residuos(fragmentos, min_palabras, max_palabras)


def _fusionar_residuos(
    fragmentos: list[FragmentoCrudo], min_palabras: int, max_palabras: int
) -> list[FragmentoCrudo]:
    """Absorbe los fragmentos demasiado cortos en su vecino inmediato.

    Solo se fusionan fragmentos **del mismo tema y del mismo tipo**: unir el
    resto de una sección con el comienzo de la siguiente reintroduciría por la
    puerta trasera la mezcla de temas que `fragmentar` evita con las fronteras
    duras. Un residuo que no encuentra vecino compatible se conserva tal cual —
    prefiere un fragmento corto antes que uno incoherente, y de todas formas la
    curación humana puede descartarlo.
    """
    if not fragmentos:
        return []

    resultado: list[FragmentoCrudo] = []
    for frag in fragmentos:
        previo = resultado[-1] if resultado else None
        cabe = (
            previo is not None
            and previo.palabras < min_palabras
            and previo.tipo == frag.tipo == "texto"
            and previo.etiqueta_tematica == frag.etiqueta_tematica
            and previo.palabras + frag.palabras <= max_palabras
        )
        if cabe:
            # El título ya está incluido en el texto del previo; se le añade
            # solo el cuerpo del siguiente para no repetirlo.
            cuerpo_nuevo = frag.texto
            if frag.etiqueta_tematica and cuerpo_nuevo.startswith(frag.etiqueta_tematica):
                cuerpo_nuevo = cuerpo_nuevo[len(frag.etiqueta_tematica) :].lstrip()
            resultado[-1] = FragmentoCrudo(
                numero=previo.numero,
                texto=f"{previo.texto} {cuerpo_nuevo}".strip(),
                pagina_inicio=min(previo.pagina_inicio, frag.pagina_inicio),
                pagina_fin=max(previo.pagina_fin, frag.pagina_fin),
                tipo=previo.tipo,
                etiqueta_tematica=previo.etiqueta_tematica,
            )
            continue
        resultado.append(frag)

    # Renumerar: las fusiones dejaron huecos en la secuencia, y
    # `numero_fragmento` tiene UNIQUE(id_documento, numero_fragmento).
    return [
        FragmentoCrudo(
            numero=i,
            texto=f.texto,
            pagina_inicio=f.pagina_inicio,
            pagina_fin=f.pagina_fin,
            tipo=f.tipo,
            etiqueta_tematica=f.etiqueta_tematica,
        )
        for i, f in enumerate(resultado, start=1)
    ]
