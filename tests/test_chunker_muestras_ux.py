"""Regresión de tres defectos del chunker, con muestras reales de INF3246 (UX).

Las muestras son páginas recortadas de dos presentaciones exportadas a PDF:

- `ux06_p2-5_p12.pdf`: páginas 2, 3, 4, 5 y 12 de «06 - Técnicas de evaluación
  de la experiencia del usuario (Parte 2)».
- `ux07_p2-4_p23.pdf`: páginas 2, 3, 4 y 23 de «07 - Diseño de la experiencia
  del usuario».

Los defectos que cubren:

1. La página del título no contaba para `pagina_inicio`.
2. La firma repetida en cada diapositiva («Dra. … – correo») caía al comienzo
   de la página siguiente y estiraba `pagina_fin` una página de más.
3. Varios "títulos" seguidos (filas de tabla o rótulos en letra grande) se
   descartaban en silencio: solo sobrevivía el último. Se perdía ~13 % del texto.
"""

from pathlib import Path

import pymupdf
import pytest

from studify.knowledge.chunker import fragmentar
from studify.knowledge.extract import BloqueTexto, extraer, marcar_repetidos

FIXTURES = Path(__file__).parent / "fixtures"
MUESTRA_06 = FIXTURES / "ux06_p2-5_p12.pdf"
MUESTRA_07 = FIXTURES / "ux07_p2-4_p23.pdf"
# Página de la muestra (1..n) → página en el documento original.
PAGINAS_06 = {1: 2, 2: 3, 3: 4, 4: 5, 5: 12}
PAGINAS_07 = {1: 2, 2: 3, 3: 4, 4: 23}
FIRMA = "Dra. Daniela Quiñones Otey – daniela.quinones@pucv.cl"

# Las muestras son material del curso y Git ignora *.pdf: en un clon sin ellas
# los tests que las leen se omiten (las reglas aisladas del final siempre corren).
requiere_muestras = pytest.mark.skipif(
    not (MUESTRA_06.exists() and MUESTRA_07.exists()),
    reason="faltan las muestras PDF de tests/fixtures (ignoradas por Git)",
)


def _fragmentos(ruta: Path):
    return fragmentar(extraer(ruta))


def _por_etiqueta(frags, inicio: str):
    encontrados = [f for f in frags if (f.etiqueta_tematica or "").startswith(inicio)]
    assert len(encontrados) == 1, f"se esperaba un fragmento con etiqueta '{inicio}'"
    return encontrados[0]


def _paginas_originales(frag, mapa: dict[int, int]) -> tuple[int, int]:
    return mapa[frag.pagina_inicio], mapa[frag.pagina_fin]


# --- (a) el contenido de tablas y rótulos llega a los fragmentos -------------


@requiere_muestras
def test_tabla_de_la_p5_completa_en_un_solo_fragmento():
    frag = _por_etiqueta(_fragmentos(MUESTRA_06), "DIFERENCIA ENTRE EVALUACIÓN HEURÍSTICA")

    for fila in (
        "La realizan expertos Participan usuarios reales",
        "Basada en heurísticas Basada en comportamiento real",
        "Detecta problemas potenciales Detecta problemas reales",
        "Más rápida y barata Más costosa y lenta",
        "No requiere usuarios Sí requiere usuarios (participantes)",
        "No mide emociones reales",
    ):
        assert fila in frag.texto, f"falta la fila «{fila}»"


@requiere_muestras
def test_componentes_1_a_6_de_la_p12_en_los_fragmentos():
    frag = _por_etiqueta(_fragmentos(MUESTRA_06), "COMPONENTES DE UNA PRUEBA CON USUARIOS")

    for componente in (
        "PARTICIPANTES 1 Usuarios representativos",
        "TAREAS 2 Actividades a completar",
        "ESCENARIOS 3 Contexto de uso realista",
        "MODERADOR 4 Guía la sesión",
        "OBSERVADOR 5 Toman notas",
        "MÉTRICAS Y DATOS 6 Definir métricas y recopilar datos durante la prueba",
    ):
        assert componente in frag.texto, f"falta «{componente}»"


@requiere_muestras
def test_frase_destacada_de_la_p23_del_07_se_conserva_entera():
    frag = _por_etiqueta(_fragmentos(MUESTRA_07), "El principal desafío del")

    assert "equilibrar la velocidad del desarrollo ágil" in frag.texto
    assert "experiencias de calidad." in frag.texto


# --- (b) páginas correctas sin corrección posterior --------------------------


@requiere_muestras
@pytest.mark.parametrize(
    ("muestra", "mapa", "etiqueta", "esperado"),
    [
        (MUESTRA_06, PAGINAS_06, "PRUEBA CON USUARIOS", (2, 2)),
        (MUESTRA_06, PAGINAS_06, "PRUEBAS CON USUARIOS", (3, 3)),
        (MUESTRA_06, PAGINAS_06, "¿POR QUÉ REALIZAR PRUEBAS", (4, 4)),
        (MUESTRA_06, PAGINAS_06, "DIFERENCIA ENTRE EVALUACIÓN HEURÍSTICA", (5, 5)),
        (MUESTRA_06, PAGINAS_06, "COMPONENTES DE UNA PRUEBA", (12, 12)),
        (MUESTRA_07, PAGINAS_07, "DISEÑO UX", (2, 2)),
        # p3 y p4 comparten etiqueta y la p3 es corta: se fusionan, y el rango
        # cubre exactamente esas dos páginas.
        (MUESTRA_07, PAGINAS_07, "DISEÑO CENTRADO EN EL USUARIO", (3, 4)),
        (MUESTRA_07, PAGINAS_07, "DISEÑO ÁGIL UX", (23, 23)),
        (MUESTRA_07, PAGINAS_07, "El principal desafío del", (23, 23)),
    ],
)
def test_paginas_del_documento_original(muestra, mapa, etiqueta, esperado):
    frag = _por_etiqueta(_fragmentos(muestra), etiqueta)
    assert _paginas_originales(frag, mapa) == esperado


