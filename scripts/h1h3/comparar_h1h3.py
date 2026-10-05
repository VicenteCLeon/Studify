"""Comparador de la ronda H1+H3: métricas C1–C4 por corrida, veredicto por brazo y efecto del fix.

    # tabla por brazo (cada etiqueta lleva una o más corridas de data/pruebas_vark)
    python scripts/h1h3/comparar_h1h3.py ETIQUETA=corrida1,corrida2 [ETIQUETA=...]

    # veredicto de los criterios de PRUEBAS_VARK (Etapa 1, ronda 2);
    # cada argumento es CONJUNTO:BRAZO=corridas
    python scripts/h1h3/comparar_h1h3.py --veredicto S42:base=r1,r2 S42:A=r3,r4 S42:B=r5,r6 \\
        S43:base=... S43:A=... S43:B=... [--rescate B=C1:C_C02_A9-R49-K42:rA,rB,rC,rD,rE]

    # efecto del fix de la actividad aplicada: base nueva contra base vieja, subconjunto K >= 40 %
    python scripts/h1h3/comparar_h1h3.py --efecto-fix NUEVA=r1,r2 VIEJA=r3,r4

Definiciones (las de PRUEBAS_VARK.md, Etapa 1; el original `comparar_etapa1.py` se perdió y
esta versión se validó reproduciendo las tablas publicadas de base, A y B en S42 y S43):
  valida   = criterios.contrato.estado == "pasa"
  C1       = glosario en las cápsulas válidas con R >= 40
  C2       = |desviación| <= 15 % del objetivo del prompt, válidas con R > 0 (no bloqueante)
  C2b/C2c  = desvío medio (%) de las válidas con R > 0 y R >= 60 / K >= 60
  C3       = (R > 0) válidas / reparaciones = llamadas - perfiles / citas inventadas
  C4a      = K >= 40, válidas, criterio «ejercicios» en 'pasa'
  C4b      = A >= 25, válidas, guion >= 40 palabras, no JSON, cobertura >= 50 %
  C4c      = A >= 40, válidas, bloque analogía
"""

import json
import re
import sys
from pathlib import Path
from statistics import mean

DATOS = Path(__file__).resolve().parents[2] / "data" / "pruebas_vark"
TODAS = ("C1", "C4a", "C4b", "C4c")  # criterios «todas»: sujetos a R1
C3_ABSOLUTO_S42 = {"validas": 25, "reparaciones": 4}  # umbrales de la Etapa 1, definidos sobre S42


def cargar(corrida: str) -> list[dict]:
    return json.loads((DATOS / corrida / "resumen.json").read_text("utf-8"))["resultados"]


def valida(r: dict) -> bool:
    return r["criterios"]["contrato"]["estado"] == "pasa"


def guion_ok(r: dict) -> bool:
    a = r["audio"]
    return (
        a["palabras_guion"] >= 40
        and not a["guion"].lstrip().startswith("{")
        and r["cobertura_lexica"] >= 0.5
    )


# Cada criterio «todas»: (a quién se le exige, cómo se cumple). Sirve para el conteo y los rescates.
EXIGE = {
    "C1": (lambda r: r["pcts"]["R"] >= 40, lambda r: valida(r) and "glosario" in r["tipos_bloque"]),
    "C4a": (
        lambda r: r["pcts"]["K"] >= 40,
        lambda r: valida(r) and r["criterios"]["ejercicios"]["estado"] == "pasa",
    ),
    "C4b": (lambda r: r["pcts"]["A"] >= 25, lambda r: valida(r) and guion_ok(r)),
    "C4c": (
        lambda r: r["pcts"]["A"] >= 40,
        lambda r: valida(r) and r["marcadores"]["A"]["analogia"],
    ),
}


def dev(r: dict) -> float:
    m = r["metricas_validador"]
    return 100 * m["desviacion_palabras"] / m["palabras_objetivo"]


