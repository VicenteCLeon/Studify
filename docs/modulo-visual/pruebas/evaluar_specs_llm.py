"""Evaluación medible de las especificaciones que generó DeepSeek.

Lee `specs_llm/` (lo que dejó `generar_specs_llm.py`) y calcula solo lo que se
puede contar. No pone nota a nada: claridad y estética las evalúa una persona.

Qué mide, y cómo, para que cada cifra se pueda discutir:

- **Etiqueta en el material.** `literal`: la etiqueta aparece tal cual en un
  fragmento, ignorando mayúsculas y espacios. `casi`: no aparece seguida, pero
  todas sus palabras con contenido están en un mismo fragmento, ignorando tildes
  y plurales. `ausente`: ni lo uno ni lo otro; es un **posible término
  inventado** y queda listado. Antes de comparar se limpia el LaTeX del PDF
  (`$X \\rightarrow Y$` pasa a `X → Y`).
- **Respaldo de una relación.** Es una coocurrencia, no una comprobación de
  sentido: `oración` si las dos etiquetas aparecen en una misma oración de un
  fragmento, `fragmento` si aparecen en el mismo fragmento pero en oraciones
  distintas, `sin respaldo` si no coinciden en ninguno. Que coincidan dice que
  el texto habla de las dos cosas juntas; **no** que el verbo elegido sea
  correcto. Eso hay que leerlo, y la oración queda guardada para hacerlo rápido.
- **Ortografía.** Signos de apertura sin su cierre (o al revés), caracteres
  rotos, palabras que en el material llevan tilde y en la especificación no (o
  al revés), y terminaciones que siempre llevan tilde (`-cion`, `-sion`).
  Las palabras que no están en el material no se pueden verificar por código y
  se cuentan aparte.

- **Render.** Cuántas relaciones llegan de verdad al SVG, y cuántos rótulos de
  flecha quedan montados uno sobre otro (se mide sobre el SVG generado).

Con esas mismas cifras elige, sin opinar, la mejor corrida de cada objetivo
(`elegir`): descarta las que el render dibuja mal y ordena el resto.

No llama a ninguna API. Uso:

    python docs/modulo-visual/pruebas/evaluar_specs_llm.py
    python docs/modulo-visual/pruebas/evaluar_specs_llm.py --carpeta v2
"""

import argparse
import json
import re
import sys
import unicodedata
from collections import Counter
from pathlib import Path

AQUI = Path(__file__).resolve().parent
sys.path.insert(0, str(AQUI))

import generar_pruebas as base  # noqa: E402

SPECS_LLM = AQUI / "specs_llm"
SPECS_A_MANO = AQUI / "specs"
SALIDA = AQUI / "resultados" / "llm"

# Las tres especificaciones redactadas a mano y el objetivo al que corresponden.
A_MANO = {
    "BD-U3-01": "01_bd_primera_forma_normal.json",
    "BD-U3-02": "02_bd_dependencias_funcionales.json",
    "PROG-U1-02": "03_prog_estructuras_de_control.json",
}

VACIAS = {
    "a", "al", "con", "de", "del", "el", "en", "la", "las", "lo", "los", "o", "por", "para",
    "que", "se", "su", "sus", "un", "una", "y", "e",
}  # fmt: skip

_LATEX = (
    (r"\rightarrow", "→"), (r"\subseteq", "⊆"), (r"\cup", "∪"), (r"\in ", "∈ "),
    (r"\{", "{"), (r"\}", "}"), ("$", ""),
)  # fmt: skip

_SIEMPRE_CON_TILDE = re.compile(r"(cion|sion)$")


def limpiar(texto: str) -> str:
    """Minúsculas, espacios simples y sin el LaTeX que dejó la extracción del PDF."""
    for marca, reemplazo in _LATEX:
        texto = texto.replace(marca, reemplazo)
    return re.sub(r"\s+", " ", texto).strip().casefold()


