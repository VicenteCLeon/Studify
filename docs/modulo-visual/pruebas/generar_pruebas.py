"""Prueba práctica del módulo Visual (Fase 5 de `analisis-modulo-visual.md`).

Toma las especificaciones JSON de `specs/` —el mismo contrato que produciría el
paso LLM— y genera, con la MISMA entrada:

    1. el esquema determinístico (SVG dibujado por plantillas, sin modelo de imagen);
    2. el prompt de imagen que se le enviaría a cada API (`resultados/prompts/`);
    3. opcionalmente, la imagen de cada candidato de pago.

**Por defecto no gasta nada.** Sin argumentos hace 1 y 2, que son locales, y
muestra el plan de las llamadas pagadas con su costo estimado. Las llamadas
reales exigen `--pagadas --confirmo-usd <monto>`, con un monto que cubra el
estimado y no pase de `TOPE_USD`: así el gasto lo confirma una persona que vio
la cifra, no el script.

Uso (desde la raíz del repo, con el venv del proyecto):

    python docs/modulo-visual/pruebas/generar_pruebas.py
    python docs/modulo-visual/pruebas/generar_pruebas.py --pagadas --confirmo-usd 0.80
    python docs/modulo-visual/pruebas/generar_pruebas.py --pagadas --solo gemini --confirmo-usd 0.15

Las API keys se leen del entorno o del `.env` de la raíz y nunca se imprimen.

⚠️ Los cuatro adaptadores de pago están escritos contra la documentación oficial
leída el 10-oct-2026, pero **ninguno se ejecutó**: no había keys. Lo que se dejó
anotado como «sin verificar» en cada uno hay que confirmarlo en la primera corrida.
"""

import argparse
import base64
import json
import math
import os
import sys
import time
from collections.abc import Callable
from dataclasses import dataclass
from html import escape
from pathlib import Path

AQUI = Path(__file__).resolve().parent
RAIZ = AQUI.parents[2]
SPECS = AQUI / "specs"
RESULTADOS = AQUI / "resultados"

# Tope de gasto de la prueba completa, fijado por el equipo.
TOPE_USD = 3.00

TIPOS = (
    "mapa_conceptual",
    "flujo",
    "comparacion",
    "linea_de_tiempo",
    "jerarquia",
    "ciclo",
    "causa_efecto",
)
ROLES = ("principal", "secundario", "resultado", "decision")

MIN_NODOS, MAX_NODOS = 3, 7
MAX_PALABRAS_TITULO = 6
MAX_PALABRAS_ETIQUETA = 4
MAX_PALABRAS_DETALLE = 8
MAX_PALABRAS_VERBO = 3


# --- Contrato ------------------------------------------------------------------


def validar(spec: dict) -> list[str]:
    """Los mismos límites que el paso LLM debe cumplir; lista vacía si está bien.

    Se cuentan palabras con `split()`, igual que `generation/schemas.py`: es lo
    que mide cuánto texto cabe en una caja, que es lo que el límite protege.
    """
    errores: list[str] = []
    if spec.get("tipo_de_diagrama") not in TIPOS:
        errores.append(f"tipo_de_diagrama desconocido: {spec.get('tipo_de_diagrama')!r}")
    if len(str(spec.get("titulo", "")).split()) > MAX_PALABRAS_TITULO:
        errores.append(f"el título pasa de {MAX_PALABRAS_TITULO} palabras")
    if not str(spec.get("titulo", "")).strip():
        errores.append("falta el título")

    nodos = spec.get("nodos") or []
    if not MIN_NODOS <= len(nodos) <= MAX_NODOS:
        errores.append(f"hay {len(nodos)} nodos; deben ser entre {MIN_NODOS} y {MAX_NODOS}")
    ids = [n.get("id") for n in nodos]
    if len(set(ids)) != len(ids):
        errores.append("hay ids de nodo repetidos")
    for n in nodos:
        if len(str(n.get("etiqueta", "")).split()) > MAX_PALABRAS_ETIQUETA:
            errores.append(f"la etiqueta de {n.get('id')} pasa de {MAX_PALABRAS_ETIQUETA} palabras")
        if not str(n.get("etiqueta", "")).strip():
            errores.append(f"el nodo {n.get('id')} no tiene etiqueta")
        if len(str(n.get("detalle") or "").split()) > MAX_PALABRAS_DETALLE:
            errores.append(f"el detalle de {n.get('id')} pasa de {MAX_PALABRAS_DETALLE} palabras")
        if n.get("rol", "secundario") not in ROLES:
            errores.append(f"rol desconocido en {n.get('id')}: {n.get('rol')!r}")
        if spec.get("tipo_de_diagrama") == "comparacion" and not n.get("grupo"):
            errores.append(f"en una comparación cada nodo necesita `grupo` ({n.get('id')})")

    for r in spec.get("relaciones") or []:
        if r.get("desde") not in ids or r.get("hacia") not in ids:
            errores.append(f"relación con un nodo inexistente: {r.get('desde')} → {r.get('hacia')}")
        if len(str(r.get("verbo", "")).split()) > MAX_PALABRAS_VERBO:
            errores.append(f"el verbo «{r.get('verbo')}» pasa de {MAX_PALABRAS_VERBO} palabras")
    if spec.get("tipo_de_diagrama") != "comparacion" and not spec.get("relaciones"):
        errores.append("un diagrama sin relaciones no muestra estructura")
    if not str(spec.get("texto_alternativo", "")).strip():
        errores.append("falta `texto_alternativo` (lo leen los lectores de pantalla)")
    return errores