@requiere_muestras
def test_la_firma_repetida_se_detecta_y_no_estira_el_rango():
    bloques = extraer(MUESTRA_06)
    firmas = [b for b in bloques if b.texto == FIRMA]

    assert firmas and all(b.repetido for b in firmas)
    # Antes de la corrección este fragmento quedaba en pp. 2–3 por la firma de
    # la p3 pegada al final.
    frag = _por_etiqueta(fragmentar(bloques), "PRUEBA CON USUARIOS")
    assert frag.pagina_inicio == frag.pagina_fin


# --- (c) no se pierden bloques ----------------------------------------------


@requiere_muestras
@pytest.mark.parametrize("muestra", [MUESTRA_06, MUESTRA_07])
def test_ningun_bloque_extraido_queda_fuera_de_los_fragmentos(muestra):
    bloques = extraer(muestra)
    texto_total = "\n".join(f.texto for f in fragmentar(bloques))

    perdidos = [b.texto for b in bloques if b.texto not in texto_total]
    assert perdidos == []


@requiere_muestras
@pytest.mark.parametrize("muestra", [MUESTRA_06, MUESTRA_07])
def test_palabras_ingeridas_cercanas_al_total_del_pdf(muestra):
    """Antes de la corrección se perdía ~13 % del texto de estas presentaciones."""
    with pymupdf.open(muestra) as doc:
        palabras_pdf = sum(len(p.get_text().split()) for p in doc)

    bloques = extraer(muestra)
    texto_total = "\n".join(f.texto for f in fragmentar(bloques))
    palabras_ingeridas = sum(len(b.texto.split()) for b in bloques if b.texto in texto_total)

    assert palabras_ingeridas / palabras_pdf >= 0.98


# --- Reglas en aislamiento ---------------------------------------------------


def _cuerpo(palabras: int, pagina: int, palabra: str = "dato") -> BloqueTexto:
    return BloqueTexto(texto=" ".join([palabra] * palabras), pagina=pagina)


def test_racha_de_titulos_en_la_misma_pagina_queda_bajo_el_primero():
    bloques = [
        BloqueTexto("Comparación", 1, es_titulo=True),
        BloqueTexto("Fila uno", 1, es_titulo=True),
        BloqueTexto("Fila dos", 1, es_titulo=True),
        _cuerpo(50, 1),
    ]
    frags = fragmentar(bloques)

    assert len(frags) == 1
    assert frags[0].etiqueta_tematica == "Comparación"
    assert "Fila uno" in frags[0].texto and "Fila dos" in frags[0].texto


def test_titulo_tras_cuerpo_sigue_siendo_frontera_dura():
    bloques = [
        BloqueTexto("Tema A", 1, es_titulo=True),
        _cuerpo(50, 1, "alfa"),
        BloqueTexto("Tema B", 1, es_titulo=True),
        _cuerpo(50, 1, "beta"),
    ]
    frags = fragmentar(bloques)

    assert [f.etiqueta_tematica for f in frags] == ["Tema A", "Tema B"]


def test_la_pagina_del_titulo_cuenta_solo_para_el_primer_fragmento():
    bloques = [
        BloqueTexto("Tema", 1, es_titulo=True),
        _cuerpo(200, 2),
        _cuerpo(200, 3),
    ]
    frags = fragmentar(bloques)

    assert [(f.pagina_inicio, f.pagina_fin) for f in frags] == [(1, 2), (3, 3)]


def test_bloque_repetido_no_cuenta_para_el_rango_de_paginas():
    bloques = [
        BloqueTexto("Tema", 1, es_titulo=True),
        _cuerpo(50, 1),
        BloqueTexto("Pie corrido", 2, repetido=True),
    ]
    frag = fragmentar(bloques)[0]

    assert (frag.pagina_inicio, frag.pagina_fin) == (1, 1)
    assert "Pie corrido" in frag.texto, "el texto se conserva aunque no cuente para páginas"


def test_marcar_repetidos_exige_mayoria_de_paginas_y_respeta_titulos():
    bloques = [
        BloqueTexto("Pie", 1),
        BloqueTexto("Pie", 2),
        BloqueTexto("Pie", 3),
        BloqueTexto("Título", 1, es_titulo=True),
        BloqueTexto("Título", 2, es_titulo=True),
        BloqueTexto("Título", 3, es_titulo=True),
        BloqueTexto("Única vez", 2),
    ]
    marcados = {(b.texto, b.pagina): b.repetido for b in marcar_repetidos(bloques)}

    assert marcados[("Pie", 1)] and marcados[("Pie", 3)]
    assert not marcados[("Título", 1)], "un título repetido sigue siendo etiqueta"
    assert not marcados[("Única vez", 2)]


def test_marcar_repetidos_no_actua_con_menos_de_tres_paginas():
    bloques = [BloqueTexto("Pie", 1), BloqueTexto("Pie", 2)]
    assert not any(b.repetido for b in marcar_repetidos(bloques))