def sin_tildes(texto: str) -> str:
    """Quita tildes y diéresis, pero conserva la ñ: `año` y `ano` no son la misma palabra."""
    texto = texto.replace("ñ", "\0").replace("Ñ", "\1")
    plano = "".join(
        c for c in unicodedata.normalize("NFD", texto) if unicodedata.category(c) != "Mn"
    )
    return plano.replace("\0", "ñ").replace("\1", "Ñ")


def raiz(palabra: str) -> str:
    """Forma para comparar: sin tildes y sin la marca de plural."""
    palabra = sin_tildes(palabra.casefold())
    if len(palabra) > 4 and palabra.endswith("es"):
        return palabra[:-2]
    if len(palabra) > 3 and palabra.endswith("s"):
        return palabra[:-1]
    return palabra


def palabras(texto: str) -> list[str]:
    return re.findall(r"[^\W\d_]+|\d+|→", limpiar(texto))


def con_contenido(texto: str) -> set[str]:
    return {raiz(p) for p in palabras(texto) if p not in VACIAS}


def oraciones(texto: str) -> list[str]:
    return [o.strip() for o in re.split(r"(?<=[.!?:;])\s+|•|\n+", texto) if o.strip()]


def contiene(texto: str, frase: str) -> bool:
    """`frase` aparece en `texto` como palabras completas: «for» no cuenta dentro de «forma»."""
    return bool(re.search(rf"(?<!\w){re.escape(limpiar(frase))}(?!\w)", limpiar(texto)))


def buscar_etiqueta(etiqueta: str, fragmentos: list[dict]) -> dict:
    """Dónde aparece una etiqueta: `literal`, `casi` o `ausente`."""
    literal = [f["id_fragmento"] for f in fragmentos if contiene(f["texto"], etiqueta)]
    if literal:
        return {"nivel": "literal", "fragmentos": literal, "faltan": []}
    buscadas = con_contenido(etiqueta)
    casi = [f["id_fragmento"] for f in fragmentos if buscadas <= con_contenido(f["texto"])]
    if casi:
        return {"nivel": "casi", "fragmentos": casi, "faltan": []}
    todas = set().union(*(con_contenido(f["texto"]) for f in fragmentos))
    return {"nivel": "ausente", "fragmentos": [], "faltan": sorted(buscadas - todas)}


def respaldo(desde: str, hacia: str, fragmentos: list[dict]) -> dict:
    """Coocurrencia de las dos etiquetas de una relación."""
    a, b = con_contenido(desde), con_contenido(hacia)
    en_fragmento: list[int] = []
    for f in fragmentos:
        if not (a | b) <= con_contenido(f["texto"]):
            continue
        en_fragmento.append(f["id_fragmento"])
        for oracion in oraciones(f["texto"]):
            if (a | b) <= con_contenido(oracion):
                return {
                    "nivel": "oración",
                    "fragmentos": [f["id_fragmento"]],
                    "evidencia": oracion[:300],
                }
    if en_fragmento:
        return {"nivel": "fragmento", "fragmentos": en_fragmento, "evidencia": ""}
    return {"nivel": "sin respaldo", "fragmentos": [], "evidencia": ""}


def textos_visibles(spec: dict) -> list[str]:
    visibles = [spec["titulo"], spec["texto_alternativo"]]
    for n in spec["nodos"]:
        visibles += [n["etiqueta"], n.get("detalle") or "", n.get("grupo") or ""]
    visibles += [r["verbo"] for r in spec["relaciones"]]
    return [v for v in visibles if v]