# --- Paso 2: del JSON al prompt de imagen ---------------------------------------

# El andamio va en inglés y los rótulos, literales, en español. Es la convención
# que mejor siguen los modelos de imagen; la alternativa (todo en español) queda
# como variable a comparar cuando haya keys.
DISPOSICION = {
    "mapa_conceptual": (
        "concept map: the main concept at the top, related concepts below it, "
        "connected by labeled arrows"
    ),
    "flujo": "process flowchart: the steps in order from left to right, connected by arrows",
    "comparacion": (
        "side-by-side comparison: one column per group with its header on top and "
        "its items stacked below"
    ),
    "linea_de_tiempo": "horizontal timeline: milestones in order from left to right",
    "jerarquia": "hierarchy tree: the root at the top, its children below, connected by lines",
    "ciclo": "cycle diagram: the stages placed around a circle, connected clockwise by arrows",
    "causa_efecto": (
        "cause-and-effect diagram: causes on the left, effects on the right, connected by arrows"
    ),
}

ENFASIS = {
    "principal": "the most prominent box, filled with the main color",
    "secundario": "a regular box with a light fill",
    "resultado": "highlighted with the accent color",
    "decision": "drawn as a diamond",
}

PALETAS = {
    # Los tokens de `web/static/css/app.css`: el esquema usa los colores del sitio.
    "studify": {
        "fondo": "#FBF8F3", "superficie": "#FFFFFF", "borde": "#D3C9B8",
        "texto": "#1F2933", "suave": "#56606B",
        "primario": "#0F766E", "primario_suave": "#E3F4F1",
        "acento": "#F2795A", "acento_suave": "#FDEBE5",
    },
    "azul": {
        "fondo": "#FBF8F3", "superficie": "#FFFFFF", "borde": "#D3C9B8",
        "texto": "#1F2933", "suave": "#56606B",
        "primario": "#1E52B8", "primario_suave": "#E7EFFD",
        "acento": "#C27D0E", "acento_suave": "#FDF2DD",
    },
    "violeta": {
        "fondo": "#FBF8F3", "superficie": "#FFFFFF", "borde": "#D3C9B8",
        "texto": "#1F2933", "suave": "#56606B",
        "primario": "#5D37B5", "primario_suave": "#F0EAFC",
        "acento": "#1F9D61", "acento_suave": "#E2F4EA",
    },
}


def construir_prompt(spec: dict, *, compacto: bool = False) -> str:
    """Convierte la especificación en el prompt de imagen.

    `detalle` no entra: cada palabra de más es una oportunidad de error
    ortográfico, y el texto largo ya lo muestra la cápsula. El modo `compacto`
    quita las pistas de énfasis, para los modelos con prompt corto.
    """
    pal = PALETAS.get(spec.get("paleta", "studify"), PALETAS["studify"])
    por_id = {n["id"]: n for n in spec["nodos"]}

    cajas = []
    for i, n in enumerate(spec["nodos"], start=1):
        linea = f'{i}. "{n["etiqueta"]}"'
        if n.get("grupo"):
            linea += f' (under the header "{n["grupo"]}")'
        if not compacto:
            linea += f" — {ENFASIS[n.get('rol', 'secundario')]}"
        cajas.append(linea)

    flechas = [
        f'- from "{por_id[r["desde"]]["etiqueta"]}" to "{por_id[r["hacia"]]["etiqueta"]}", '
        f'labeled "{r["verbo"]}"'
        for r in spec.get("relaciones", [])
    ]

    partes = [
        "Flat vector infographic diagram for a university study app.",
        f"Diagram type: {DISPOSICION[spec['tipo_de_diagrama']]}.",
        f'Title at the top, exactly: "{spec["titulo"]}".',
        f"The diagram has exactly {len(cajas)} boxes. Each box contains ONLY the text in quotes:",
        "\n".join(cajas),
    ]
    if flechas:
        partes += [
            f"Draw exactly these {len(flechas)} arrows, each with its small label in quotes:",
            "\n".join(flechas),
        ]
    partes += [
        "Text rules: every visible word is Spanish. Copy each quoted string character by "
        "character, keeping accents (á é í ó ú), ñ and the opening marks ¿ ¡. Do not "
        "translate, abbreviate or reword. Do not add any other text, numbers, captions, "
        "legends, logos or watermarks. Bold sans-serif lettering, large and dark.",
        f"Style: clean flat design, simple geometric shapes, rounded rectangles, thin arrows, "
        f"generous spacing, light background {pal['fondo']}, main color {pal['primario']}, "
        f"accent color {pal['acento']}, text color {pal['texto']}, high contrast.",
        "No photographs, no realistic people, no faces, no 3D, no gradients, no shadows, "
        "no decorative clutter.",
        "Landscape 4:3 layout with even margins; nothing cropped or overlapping.",
    ]
    return "\n".join(partes)