def metricas(res: list[dict]) -> dict:
    rp = [r for r in res if r["pcts"]["R"] > 0]
    rv = [r for r in rp if valida(r)]
    out: dict = {}

    for crit, (aplica, cumple) in EXIGE.items():
        grupo = [r for r in res if aplica(r)]
        # Se miden las cápsulas válidas; los perfiles sin cápsula van en C1_sin_valida.
        medidas = [r for r in grupo if valida(r)]
        out[crit] = (sum(cumple(r) for r in medidas), len(medidas))
        out[f"{crit}_fallan"] = [r["slug"] for r in medidas if not cumple(r)]
    out["C1_sin_valida"] = (
        sum(not valida(r) for r in res if r["pcts"]["R"] >= 40),
        sum(r["pcts"]["R"] >= 40 for r in res),
    )

    out["C2"] = (sum(abs(dev(r)) <= 15 for r in rv), len(rv))
    for nombre, canal in (("C2b", "R"), ("C2c", "K")):
        g = [r for r in rv if r["pcts"][canal] >= 60]
        out[nombre] = (round(mean(dev(r) for r in g), 1) if g else None, len(g))

    out["C3_validas"] = (len(rv), len(rp))
    out["C3_reparaciones"] = (sum(r["operativo"]["llamadas"] - 1 for r in rp), len(rp))
    out["C3_citas"] = (sum(r["metricas_validador"]["citas_inventadas"] for r in rv), len(rv))
    out["todas_validas"] = (sum(valida(r) for r in res), len(res))
    out["glosarios_sin_directiva"] = (
        sum(
            "glosario" in r["tipos_bloque"] and "glosario" not in r["config"]["directivas"]
            for r in res
            if valida(r)
        ),
        sum(valida(r) for r in res),
    )
    out["_validos"] = {r["slug"] for r in res if valida(r)}

    # Zona K 31-39 % y subconjunto K >= 40 % (efecto del fix de la actividad aplicada).
    zona = [r for r in res if 31 <= r["pcts"]["K"] <= 39]
    out["Z_validas"] = (sum(valida(r) for r in zona), len(zona))
    out["Z_flashcards_y_quiz"] = (
        sum(valida(r) and r["tipo_actividad"] == "flashcards_y_quiz" for r in zona),
        len(zona),
    )
    out["Z_reparaciones"] = (sum(r["operativo"]["llamadas"] - 1 for r in zona), len(zona))
    k40 = [r for r in res if r["pcts"]["K"] >= 40]
    out["K40_validas"] = (sum(valida(r) for r in k40), len(k40))
    out["K40_reparaciones"] = (sum(r["operativo"]["llamadas"] - 1 for r in k40), len(k40))
    contados = [
        tuple(map(int, m.groups()))
        for r in k40
        if valida(r)
        if (m := re.search(r"prácticos (\d+)/(\d+)", r["criterios"]["ejercicios"]["detalle"]))
    ]
    out["K40_practicos"] = (
        round(mean(c for c, _ in contados), 2) if contados else None,
        len(contados),
    )
    return out


def fmt(v) -> str:
    if isinstance(v, (list, set)):
        return ",".join(sorted(v)) or "—"
    a, b = v
    return f"{a}/{b}" if isinstance(a, int) else f"{a}% (n={b})"


def tabla(brazos: dict[str, list[str]]) -> None:
    claves = [
        "C1",
        "C1_sin_valida",
        "C2",
        "C2b",
        "C2c",
        "C3_validas",
        "C3_reparaciones",
        "C3_citas",
        "C4a",
        "C4b",
        "C4c",
        "glosarios_sin_directiva",
        "todas_validas",
    ]
    for etiqueta, corridas in brazos.items():
        ms = [metricas(cargar(c)) for c in corridas]
        print(f"\n=== {etiqueta} ({len(ms)} corrida/s: {', '.join(corridas)})")
        for k in claves:
            nums = [m[k][0] for m in ms if m[k][0] is not None]
            prom = f"   promedio {mean(nums):.2f}" if len(ms) > 1 and nums else ""
            print(f"  {k:<24} {' | '.join(fmt(m[k]) for m in ms)}{prom}")
        if len(ms) > 1:
            print(
                "  perfiles válidos en TODAS las corridas: "
                f"{len(set.intersection(*[m['_validos'] for m in ms]))}"
            )


def parsear(args: list[str]) -> dict[str, list[str]]:
    out = {}
    for a in args:
        etiqueta, _, corridas = a.partition("=")
        out[etiqueta] = corridas.split(",")
    return out


# ------------------------------------------------------------------ veredicto de la ronda
def c3_de_conjunto(conjunto: str, base: list[dict], brazo: list[dict]) -> tuple[bool, list[str]]:
    """C3: lo más estricto entre los umbrales absolutos de la Etapa 1 (solo S42) y la base nueva."""
    prom = lambda ms, k: mean(m[k][0] for m in ms)  # noqa: E731
    umbral_v = prom(base, "C3_validas") - 1
    umbral_r = prom(base, "C3_reparaciones") + 2
    if conjunto == "S42":
        umbral_v = max(umbral_v, C3_ABSOLUTO_S42["validas"])
        umbral_r = min(umbral_r, C3_ABSOLUTO_S42["reparaciones"])
    notas, ok = [], True
    v, rep = prom(brazo, "C3_validas"), prom(brazo, "C3_reparaciones")
    for etiqueta, cond, texto in (
        ("válidas", v >= umbral_v, f"{v:.1f} (umbral ≥ {umbral_v:.1f})"),
        ("reparaciones", rep <= umbral_r, f"{rep:.1f} (umbral ≤ {umbral_r:.1f})"),
        ("citas inventadas", all(m["C3_citas"][0] == 0 for m in brazo), "0 en todas las corridas"),
    ):
        ok &= cond
        notas.append(f"{conjunto} {etiqueta}: {texto} {'✅' if cond else '❌'}")
    estables = set.intersection(*[m["_validos"] for m in base])
    perdidos = {p for m in brazo for p in estables - m["_validos"]}
    ok &= not perdidos
    notas.append(
        f"{conjunto} perfiles estables de la base perdidos: "
        f"{sorted(perdidos) or 'ninguno'} {'✅' if not perdidos else '❌'}"
    )
    return ok, notas