def revisar_ortografia(spec: dict, material: dict) -> dict:
    vocabulario: dict[str, set[str]] = {}
    fuente = " ".join(
        [material["asignatura"], material["unidad"], material["tema"]]
        + [f["texto"] for f in material["fragmentos"]]
    )
    for p in re.findall(r"[^\W\d_]+", fuente.casefold()):
        vocabulario.setdefault(sin_tildes(p), set()).add(p)

    problemas: list[str] = []
    con_tilde, sin_verificar = set(), set()
    for texto in textos_visibles(spec):
        for abre, cierra in (("¿", "?"), ("¡", "!")):
            if texto.count(abre) != texto.count(cierra):
                problemas.append(f"signos {abre}{cierra} desparejos en «{texto}»")
        if re.search(r"[ÃÂ�\x00-\x08]", texto):
            problemas.append(f"caracteres rotos en «{texto}»")
        for p in re.findall(r"[^\W\d_]+", texto.casefold()):
            if re.search(r"[áéíóúüñ]", p):
                con_tilde.add(p)
            formas = vocabulario.get(sin_tildes(p))
            if formas is None:
                if len(p) > 3:
                    sin_verificar.add(p)
                if _SIEMPRE_CON_TILDE.search(p):
                    problemas.append(f"«{p}» termina en -cion/-sion sin tilde")
            elif p not in formas:
                problemas.append(f"«{p}» difiere del material, que escribe {sorted(formas)}")
    return {
        "problemas": sorted(set(problemas)),
        "palabras_con_tilde_o_enie": sorted(con_tilde),
        "palabras_fuera_del_material": sorted(sin_verificar),
    }


def es_conexo(spec: dict) -> bool:
    ids = [n["id"] for n in spec["nodos"]]
    vecinos: dict[str, set[str]] = {i: set() for i in ids}
    for r in spec["relaciones"]:
        vecinos[r["desde"]].add(r["hacia"])
        vecinos[r["hacia"]].add(r["desde"])
    vistos, cola = {ids[0]}, [ids[0]]
    while cola:
        for v in vecinos[cola.pop()] - vistos:
            vistos.add(v)
            cola.append(v)
    return len(vistos) == len(ids)


def relaciones_que_dibuja(spec: dict) -> int:
    """Cuántas relaciones llegan al SVG con el render actual."""
    ids = [n["id"] for n in spec["nodos"]]
    pares = {(r["desde"], r["hacia"]) for r in spec["relaciones"]}
    if spec["tipo_de_diagrama"] in ("flujo", "linea_de_tiempo"):
        return len(pares & set(zip(ids, ids[1:], strict=False)))
    if spec["tipo_de_diagrama"] == "comparacion":
        return 0
    return len(pares)


_ROTULO = re.compile(r'<rect x="([\d.-]+)" y="([\d.-]+)" width="([\d.]+)" height="22" rx="11"')


def rotulos_superpuestos(spec: dict) -> int:
    """Pares de rótulos de flecha que se pisan en el SVG del render actual."""
    cajas = [tuple(float(v) for v in m) for m in _ROTULO.findall(base.renderizar_svg(spec))]
    pisados = 0
    for i, (x1, y1, w1) in enumerate(cajas):
        for x2, y2, w2 in cajas[i + 1 :]:
            if min(x1 + w1, x2 + w2) - max(x1, x2) > 2 and abs(y1 - y2) < 20:
                pisados += 1
    return pisados


def detalles_repetidos(spec: dict) -> int:
    detalles = [limpiar(n["detalle"]) for n in spec["nodos"] if n.get("detalle")]
    return len(detalles) - len(set(detalles))


def defectos_de_render(fila: dict) -> tuple[int, int, int]:
    """(grafo partido, relaciones que no llegan al SVG, rótulos superpuestos)."""
    return (
        0 if fila["conexo"] else 1,
        fila["relaciones"] - fila["relaciones_dibujadas"],
        fila["rotulos_superpuestos"],
    )