# --- Render determinístico -------------------------------------------------------

ANCHO = 800
MARGEN = 32
Y_TITULO = 58
Y_CONTENIDO = 112
FUENTE = "Figtree, 'Segoe UI', system-ui, -apple-system, Roboto, sans-serif"
FUENTE_TITULO = "Fraunces, Georgia, 'Times New Roman', serif"


@dataclass
class Caja:
    nodo: dict
    cx: float
    cy: float
    w: float
    h: float
    lineas: list[str]
    lineas_detalle: list[str]
    tam: int
    tam_detalle: int


def _partir(texto: str, ancho_px: float, tam: int, *, negrita: bool = False) -> list[str]:
    """Corta el texto en líneas que caben en `ancho_px`.

    Sin métricas de fuente: se estima el ancho medio del carácter. Alcanza
    porque el contrato limita las etiquetas a 4 palabras; con texto libre no.
    """
    por_linea = max(4, int(ancho_px / (tam * (0.60 if negrita else 0.53))))
    lineas: list[str] = []
    actual = ""
    for palabra in texto.split():
        candidata = f"{actual} {palabra}".strip()
        if len(candidata) <= por_linea or not actual:
            actual = candidata
        else:
            lineas.append(actual)
            actual = palabra
    if actual:
        lineas.append(actual)
    return lineas


def _medir(nodo: dict, w: float) -> Caja:
    tam = 19 if w >= 200 else 17 if w >= 160 else 15
    tam_detalle = 14 if w >= 160 else 13
    lineas = _partir(nodo["etiqueta"], w - 28, tam, negrita=True)
    detalle = _partir(nodo.get("detalle") or "", w - 28, tam_detalle)
    h = 28 + len(lineas) * tam * 1.25
    if detalle:
        h += 6 + len(detalle) * tam_detalle * 1.3
    return Caja(nodo, 0, 0, w, h, lineas, detalle, tam, tam_detalle)


def _emparejar(cajas: list[Caja]) -> float:
    """Les da a las cajas la altura de la más alta: la retícula se ve pareja."""
    alto = max(c.h for c in cajas)
    for c in cajas:
        c.h = alto
    return alto


def _cajas(nodos: list[dict], w: float, *, parejas: bool = True) -> dict[str, Caja]:
    cajas = {n["id"]: _medir(n, w) for n in nodos}
    if parejas:
        _emparejar(list(cajas.values()))
    return cajas


def _svg_caja(c: Caja, pal: dict) -> str:
    rol = c.nodo.get("rol", "secundario")
    relleno, trazo, tinta, tinta_det, extra = {
        "principal": (pal["primario"], pal["primario"], "#FFFFFF", "#FFFFFF", ""),
        "secundario": (pal["superficie"], pal["borde"], pal["texto"], pal["suave"], ""),
        "resultado": (pal["acento_suave"], pal["acento"], pal["texto"], pal["suave"], ""),
        "decision": (
            pal["primario_suave"], pal["primario"], pal["texto"], pal["suave"],
            ' stroke-dasharray="7 5"',
        ),
    }[rol]
    partes = [
        f'<rect x="{c.cx - c.w / 2:.1f}" y="{c.cy - c.h / 2:.1f}" width="{c.w:.1f}" '
        f'height="{c.h:.1f}" rx="14" fill="{relleno}" stroke="{trazo}" stroke-width="2"{extra}/>'
    ]
    alto_texto = len(c.lineas) * c.tam * 1.25
    if c.lineas_detalle:
        alto_texto += 6 + len(c.lineas_detalle) * c.tam_detalle * 1.3
    y = c.cy - alto_texto / 2 + c.tam * 0.95
    for linea in c.lineas:
        partes.append(
            f'<text x="{c.cx:.1f}" y="{y:.1f}" text-anchor="middle" font-size="{c.tam}" '
            f'font-weight="700" fill="{tinta}">{escape(linea)}</text>'
        )
        y += c.tam * 1.25
    y += 6 - (c.tam * 0.95 - c.tam_detalle * 0.95)
    for linea in c.lineas_detalle:
        partes.append(
            f'<text x="{c.cx:.1f}" y="{y:.1f}" text-anchor="middle" '
            f'font-size="{c.tam_detalle}" fill="{tinta_det}">{escape(linea)}</text>'
        )
        y += c.tam_detalle * 1.3
    return "\n".join(partes)


def _borde(c: Caja, hacia_x: float, hacia_y: float, holgura: float = 4) -> tuple[float, float]:
    """Punto donde el segmento centro→(x, y) cruza el borde de la caja."""
    dx, dy = hacia_x - c.cx, hacia_y - c.cy
    if dx == 0 and dy == 0:
        return c.cx, c.cy
    tx = (c.w / 2 + holgura) / abs(dx) if dx else math.inf
    ty = (c.h / 2 + holgura) / abs(dy) if dy else math.inf
    t = min(tx, ty)
    return c.cx + dx * t, c.cy + dy * t


