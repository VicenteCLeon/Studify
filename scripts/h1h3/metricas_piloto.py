"""Métricas y veredicto del piloto de la ronda 4 (PRUEBAS_VARK.md, «Etapa 1 — Ronda 4»).

    python scripts/h1h3/metricas_piloto.py [--estado RUTA] [--base base] [--e E]

Lee el estado que deja `scripts/h1h3/piloto.py`, calcula sobre `data/pruebas_vark/`:

  Veredicto (todas deben cumplirse):
    1. primeros intentos con más de 300 palabras: como máximo 9 de 28 en E
    2. cápsulas sin ninguna válida: como máximo 1 de 28 en E
    3. glosario presente en todas las cápsulas válidas de E
    4. ningún perfil estable perdido: «estable» = válido en las 2 corridas de la base;
       «perdido» = inválido en las 2 corridas de E
  Informativas (no bloquean):
    primeros intentos bajo 150 palabras (base y E); entradas por glosario («exactamente 3»);
    composición de `representacion_adaptativa` en los perfiles «solo R»; palabras que bajó E frente a A
    (ronda 2, pareado por perfil); y las muestras legibles en data/h1h3/muestras_ronda4.md.

Las palabras del primer intento se cuentan sobre `respuestas_crudas.json` como las cuenta el validador.
"""

# ruff: noqa: E501  (informe impreso con f-strings largos)
import argparse
import json
import statistics as st
from collections import Counter
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
DATOS = RAIZ / "data" / "pruebas_vark"
SALIDA = RAIZ / "data" / "h1h3"

UMBRAL_DESBORDES = 9
UMBRAL_INVALIDAS = 1
SOLO_R = {"encabezados_jerarquicos", "definiciones_exactas", "glosario"}
# Brazo A de la ronda 2 (mismo prompt que E salvo el glosario): S42 y S43, 2 corridas cada uno.
A_RONDA2 = {
    "S42": ["20261005-194719_semilla42", "20261005-195726_semilla42"],
    "S43": ["20261005-195319_semilla43", "20261005-200432_semilla43"],
}
MUESTRAS = ("A_A0-R100-K0", "B_A20-R70-K10", "B_A50-R50-K0")


def palabras(texto: str) -> int:
    return len(texto.split())


def palabras_bloque(b: dict) -> int:
    n = palabras(b.get("encabezado") or "")
    cuerpo = b["cuerpo"]
    if isinstance(cuerpo, str):
        return n + palabras(cuerpo)
    for e in cuerpo:
        n += palabras(e) if isinstance(e, str) else sum(palabras(x) for x in e)
    return n


def primer_intento(directorio: str, slug: str) -> dict | None:
    """Palabras y estructura de la primera respuesta del modelo, o None si no se puede leer."""
    try:
        crudas = json.loads(
            (DATOS / directorio / slug / "respuestas_crudas.json").read_text("utf-8")
        )
        j = json.loads(crudas[0]["respuesta"])
        rep = j["representacion_adaptativa"]
        total = (
            palabras(j["activacion"])
            + palabras(j["concepto_central"])
            + sum(palabras_bloque(b) for b in rep)
            + palabras_bloque(j["ejemplo"])
        )
        gl = [b for b in rep if b["tipo"] == "glosario"]
        entradas = [len(b["cuerpo"]) if isinstance(b["cuerpo"], list) else None for b in gl]
        return {"palabras": total, "tipos": [b["tipo"] for b in rep], "entradas": entradas}
    except (OSError, KeyError, ValueError, TypeError, IndexError):
        return None