def elegir(filas: list[dict]) -> dict[str, dict]:
    """La mejor corrida de cada objetivo, solo con criterios contables.

    Manda lo que el render actual dibuja mal: grafo no conexo, relaciones que
    no llegan al SVG y rótulos superpuestos. A igualdad de eso gana la que
    tiene más etiquetas literales, menos relaciones sin respaldo, menos
    detalles repetidos, menos reparaciones y más relaciones respaldadas en una
    misma oración; si aún empatan, la primera. `limpia` dice si la elegida
    quedó sin ningún defecto de render.
    """
    elegidas: dict[str, dict] = {}
    for codigo in dict.fromkeys(f["codigo_objetivo"] for f in filas):
        candidatas = sorted(
            (f for f in filas if f["codigo_objetivo"] == codigo and f["valida"]),
            key=lambda f: (
                defectos_de_render(f),
                -f["etiquetas_literal"] / f["nodos"],
                len(f["relaciones_sin_respaldo"]),
                f["detalles_repetidos"],
                f["reparaciones"],
                -f["relaciones_oracion"],
                f["corrida"],
            ),
        )
        if candidatas:
            mejor = candidatas[0]
            elegidas[codigo] = {
                "nombre": mejor["nombre"],
                "limpia": defectos_de_render(mejor) == (0, 0, 0),
                "defectos_de_render": defectos_de_render(mejor),
            }
    return elegidas


def para_mostrar(elegidas: dict[str, dict], cuantas: int = 3) -> list[str]:
    """Las elegidas de los objetivos con menos defectos de render, una por objetivo."""
    orden = sorted(elegidas.values(), key=lambda e: e["defectos_de_render"])
    return [e["nombre"] for e in orden[:cuantas]]


def evaluar(spec: dict, material: dict) -> dict:
    fragmentos = material["fragmentos"]
    etiqueta = {n["id"]: n["etiqueta"] for n in spec["nodos"]}
    etiquetas = [
        {"id": n["id"], "etiqueta": n["etiqueta"], **buscar_etiqueta(n["etiqueta"], fragmentos)}
        for n in spec["nodos"]
    ]
    relaciones = [
        {
            "relacion": f"{etiqueta[r['desde']]} —{r['verbo']}→ {etiqueta[r['hacia']]}",
            "verbo_literal_en_material": any(contiene(f["texto"], r["verbo"]) for f in fragmentos),
            **respaldo(etiqueta[r["desde"]], etiqueta[r["hacia"]], fragmentos),
        }
        for r in spec["relaciones"]
    ]
    niveles = Counter(e["nivel"] for e in etiquetas)
    respaldos = Counter(r["nivel"] for r in relaciones)
    return {
        "tipo_de_diagrama": spec["tipo_de_diagrama"],
        "titulo": spec["titulo"],
        "nodos": len(spec["nodos"]),
        "relaciones": len(spec["relaciones"]),
        "etiquetas": etiquetas,
        "etiquetas_literal": niveles["literal"],
        "etiquetas_casi": niveles["casi"],
        "etiquetas_ausentes": [e["etiqueta"] for e in etiquetas if e["nivel"] == "ausente"],
        "detalle_relaciones": relaciones,
        "relaciones_oracion": respaldos["oración"],
        "relaciones_fragmento": respaldos["fragmento"],
        "relaciones_sin_respaldo": [
            r["relacion"] for r in relaciones if r["nivel"] == "sin respaldo"
        ],
        "conexo": es_conexo(spec),
        "relaciones_dibujadas": relaciones_que_dibuja(spec),
        "rotulos_superpuestos": rotulos_superpuestos(spec),
        "detalles_repetidos": detalles_repetidos(spec),
        "fuentes": spec.get("fuentes") or [],
        "ortografia": revisar_ortografia(spec, material),
    }


def comparar(llm: dict, a_mano: dict) -> dict:
    """Diferencias contables entre una especificación del LLM y la escrita a mano."""

    def claves(spec: dict) -> dict[str, str]:
        etiquetas = (n["etiqueta"] for n in spec["nodos"])
        return {" ".join(sorted(con_contenido(e))): e for e in etiquetas}

    del_llm, de_mano = claves(llm), claves(a_mano)
    return {
        "mismo_tipo": llm["tipo_de_diagrama"] == a_mano["tipo_de_diagrama"],
        "tipo_llm": llm["tipo_de_diagrama"],
        "tipo_a_mano": a_mano["tipo_de_diagrama"],
        "nodos_llm": len(llm["nodos"]),
        "nodos_a_mano": len(a_mano["nodos"]),
        "etiquetas_en_comun": sorted(del_llm[k] for k in del_llm.keys() & de_mano.keys()),
        "solo_llm": sorted(del_llm[k] for k in del_llm.keys() - de_mano.keys()),
        "solo_a_mano": sorted(de_mano[k] for k in de_mano.keys() - del_llm.keys()),
    }