def _rotulo(x: float, y: float, texto: str, pal: dict, *, ancla: str = "middle") -> str:
    """El verbo de una relación, sobre un fondo que tapa la línea que cruza."""
    if not texto:
        return ""
    ancho = len(texto) * 13 * 0.56 + 14
    x0 = x - ancho / 2 if ancla == "middle" else x - 7
    return (
        f'<rect x="{x0:.1f}" y="{y - 11:.1f}" width="{ancho:.1f}" height="22" rx="11" '
        f'fill="{pal["fondo"]}"/>'
        f'<text x="{x:.1f}" y="{y + 4.5:.1f}" text-anchor="{ancla}" font-size="13" '
        f'font-style="italic" fill="{pal["suave"]}">{escape(texto)}</text>'
    )


def _punta(x: float, y: float, angulo: float, pal: dict) -> str:
    """La punta de una flecha, como polígono y no como `<marker>`.

    Los marcadores dependen del visor: el rasterizador de PyMuPDF, por ejemplo,
    no los dibuja y la flecha queda como una línea sin dirección.
    """
    largo, apertura = 12, 0.42
    puntos = [(x, y)] + [
        (x - largo * math.cos(angulo + s), y - largo * math.sin(angulo + s))
        for s in (-apertura, apertura)
    ]
    return (
        f'<polygon points="{" ".join(f"{px:.1f},{py:.1f}" for px, py in puntos)}" '
        f'fill="{pal["suave"]}"/>'
    )


def _flecha(x1: float, y1: float, x2: float, y2: float, pal: dict) -> str:
    angulo = math.atan2(y2 - y1, x2 - x1)
    # La línea termina dentro de la punta, para que no asome por delante.
    fx, fy = x2 - 8 * math.cos(angulo), y2 - 8 * math.sin(angulo)
    return (
        f'<line x1="{x1:.1f}" y1="{y1:.1f}" x2="{fx:.1f}" y2="{fy:.1f}" '
        f'stroke="{pal["suave"]}" stroke-width="2"/>'
    ) + _punta(x2, y2, angulo, pal)


def _union_recta(a: Caja, b: Caja, verbo: str, pal: dict) -> str:
    x1, y1 = _borde(a, b.cx, b.cy)
    x2, y2 = _borde(b, a.cx, a.cy)
    return _flecha(x1, y1, x2, y2, pal) + _rotulo((x1 + x2) / 2, (y1 + y2) / 2, verbo, pal)


def _verbos(spec: dict) -> dict[tuple[str, str], str]:
    return {(r["desde"], r["hacia"]): r.get("verbo", "") for r in spec.get("relaciones", [])}


def _cadena(spec: dict, pal: dict) -> tuple[str, float]:
    """`flujo` y `linea_de_tiempo`: una columna, en el orden de `nodos`.

    Vertical a propósito: en un teléfono el visor mide ~360 px de ancho, y una
    fila de cinco cajas dejaría el texto ilegible.
    """
    es_tiempo = spec["tipo_de_diagrama"] == "linea_de_tiempo"
    nodos = spec["nodos"]
    w, cx = (520, 500) if es_tiempo else (460, ANCHO / 2 + 20)
    cajas = _cajas(nodos, w)
    verbos = _verbos(spec)
    separacion = 52
    partes: list[str] = []

    y = Y_CONTENIDO
    for n in nodos:
        c = cajas[n["id"]]
        c.cx, c.cy = cx, y + c.h / 2
        y += c.h + separacion
    alto = y - separacion + MARGEN

    x_guia = cx - w / 2 - 38
    if es_tiempo:
        primero, ultimo = cajas[nodos[0]["id"]], cajas[nodos[-1]["id"]]
        partes.append(
            f'<line x1="{x_guia}" y1="{primero.cy:.1f}" x2="{x_guia}" y2="{ultimo.cy:.1f}" '
            f'stroke="{pal["borde"]}" stroke-width="4" stroke-linecap="round"/>'
        )
    for i, n in enumerate(nodos):
        c = cajas[n["id"]]
        if es_tiempo:
            partes.append(
                f'<circle cx="{x_guia}" cy="{c.cy:.1f}" r="9" fill="{pal["primario"]}"/>'
                f'<text x="{x_guia - 20}" y="{c.cy + 5:.1f}" text-anchor="end" font-size="15" '
                f'font-weight="700" fill="{pal["texto"]}">{escape(str(n.get("grupo", "")))}</text>'
            )
        else:
            partes.append(
                f'<circle cx="{x_guia}" cy="{c.cy:.1f}" r="17" fill="{pal["primario_suave"]}" '
                f'stroke="{pal["primario"]}" stroke-width="2"/>'
                f'<text x="{x_guia}" y="{c.cy + 5.5:.1f}" text-anchor="middle" font-size="16" '
                f'font-weight="700" fill="{pal["primario"]}">{i + 1}</text>'
            )
        partes.append(_svg_caja(c, pal))
        if i + 1 < len(nodos):
            sig = cajas[nodos[i + 1]["id"]]
            y1, y2 = c.cy + c.h / 2 + 4, sig.cy - sig.h / 2 - 4
            partes.append(_flecha(cx, y1, cx, y2, pal))
            partes.append(
                _rotulo(cx + 16, (y1 + y2) / 2, verbos.get((n["id"], nodos[i + 1]["id"]), ""),
                        pal, ancla="start")
            )
    return "\n".join(partes), alto