def veredicto(grupos: dict[str, list[str]], rescates: dict[str, list[str]]) -> None:
    conjuntos = sorted({k.split(":")[0] for k in grupos})
    metr = {k: [metricas(cargar(c)) for c in v] for k, v in grupos.items()}
    resultado: dict[str, bool] = {}
    for brazo in ("A", "B"):
        print(f"\n######## BRAZO {brazo}")
        c3_ok, ok_todas = True, True
        # R1: cada par (criterio, corrida) con un único perfil fallido es un rescate posible.
        # Con dos o más perfiles, o más de 2 rescates en el brazo, cuenta como falla.
        casos_rescate: list[tuple[str, str, str, int]] = []
        for conj in conjuntos:
            ok, notas = c3_de_conjunto(conj, metr[f"{conj}:base"], metr[f"{conj}:{brazo}"])
            c3_ok &= ok
            for nota in notas:
                print(f"  C3 {nota}")
        for crit in TODAS:
            hubo = False
            for conj in conjuntos:
                for i, m in enumerate(metr[f"{conj}:{brazo}"], start=1):
                    fallan = m[f"{crit}_fallan"]
                    if len(fallan) == 1:
                        hubo = True
                        casos_rescate.append((crit, conj, fallan[0], i))
                        print(f"  {crit}: {conj} corrida {i}: UN fallo ({fallan[0]}), candidato R1")
                    elif fallan:
                        hubo = ok_todas = False
                        print(f"  {crit}: {conj} corrida {i}: {len(fallan)} fallos {fallan} ❌")
            if not hubo and ok_todas:
                print(f"  {crit}: todas las corridas cumplen ✅")
        if len(casos_rescate) > 2:
            ok_todas = False
            print(f"    {len(casos_rescate)} rescates necesarios (máximo 2) → cuenta como falla ❌")
        else:
            for crit, conj, slug, _ in casos_rescate:
                clave = f"{crit}:{slug}"
                previos = rescates.get(brazo, [])
                datos = next((v for v in previos if v.startswith(clave + ":")), None)
                if datos is None:
                    print(f"    rescate pendiente: {clave} ({conj}; 5 repeticiones de {brazo})")
                    ok_todas = False
                    continue
                corridas = datos.split(":", 2)[2].split(",")
                filas = [r for c in corridas for r in cargar(c) if r["slug"] == slug]
                n_ok = sum(EXIGE[crit][1](r) for r in filas)
                paso = len(filas) == 5 and n_ok >= 4
                ok_todas &= paso
                print(f"    rescate {clave}: {n_ok}/{len(filas)} {'✅' if paso else '❌'}")
        c1_c4 = ok_todas
        resultado[brazo] = c3_ok and c1_c4
        print(
            f"  ⇒ C1+C4: {'cumple' if c1_c4 else 'NO cumple'}"
            f" · C3: {'cumple' if c3_ok else 'NO cumple'}"
        )
        c2 = [mean(m["C2"][0] / m["C2"][1] for m in metr[f"{c}:{brazo}"]) for c in conjuntos]
        print(
            "  (C2 no bloqueante, fracción dentro de ±15 %: "
            + ", ".join(f"{c}={x:.2f}" for c, x in zip(conjuntos, c2, strict=True))
            + ")"
        )
    print("\n######## REGLA DE CIERRE")
    if resultado.get("B"):
        print("  Se aplica B (cumple C1, C3 y C4).")
    elif resultado.get("A"):
        print("  B no cumple; se aplica A.")
    else:
        print("  Ningún brazo cumple: se revierte y se analiza.")


def efecto_fix(grupos: dict[str, list[str]]) -> None:
    for etiqueta, corridas in grupos.items():
        ms = [metricas(cargar(c)) for c in corridas]
        print(f"\n=== {etiqueta} — K >= 40 % ({', '.join(corridas)})")
        for k in ("K40_validas", "K40_reparaciones", "C4a"):
            print(f"  {k:<18} {' | '.join(fmt(m[k]) for m in ms)}")
        practicos = " | ".join(f"{m['K40_practicos'][0]} (n={m['K40_practicos'][1]})" for m in ms)
        print(f"  K40_practicos      promedio contado por perfil: {practicos}")
        flash = " | ".join(fmt(m["Z_flashcards_y_quiz"]) for m in ms)
        validas = " | ".join(fmt(m["Z_validas"]) for m in ms)
        print(f"  zona K 31-39: flashcards_y_quiz {flash} · válidas {validas}")


def main() -> None:
    args = sys.argv[1:]
    if not args:
        raise SystemExit(__doc__)
    if args[0] == "--veredicto":
        resto = args[1:]
        rescates: dict[str, list[str]] = {}
        while "--rescate" in resto:
            i = resto.index("--rescate")
            brazo, _, dato = resto[i + 1].partition("=")
            rescates.setdefault(brazo, []).append(dato)
            resto = resto[:i] + resto[i + 2 :]
        veredicto(parsear(resto), rescates)
    elif args[0] == "--efecto-fix":
        efecto_fix(parsear(args[1:]))
    else:
        tabla(parsear(args))


if __name__ == "__main__":
    main()