def cargar_brazo(estado: dict, brazo: str) -> list[dict]:
    """Una fila por perfil-corrida del brazo."""
    filas = []
    for corrida in estado["corridas"].values():
        if corrida["arbol"] != brazo:
            continue
        resumen = json.loads((DATOS / corrida["directorio"] / "resumen.json").read_text("utf-8"))
        for r in resumen["resultados"]:
            valida = r["criterios"]["contrato"]["estado"] == "pasa"
            capsula = None
            ruta = DATOS / corrida["directorio"] / r["slug"] / "capsula.json"
            if valida and ruta.exists():
                capsula = json.loads(ruta.read_text("utf-8"))
            filas.append(
                {
                    "brazo": brazo,
                    "conjunto": corrida["conjunto"],
                    "ciclo": corrida["ciclo"],
                    "directorio": corrida["directorio"],
                    "slug": r["slug"],
                    "valida": valida,
                    "capsula": capsula,
                    "solo_r": set(r["config"]["directivas"]) <= SOLO_R,
                    "llamadas": r["operativo"]["llamadas"],
                    "n1": primer_intento(corrida["directorio"], r["slug"]),
                }
            )
    return filas


def tipos_representacion(fila: dict) -> str:
    if fila["capsula"] is not None:
        return "+".join(b["tipo"] for b in fila["capsula"]["representacion_adaptativa"])
    n1 = fila["n1"]
    return "sin cápsula (1.er intento: " + ("+".join(n1["tipos"]) if n1 else "ilegible") + ")"


def render_capsula(c: dict) -> str:
    def cuerpo(b: dict) -> str:
        x = b["cuerpo"]
        if isinstance(x, str):
            return x
        if x and isinstance(x[0], list):
            return "\n".join("  | " + " | ".join(f) + " |" for f in x)
        return "\n".join(f"  - {e}" for e in x)

    out = [
        f"**Título:** {c.get('titulo')}",
        f"**Objetivo:** {c.get('objetivo_aprendizaje')}",
        f"**Activación:** {c.get('activacion')}",
        f"**Concepto central:** {c.get('concepto_central')}",
        "**Representación adaptativa:**",
    ]
    for b in c["representacion_adaptativa"]:
        out.append(f"- `{b['tipo']}` — {b.get('encabezado') or '(sin encabezado)'}\n{cuerpo(b)}")
    ej = c["ejemplo"]
    out.append(
        f"**Ejemplo:** `{ej['tipo']}` — {ej.get('encabezado') or '(sin encabezado)'}\n{cuerpo(ej)}"
    )
    a = c.get("actividad", {})
    out.append(f"**Actividad:** `{a.get('tipo')}` — {a.get('pregunta')}")
    for t in a.get("tarjetas") or []:
        out.append(f"  - tarjeta: {t.get('anverso')} → {t.get('reverso')}")
    for q in a.get("preguntas") or []:
        out.append(f"  - pregunta: {q.get('enunciado')} (correcta: {q.get('indice_correcta')})")
    out.append(
        "**Fuentes:** "
        + ", ".join(f"{f.get('documento')} p.{f.get('pagina')}" for f in c.get("fuentes", []))
    )
    return "\n\n".join(out)