def _ciclo(spec: dict, pal: dict) -> tuple[str, float]:
    nodos = spec["nodos"]
    n = len(nodos)
    cajas = _cajas(nodos, 210 if n <= 4 else 180 if n == 5 else 150)
    alto = 660
    cx, cy = ANCHO / 2, Y_CONTENIDO + (alto - Y_CONTENIDO - MARGEN) / 2
    rx = ANCHO / 2 - MARGEN - max(c.w for c in cajas.values()) / 2
    ry = (alto - Y_CONTENIDO - MARGEN) / 2 - max(c.h for c in cajas.values()) / 2
    for i, nodo in enumerate(nodos):
        angulo = -math.pi / 2 + 2 * math.pi * i / n
        cajas[nodo["id"]].cx = cx + rx * math.cos(angulo)
        cajas[nodo["id"]].cy = cy + ry * math.sin(angulo)
    partes = [_union_recta(cajas[a], cajas[b], v, pal) for (a, b), v in _verbos(spec).items()]
    partes += [_svg_caja(c, pal) for c in cajas.values()]
    return "\n".join(partes), alto


def _niveles(spec: dict) -> dict[str, int]:
    """Nivel de cada nodo: el camino más largo desde una raíz (Kahn)."""
    ids = [n["id"] for n in spec["nodos"]]
    hijos: dict[str, list[str]] = {i: [] for i in ids}
    entrantes = dict.fromkeys(ids, 0)
    for a, b in _verbos(spec):
        hijos[a].append(b)
        entrantes[b] += 1
    nivel = dict.fromkeys(ids, 0)
    cola = [i for i in ids if entrantes[i] == 0]
    vistos: set[str] = set()
    while cola:
        actual = cola.pop(0)
        vistos.add(actual)
        for h in hijos[actual]:
            nivel[h] = max(nivel[h], nivel[actual] + 1)
            entrantes[h] -= 1
            if entrantes[h] == 0:
                cola.append(h)
    # Lo que quedó sin visitar está en un ciclo: va después de todo lo demás.
    fondo = max(nivel.values(), default=0) + 1
    for i in ids:
        if i not in vistos:
            nivel[i] = fondo
    return nivel


def _capas(spec: dict, pal: dict) -> tuple[str, float]:
    """`mapa_conceptual`, `jerarquia` (de arriba abajo) y `causa_efecto` (de izq. a der.)."""
    nodos = spec["nodos"]
    ids = [n["id"] for n in nodos]
    verbos = _verbos(spec)
    nivel = _niveles(spec)
    capas: list[list[str]] = [[] for _ in range(max(nivel.values()) + 1)]
    for i in ids:
        capas[nivel[i]].append(i)
    horizontal = spec["tipo_de_diagrama"] == "causa_efecto"

    padres: dict[str, list[str]] = {i: [] for i in ids}
    hijos: dict[str, list[str]] = {i: [] for i in ids}
    for a, b in verbos:
        padres[b].append(a)
        hijos[a].append(b)
    es_arbol = all(len(p) <= 1 for p in padres.values()) and all(
        nivel[b] == nivel[a] + 1 for a, b in verbos
    )

    if horizontal:
        columna = (ANCHO - 2 * MARGEN) / len(capas)
        cajas = _cajas(nodos, min(220, columna - 70))
        alto_caja = next(iter(cajas.values())).h
        paso = alto_caja + 26
        alto = Y_CONTENIDO + max(len(c) for c in capas) * paso - 26 + MARGEN
        centro = (Y_CONTENIDO + alto - MARGEN) / 2
        for k, capa in enumerate(capas):
            for j, i in enumerate(capa):
                cajas[i].cx = MARGEN + columna * (k + 0.5)
                cajas[i].cy = centro + (j - (len(capa) - 1) / 2) * paso
    else:
        ancho_util = ANCHO - 2 * MARGEN
        if es_arbol:
            # Las hojas se reparten el ancho y cada padre queda centrado sobre sus hijos.
            hojas = [i for i in ids if not hijos[i]]
            orden: list[str] = []

            def recorrer(i: str) -> None:
                if not hijos[i]:
                    orden.append(i)
                for h in hijos[i]:
                    recorrer(h)

            for raiz in (i for i in ids if not padres[i]):
                recorrer(raiz)
            casilla = ancho_util / len(hojas)
            cajas = _cajas(nodos, min(240, casilla - 18), parejas=False)
            x: dict[str, float] = {h: MARGEN + casilla * (k + 0.5) for k, h in enumerate(orden)}

            def centrar(i: str) -> float:
                if i not in x:
                    x[i] = sum(centrar(h) for h in hijos[i]) / len(hijos[i])
                return x[i]

            for i in ids:
                cajas[i].cx = centrar(i)
        else:
            mas_ancha = max(len(c) for c in capas)
            cajas = _cajas(nodos, min(240, ancho_util / mas_ancha - 18), parejas=False)
            for capa in capas:
                # Baricentro de los padres: reduce cruces sin un layout completo.
                capa.sort(
                    key=lambda i: sum(cajas[p].cx for p in padres[i]) / len(padres[i])
                    if padres[i] else 0
                )
                for j, i in enumerate(capa):
                    cajas[i].cx = MARGEN + ancho_util * (j + 0.5) / len(capa)
        # Cada nivel toma la altura de su caja más alta, no la de todo el diagrama.
        y = Y_CONTENIDO
        for capa in capas:
            alto_nivel = _emparejar([cajas[i] for i in capa])
            for i in capa:
                cajas[i].cy = y + alto_nivel / 2
            y += alto_nivel + 78
        alto = y - 78 + MARGEN

    partes: list[str] = []
    codos = spec["tipo_de_diagrama"] == "jerarquia" and es_arbol
    for (a, b), verbo in verbos.items():
        ca, cb = cajas[a], cajas[b]
        if codos:
            y1, y2 = ca.cy + ca.h / 2, cb.cy - cb.h / 2 - 4
            medio = y1 + 30
            partes.append(
                f'<path d="M{ca.cx:.1f},{y1:.1f} V{medio:.1f} H{cb.cx:.1f} V{y2 - 8:.1f}" '
                f'fill="none" stroke="{pal["suave"]}" stroke-width="2"/>'
            )
            partes.append(_punta(cb.cx, y2, math.pi / 2, pal))
            partes.append(_rotulo(cb.cx, (medio + y2) / 2, verbo, pal))
        else:
            partes.append(_union_recta(ca, cb, verbo, pal))
    partes += [_svg_caja(c, pal) for c in cajas.values()]
    return "\n".join(partes), alto