def _celda(lista: list[str]) -> str:
    return "; ".join(f"«{x}»" for x in lista) if lista else "—"


def main() -> int:
    global SPECS_LLM, SALIDA
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--carpeta", default="", help="subcarpeta de specs_llm/ (una tanda)")
    args = parser.parse_args()
    SPECS_LLM, SALIDA = SPECS_LLM / args.carpeta, SALIDA / args.carpeta

    registro = json.loads((SPECS_LLM / "registro.json").read_text(encoding="utf-8"))
    materiales = {
        p.stem: json.loads(p.read_text(encoding="utf-8"))
        for p in (SPECS_LLM / "material").glob("*.json")
    }
    filas: list[dict] = []
    for corrida in registro:
        fila = {k: v for k, v in corrida.items() if k != "detalle_intentos"}
        fila["errores_primer_intento"] = corrida["detalle_intentos"][0]["errores"]
        if corrida["valida"]:
            spec = json.loads((SPECS_LLM / f"{corrida['nombre']}.json").read_text(encoding="utf-8"))
            fila |= evaluar(spec, materiales[corrida["codigo_objetivo"]])
            if corrida["codigo_objetivo"] in A_MANO:
                a_mano = json.loads(
                    (SPECS_A_MANO / A_MANO[corrida["codigo_objetivo"]]).read_text(encoding="utf-8")
                )
                fila["contra_a_mano"] = comparar(spec, a_mano)
        filas.append(fila)

    # La misma vara para las especificaciones a mano: si no, la comparación no es pareja.
    a_mano_evaluadas = {}
    for codigo, archivo in A_MANO.items():
        if codigo not in materiales:
            continue  # una tanda parcial no trae el material de todos los objetivos
        spec = json.loads((SPECS_A_MANO / archivo).read_text(encoding="utf-8"))
        a_mano_evaluadas[codigo] = evaluar(spec, materiales[codigo])

    por_objetivo = {}
    for codigo in dict.fromkeys(f["codigo_objetivo"] for f in filas):
        del_objetivo = [f for f in filas if f["codigo_objetivo"] == codigo]
        tipos = [f.get("tipo_de_diagrama", "falló") for f in del_objetivo]
        por_objetivo[codigo] = {"tipos": tipos, "coinciden": len(set(tipos)) == 1}

    validas = [f for f in filas if f["valida"]]
    resumen = {
        "corridas": len(filas),
        "validas": len(validas),
        "a_la_primera": sum(f["reparaciones"] == 0 for f in validas),
        "con_reparacion": sum(f["reparaciones"] > 0 for f in validas),
        "fallidas": len(filas) - len(validas),
        "etiquetas": sum(f["nodos"] for f in validas),
        "etiquetas_literal": sum(f["etiquetas_literal"] for f in validas),
        "etiquetas_casi": sum(f["etiquetas_casi"] for f in validas),
        "etiquetas_ausentes": sum(len(f["etiquetas_ausentes"]) for f in validas),
        "etiquetas_ausentes_distintas": sorted(
            {e for f in validas for e in f["etiquetas_ausentes"]}
        ),
        "relaciones": sum(f["relaciones"] for f in validas),
        "relaciones_oracion": sum(f["relaciones_oracion"] for f in validas),
        "relaciones_fragmento": sum(f["relaciones_fragmento"] for f in validas),
        "relaciones_sin_respaldo": sum(len(f["relaciones_sin_respaldo"]) for f in validas),
        "relaciones_dibujadas": sum(f["relaciones_dibujadas"] for f in validas),
        "no_conexas": [f["nombre"] for f in validas if not f["conexo"]],
        "con_relaciones_sin_dibujar": [
            f["nombre"] for f in validas if f["relaciones_dibujadas"] < f["relaciones"]
        ],
        "con_rotulos_superpuestos": [f["nombre"] for f in validas if f["rotulos_superpuestos"]],
        "elegidas": elegir(filas),
        "para_mostrar": para_mostrar(elegir(filas)),
        "con_problemas_de_ortografia": [
            f["nombre"] for f in validas if f["ortografia"]["problemas"]
        ],
        "tokens_entrada": sum(f["tokens_entrada"] for f in filas),
        "tokens_salida": sum(f["tokens_salida"] for f in filas),
        "costo_usd": sum(f["costo_usd"] for f in filas),
        "costo_usd_punta": sum(f["costo_usd_punta"] for f in filas),
        "segundos": sum(f["segundos"] for f in filas),
    }

    SALIDA.mkdir(parents=True, exist_ok=True)
    (SALIDA / "evaluacion.json").write_text(
        json.dumps(
            {
                "resumen": resumen,
                "por_objetivo": por_objetivo,
                "corridas": filas,
                "a_mano": a_mano_evaluadas,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    md = [
        "| Corrida | Validación | Tipo | Etiquetas en el material | Posibles términos inventados | "
        "Relaciones con respaldo | Sin respaldo | Ortografía | Tokens (entrada + salida) | "
        "Costo (US$) | Segundos |",
        "|---|---|---|---|---|---|---|---|--:|--:|--:|",
    ]
    for f in filas:
        if not f["valida"]:
            md.append(f"| `{f['nombre']}` | **falló** | — | — | — | — | — | — | "
                      f"{f['tokens_entrada']} + {f['tokens_salida']} | {f['costo_usd']:.5f} | "
                      f"{f['segundos']:.1f} |")
            continue
        validacion = "a la primera" if f["reparaciones"] == 0 else f"{f['reparaciones']} reparación"
        orto = f["ortografia"]["problemas"]
        md.append(
            f"| `{f['nombre']}` | {validacion} | `{f['tipo_de_diagrama']}` | "
            f"{f['etiquetas_literal']} literal + {f['etiquetas_casi']} casi, de {f['nodos']} | "
            f"{_celda(f['etiquetas_ausentes'])} | "
            f"{f['relaciones_oracion']} oración + {f['relaciones_fragmento']} fragmento, "
            f"de {f['relaciones']} | {_celda(f['relaciones_sin_respaldo'])} | "
            f"{'sin problemas' if not orto else _celda(orto)} | "
            f"{f['tokens_entrada']} + {f['tokens_salida']} | {f['costo_usd']:.5f} | "
            f"{f['segundos']:.1f} |"
        )
    md += [
        "",
        "| Corrida | Nodos | Grafo conexo | Relaciones que dibuja el render | "
        "Rótulos superpuestos | Detalles repetidos | `fuentes` | Elegida |",
        "|---|--:|:-:|:-:|--:|--:|---|:-:|",
    ]
    for f in validas:
        md.append(
            f"| `{f['nombre']}` | {f['nodos']} | {'sí' if f['conexo'] else '**no**'} | "
            f"{f['relaciones_dibujadas']} de {f['relaciones']} | {f['rotulos_superpuestos']} | "
            f"{f['detalles_repetidos']} | {', '.join(str(i) for i in f['fuentes']) or '—'} | "
            f"{'✔' if f['nombre'] in resumen['para_mostrar'] else ''} |"
        )
    (SALIDA / "evaluacion.md").write_text("\n".join(md) + "\n", encoding="utf-8")

    print(json.dumps(resumen, ensure_ascii=False, indent=2))
    print(json.dumps(por_objetivo, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    raise SystemExit(main())