def escribir_muestras(filas: dict[str, list[dict]], ruta: Path) -> None:
    ruta.parent.mkdir(parents=True, exist_ok=True)
    partes = [
        "# Muestras para lectura humana: ronda 4 (base y E)\n",
        "Una corrida cada una (la 1.ª de S42). Archivo local, ignorado por git.\n",
    ]
    for slug in MUESTRAS:
        partes.append(f"\n## {slug}\n")
        for brazo, lista in filas.items():
            f = next((x for x in lista if x["slug"] == slug and x["ciclo"] == 1), None)
            if f is None:
                continue
            palabras_c = f["n1"]["palabras"] if f["n1"] else "—"
            partes.append(
                f"\n### Brazo {brazo} · corrida `{f['directorio']}` · "
                f"{'válida' if f['valida'] else 'SIN CÁPSULA VÁLIDA'} · llamadas {f['llamadas']} · "
                f"palabras del 1.er intento {palabras_c}\n"
            )
            if f["capsula"] is not None:
                partes.append(render_capsula(f["capsula"]))
            else:
                crudas = DATOS / f["directorio"] / slug / "respuestas_crudas.json"
                texto = json.loads(crudas.read_text("utf-8"))[0]["respuesta"]
                partes.append(
                    "Primer intento (no pasó la validación):\n\n```json\n" + texto + "\n```"
                )
    ruta.write_text("\n".join(partes), "utf-8")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    ap.add_argument("--estado", default=str(SALIDA / "piloto_base_E_estado.json"))
    ap.add_argument("--base", default="base")
    ap.add_argument("--e", default="E")
    ap.add_argument("--muestras", default=str(SALIDA / "muestras_ronda4.md"))
    args = ap.parse_args()
    estado = json.loads(Path(args.estado).read_text("utf-8"))
    filas = {b: cargar_brazo(estado, b) for b in (args.base, args.e)}
    base, e = filas[args.base], filas[args.e]
    print(
        f"HEAD del piloto: {estado.get('head')} · gasto US$ {sum(c['costo'] for c in estado['corridas'].values()):.3f}"
    )

    def resumen(nombre: str, lista: list[dict]) -> dict:
        med = [f for f in lista if f["n1"]]
        return {
            "n": len(lista),
            "medibles": len(med),
            "desbordes": sum(f["n1"]["palabras"] > 300 for f in med),
            "bajo150": sum(f["n1"]["palabras"] < 150 for f in med),
            "invalidas": sum(not f["valida"] for f in lista),
            "reparaciones": sum(f["llamadas"] - 1 for f in lista),
            "media": st.mean(f["n1"]["palabras"] for f in med) if med else float("nan"),
        }

    rb, re_ = resumen(args.base, base), resumen(args.e, e)
    print("\n== Métricas por brazo (perfiles-corrida)")
    for nombre, r in ((args.base, rb), (args.e, re_)):
        print(
            f"  {nombre:<6} n={r['n']} · 1.os intentos >300: {r['desbordes']}/{r['medibles']} · "
            f"<150: {r['bajo150']} · sin cápsula válida: {r['invalidas']} · "
            f"reparaciones {r['reparaciones']} · media del 1.er intento {r['media']:.0f}"
        )

    # glosario presente en las válidas de E
    validas_e = [f for f in e if f["valida"] and f["capsula"] is not None]
    sin_glosario = [
        f
        for f in validas_e
        if not any(b["tipo"] == "glosario" for b in f["capsula"]["representacion_adaptativa"])
    ]
    # estables de la base perdidos en E
    por_perfil_b = {}
    for f in base:
        por_perfil_b.setdefault((f["conjunto"], f["slug"]), []).append(f["valida"])
    por_perfil_e = {}
    for f in e:
        por_perfil_e.setdefault((f["conjunto"], f["slug"]), []).append(f["valida"])
    estables = {k for k, v in por_perfil_b.items() if all(v)}
    perdidos = sorted(k for k in estables if not any(por_perfil_e.get(k, [True])))

    print("\n== Veredicto")
    c1 = re_["desbordes"] <= UMBRAL_DESBORDES
    c2 = re_["invalidas"] <= UMBRAL_INVALIDAS
    c3 = not sin_glosario
    c4 = not perdidos
    marca = lambda ok: "✅" if ok else "❌"  # noqa: E731
    print(
        f"  1. primeros intentos >300: {re_['desbordes']} de {re_['medibles']} (≤ {UMBRAL_DESBORDES}) {marca(c1)}"
    )
    print(
        f"  2. cápsulas sin ninguna válida: {re_['invalidas']} de {re_['n']} (≤ {UMBRAL_INVALIDAS}) {marca(c2)}"
    )
    print(
        f"  3. glosario en todas las válidas de {args.e}: {len(validas_e) - len(sin_glosario)}/{len(validas_e)} {marca(c3)}"
    )
    print(
        f"  4. perfiles estables perdidos (inválidos en las 2 corridas de {args.e}): {perdidos or 'ninguno'} {marca(c4)}"
    )
    paso = c1 and c2 and c3 and c4
    print(
        f"  ⇒ {'EL PILOTO PASA' if paso else 'EL PILOTO NO PASA'}: "
        + (
            "se muestra el costo de la ronda completa con S45 y se espera el OK del autor."
            if paso
            else "no se itera; se restaura el estado base y H1 queda como limitación conocida."
        )
    )

    print("\n== Informativas")
    print(
        f"  primeros intentos bajo 150 palabras: {args.base} {rb['bajo150']}/{rb['medibles']} · {args.e} {re_['bajo150']}/{re_['medibles']}"
    )
    entradas_1 = Counter(n for f in e if f["n1"] for n in f["n1"]["entradas"])
    entradas_f = Counter(
        len(b["cuerpo"]) if isinstance(b["cuerpo"], list) else "texto"
        for f in validas_e
        for b in f["capsula"]["representacion_adaptativa"]
        if b["tipo"] == "glosario"
    )
    tot1, totf = sum(entradas_1.values()), sum(entradas_f.values())
    print(
        f"  entradas por glosario, 1.os intentos de {args.e}: {dict(sorted(entradas_1.items(), key=str))}"
        + (
            f" → exactamente 3 en {entradas_1.get(3, 0)}/{tot1} ({100 * entradas_1.get(3, 0) / tot1:.0f} %)"
            if tot1
            else ""
        )
    )
    print(
        f"  entradas por glosario, cápsulas válidas de {args.e}: {dict(sorted(entradas_f.items(), key=str))}"
        + (
            f" → exactamente 3 en {entradas_f.get(3, 0)}/{totf} ({100 * entradas_f.get(3, 0) / totf:.0f} %)"
            if totf
            else ""
        )
    )

    print(
        "\n  composición de representacion_adaptativa en los perfiles «solo R» (corrida 1 · corrida 2):"
    )
    perfiles = sorted({(f["conjunto"], f["slug"]) for f in e if f["solo_r"]})
    solo_gl = total = 0
    for conj, slug in perfiles:
        celdas = []
        for brazo_lista in (base, e):
            fs = sorted(
                (f for f in brazo_lista if f["slug"] == slug and f["conjunto"] == conj),
                key=lambda f: f["ciclo"],
            )
            celdas.append(" · ".join(tipos_representacion(f) for f in fs))
        print(f"    {conj} {slug[2:]:<18} {args.base}: {celdas[0]:<34} {args.e}: {celdas[1]}")
    for f in e:
        if f["solo_r"] and f["capsula"] is not None:
            total += 1
            solo_gl += [b["tipo"] for b in f["capsula"]["representacion_adaptativa"]] == [
                "glosario"
            ]
    print(
        f"  {args.e}, perfiles «solo R» con cápsula válida: representación = solo glosario en {solo_gl}/{total}"
    )

    # palabras que bajó E frente a A (ronda 2), pareado por perfil
    a_n1: dict[tuple[str, str], list[int]] = {}
    for conj, dirs in A_RONDA2.items():
        for d in dirs:
            for r in json.loads((DATOS / d / "resumen.json").read_text("utf-8"))["resultados"]:
                p1 = primer_intento(d, r["slug"])
                if p1:
                    a_n1.setdefault((conj, r["slug"]), []).append(p1["palabras"])
    e_n1: dict[tuple[str, str], list[int]] = {}
    for f in e:
        if f["n1"]:
            e_n1.setdefault((f["conjunto"], f["slug"]), []).append(f["n1"]["palabras"])
    difs = [st.mean(a_n1[k]) - st.mean(v) for k, v in e_n1.items() if k in a_n1]
    if difs:
        print(
            f"\n  palabras que bajó {args.e} frente a A (1.er intento, pareado, n={len(difs)} perfiles): "
            f"media {st.mean(difs):+.1f} · mediana {st.median(difs):+.1f}"
        )

    escribir_muestras(filas, Path(args.muestras))
    print(f"\n  muestras para lectura humana: {args.muestras}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