def _comparacion(spec: dict, pal: dict) -> tuple[str, float]:
    grupos = list(dict.fromkeys(n["grupo"] for n in spec["nodos"]))
    hueco = 20
    w = (ANCHO - 2 * MARGEN - hueco * (len(grupos) - 1)) / len(grupos)
    cajas = _cajas(spec["nodos"], w)
    partes: list[str] = []
    alto = 0.0
    for k, grupo in enumerate(grupos):
        cx = MARGEN + w / 2 + k * (w + hueco)
        partes.append(
            f'<rect x="{cx - w / 2:.1f}" y="{Y_CONTENIDO}" width="{w:.1f}" height="46" rx="23" '
            f'fill="{pal["primario"]}"/>'
            f'<text x="{cx:.1f}" y="{Y_CONTENIDO + 30}" text-anchor="middle" font-size="19" '
            f'font-weight="700" fill="#FFFFFF">{escape(grupo)}</text>'
        )
        y = Y_CONTENIDO + 46 + 16
        for n in (n for n in spec["nodos"] if n["grupo"] == grupo):
            c = cajas[n["id"]]
            c.cx, c.cy = cx, y + c.h / 2
            partes.append(_svg_caja(c, pal))
            y += c.h + 14
        alto = max(alto, y - 14 + MARGEN)
    return "\n".join(partes), alto


def renderizar_svg(spec: dict) -> str:
    """El esquema completo como SVG autónomo, con texto real y accesible."""
    pal = PALETAS.get(spec.get("paleta", "studify"), PALETAS["studify"])
    cuerpo, alto = {
        "flujo": _cadena,
        "linea_de_tiempo": _cadena,
        "ciclo": _ciclo,
        "comparacion": _comparacion,
    }.get(spec["tipo_de_diagrama"], _capas)(spec, pal)

    titulo = spec["titulo"]
    tam_titulo = 30 if len(titulo) <= 38 else 25
    return f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {ANCHO} {alto:.0f}" \
width="{ANCHO}" height="{alto:.0f}" role="img" aria-labelledby="esq-titulo esq-desc" \
font-family="{FUENTE}">
<title id="esq-titulo">{escape(titulo)}</title>
<desc id="esq-desc">{escape(spec.get("texto_alternativo", ""))}</desc>
<rect width="{ANCHO}" height="{alto:.0f}" rx="20" fill="{pal["fondo"]}"/>
<text x="{ANCHO / 2}" y="{Y_TITULO}" text-anchor="middle" font-family="{FUENTE_TITULO}" \
font-size="{tam_titulo}" font-weight="700" fill="{pal["texto"]}">{escape(titulo)}</text>
<rect x="{ANCHO / 2 - 36}" y="{Y_TITULO + 16}" width="72" height="4" rx="2" fill="{pal["acento"]}"/>
{cuerpo}
</svg>
"""


def exportar_png(svg: str, destino: Path) -> bool:
    """PNG de vista previa con PyMuPDF, si está instalado (extra `ingest`).

    Es solo para mirar el resultado sin navegador: PyMuPDF no tiene las fuentes
    del sitio y dibuja con las suyas. El artefacto que cuenta es el SVG.
    """
    try:
        import pymupdf
    except ImportError:
        return False
    documento = pymupdf.open(stream=svg.encode("utf-8"), filetype="svg")
    documento[0].get_pixmap(dpi=144).save(destino)
    return True


# --- Candidatos de pago -----------------------------------------------------------


def _descargar(url: str) -> bytes:
    import httpx

    respuesta = httpx.get(url, timeout=120, follow_redirects=True)
    respuesta.raise_for_status()
    return respuesta.content


def _gemini(prompt: str, key: str) -> bytes:
    # Endpoint y cuerpo tomados de ai.google.dev/gemini-api/docs/image-generation.
    # Sin verificar: la ruta exacta de la imagen en el JSON de REST (la guía la
    # da para el SDK: `interaction.output_image.data`), por eso se busca.
    import httpx

    respuesta = httpx.post(
        "https://generativelanguage.googleapis.com/v1beta/interactions",
        headers={"x-goog-api-key": key},
        json={
            "model": "gemini-nano-banana-2.1",
            "input": prompt,
            "response_format": {"type": "image", "mime_type": "image/png", "aspect_ratio": "4:3"},
        },
        timeout=180,
    )
    respuesta.raise_for_status()

    def buscar(valor: object) -> str | None:
        if isinstance(valor, dict):
            dato = valor.get("data")
            if isinstance(dato, str) and len(dato) > 1000:
                return dato
            valor = list(valor.values())
        if isinstance(valor, list):
            for elemento in valor:
                if (hallado := buscar(elemento)) is not None:
                    return hallado
        return None

    imagen = buscar(respuesta.json())
    if imagen is None:
        raise RuntimeError("la respuesta de Gemini no trae una imagen en base64")
    return base64.b64decode(imagen)


def _openai(prompt: str, key: str) -> bytes:
    # Sin verificar: que `gpt-image-2.5-flare` acepte `size` y `quality` con estos
    # valores en /v1/images/generations (la referencia del endpoint dio 404).
    import httpx

    respuesta = httpx.post(
        "https://api.openai.com/v1/images/generations",
        headers={"Authorization": f"Bearer {key}"},
        json={
            "model": "gpt-image-2.5-flare",
            "prompt": prompt,
            "size": "1536x1024",
            "quality": "high",
            "n": 1,
        },
        timeout=240,
    )
    respuesta.raise_for_status()
    return base64.b64decode(respuesta.json()["data"][0]["b64_json"])


def _recraft(prompt: str, key: str) -> bytes:
    # Sin verificar: el largo máximo del prompt de V4.1 (se manda el compacto) y
    # que la URL de un modelo `_vector` entregue el SVG directamente.
    import httpx

    respuesta = httpx.post(
        "https://external.api.recraft.ai/v1/images/generations",
        headers={"Authorization": f"Bearer {key}"},
        json={"prompt": prompt, "model": "recraftv4_1_vector", "size": "4:3"},
        timeout=180,
    )
    respuesta.raise_for_status()
    return _descargar(respuesta.json()["data"][0]["url"])


def _ideogram(prompt: str, key: str) -> bytes:
    # Sin verificar: los valores de `resolution` (se deja el predeterminado). Con
    # `text_prompt` el «magic prompt» se aplica solo y puede reescribir rótulos;
    # si pasa, hay que migrar a `json_prompt`.
    import httpx

    respuesta = httpx.post(
        "https://api.ideogram.ai/v1/ideogram-v4/generate",
        headers={"Api-Key": key},
        files={"text_prompt": (None, prompt)},
        timeout=180,
    )
    respuesta.raise_for_status()
    return _descargar(respuesta.json()["data"][0]["url"])


@dataclass(frozen=True)
class Candidato:
    clave: str
    modelo: str
    variable: str
    usd_por_imagen: float
    fuente_precio: str
    generar: Callable[[str, str], bytes]
    compacto: bool = False


CANDIDATOS = (
    Candidato(
        "gemini", "gemini-nano-banana-2.1", "GEMINI_API_KEY", 0.0336,
        "oficial, ai.google.dev/gemini-api/docs/pricing (10-oct-2026), imagen 1K", _gemini,
    ),
    Candidato(
        "openai", "gpt-image-2.5-flare (high, 1536x1024)", "OPENAI_API_KEY", 0.08,
        "ESTIMADO con holgura: US$30/1M tokens de salida (oficial) y ~1.756 tokens a "
        "1024² según terceros; el tamaño apaisado no está publicado", _openai,
    ),
    Candidato(
        "recraft", "recraftv4_1_vector (SVG)", "RECRAFT_API_KEY", 0.08,
        "oficial, recraft.ai/docs/api-reference/pricing (10-oct-2026)", _recraft, compacto=True,
    ),
    Candidato(
        "ideogram", "ideogram-v4 (Default)", "IDEOGRAM_API_KEY", 0.06,
        "fuente secundaria (developer.puter.com, jun-2026); la página oficial no cargó", _ideogram,
    ),
)


def leer_keys() -> dict[str, str]:
    """Las keys presentes, del entorno o del `.env` de la raíz. No se imprimen."""
    del_env: dict[str, str] = {}
    archivo = RAIZ / ".env"
    if archivo.exists():
        for linea in archivo.read_text(encoding="utf-8").splitlines():
            nombre, signo, valor = linea.partition("=")
            if signo and not nombre.lstrip().startswith("#"):
                del_env[nombre.strip()] = valor.strip().strip("\"'")
    return {
        c.variable: (os.environ.get(c.variable) or del_env.get(c.variable, ""))
        for c in CANDIDATOS
    }


def _extension(datos: bytes) -> str:
    if datos[:5].lstrip().startswith((b"<svg", b"<?xml")):
        return "svg"
    if datos.startswith(b"\x89PNG"):
        return "png"
    if datos[:4] == b"RIFF":
        return "webp"
    return "jpg"


# --- Programa ---------------------------------------------------------------------


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--pagadas", action="store_true", help="hacer las llamadas de pago")
    parser.add_argument(
        "--confirmo-usd", type=float, default=0.0,
        help="monto que la persona autoriza gastar, después de ver el estimado",
    )
    parser.add_argument("--solo", default="", help="candidatos separados por coma (p. ej. gemini)")
    parser.add_argument(
        "--con-estres", action="store_true",
        help="incluir specs/90_estres_ortografia.json también en las llamadas pagadas",
    )
    args = parser.parse_args()

    specs: dict[str, dict] = {}
    for ruta in sorted(SPECS.glob("*.json")):
        spec = json.loads(ruta.read_text(encoding="utf-8"))
        if errores := validar(spec):
            print(f"✗ {ruta.name} no cumple el contrato:\n  - " + "\n  - ".join(errores))
            return 1
        specs[ruta.stem] = spec

    # 1 y 2: lo que no cuesta nada.
    (RESULTADOS / "deterministico").mkdir(parents=True, exist_ok=True)
    (RESULTADOS / "prompts").mkdir(parents=True, exist_ok=True)
    for nombre, spec in specs.items():
        inicio = time.perf_counter()
        svg = renderizar_svg(spec)
        milisegundos = (time.perf_counter() - inicio) * 1000
        (RESULTADOS / "deterministico" / f"{nombre}.svg").write_text(svg, encoding="utf-8")
        con_png = exportar_png(svg, RESULTADOS / "deterministico" / f"{nombre}.png")
        (RESULTADOS / "prompts" / f"{nombre}.txt").write_text(
            construir_prompt(spec), encoding="utf-8"
        )
        (RESULTADOS / "prompts" / f"{nombre}.compacto.txt").write_text(
            construir_prompt(spec, compacto=True), encoding="utf-8"
        )
        print(
            f"✓ determinístico  {nombre}.svg  ({milisegundos:.1f} ms"
            f"{', con PNG de vista previa' if con_png else ''})"
        )

    # 3: el plan de pago, siempre a la vista antes de gastar.
    keys = leer_keys()
    pedidos = {c.strip() for c in args.solo.split(",") if c.strip()}
    elegidos = [c for c in CANDIDATOS if not pedidos or c.clave in pedidos]
    de_pago = {n: s for n, s in specs.items() if args.con_estres or not n.startswith("90_")}
    con_key = [c for c in elegidos if keys[c.variable]]
    estimado = sum(c.usd_por_imagen for c in con_key) * len(de_pago)

    print("\nPlan de llamadas pagadas")
    for c in elegidos:
        estado = "key presente" if keys[c.variable] else f"SIN KEY ({c.variable})"
        print(
            f"  {c.clave:<9} {c.modelo:<40} {len(de_pago)} × US${c.usd_por_imagen:.4f} "
            f"= US${c.usd_por_imagen * len(de_pago):.2f}   [{estado}]"
        )
        print(f"            precio: {c.fuente_precio}")
    print(f"  Total estimado con las keys disponibles: US${estimado:.2f} (tope US${TOPE_USD:.2f})")

    if not args.pagadas:
        print("\nNo se hizo ninguna llamada de pago (falta --pagadas).")
        return 0
    if not con_key:
        print("\nNo hay ninguna API key de imagen: no hay nada que ejecutar.")
        return 1
    if estimado > TOPE_USD:
        print(f"\nEl estimado supera el tope de US${TOPE_USD:.2f}: no se ejecuta.")
        return 1
    if args.confirmo_usd < estimado:
        print(
            f"\nFalta la confirmación: repite el comando con --confirmo-usd {estimado:.2f} "
            f"(o más, hasta {TOPE_USD:.2f})."
        )
        return 1

    registro: list[dict] = []
    for c in con_key:
        (RESULTADOS / c.clave).mkdir(parents=True, exist_ok=True)
        for nombre, spec in de_pago.items():
            prompt = construir_prompt(spec, compacto=c.compacto)
            entrada = {"candidato": c.clave, "modelo": c.modelo, "spec": nombre,
                       "usd_estimado": c.usd_por_imagen}
            inicio = time.perf_counter()
            try:
                datos = c.generar(prompt, keys[c.variable])
            except Exception as exc:  # noqa: BLE001 - un fallo no debe cortar la comparación
                # Solo el tipo y el código: el mensaje de httpx puede traer la URL
                # y, en algunos proveedores, la key en la query.
                codigo = getattr(getattr(exc, "response", None), "status_code", "")
                entrada["error"] = f"{type(exc).__name__} {codigo}".strip()
                print(f"✗ {c.clave:<9} {nombre}: {entrada['error']}")
            else:
                destino = RESULTADOS / c.clave / f"{nombre}.{_extension(datos)}"
                destino.write_bytes(datos)
                entrada["archivo"] = str(destino.relative_to(AQUI))
                print(f"✓ {c.clave:<9} {destino.name}")
            entrada["segundos"] = round(time.perf_counter() - inicio, 2)
            registro.append(entrada)

    (RESULTADOS / "registro.json").write_text(
        json.dumps(registro, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"\nRegistro en {RESULTADOS / 'registro.json'}. Falta la evaluación con la rúbrica.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
