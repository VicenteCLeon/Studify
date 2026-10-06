"""Piloto de la ronda 4: 14 perfiles R >= 40 % de S42 y S43, dos brazos, 2 corridas por brazo.

    python scripts/h1h3/piloto.py [--brazos base,E] [--tope 0.15]

Orden intercalado (base, E, base, E); cada corrida es una invocación sobre S42 (9 perfiles) y otra
sobre S43 (5). Todo con --sin-audio y --doc fuera de `docs/`. Se detiene si el gasto supera el
tope, si se acumulan 3 errores de la API o si `src/` o `tests/` tienen cambios sin commitear. El
estado queda en data/h1h3/ (ignorado por git) y permite reanudar; para repetir, borra ese archivo.

Los árboles de las variantes salen de `scripts/h1h3/hacer_variantes.py`. Las métricas y el veredicto
los calcula `scripts/h1h3/metricas_piloto.py`.
"""

import argparse
import json
import subprocess
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
SALIDA = RAIZ / "data" / "h1h3"
DATOS = RAIZ / "data" / "pruebas_vark"
MAX_ERRORES = 3

sys.path.insert(0, str(RAIZ / "scripts"))
import probar_perfiles_vark as bateria  # noqa: E402

SLUGS = {
    "S42": [p.slug for p in bateria.construir_bateria("ABC", 8, 42) if p.r >= 40],
    "S43": [p.slug for p in bateria.construir_bateria("C", 8, 43) if p.r >= 40],
}


def git(*args: str) -> str:
    return subprocess.run(["git", *args], cwd=RAIZ, capture_output=True, text=True).stdout.strip()


def comando(arbol: str, conjunto: str, etiqueta: str) -> list[str]:
    informe = SALIDA / "informes" / f"piloto_{etiqueta}.md"
    informe.parent.mkdir(parents=True, exist_ok=True)
    base = [
        sys.executable,
        "scripts/h1h3/correr_brazo.py",
        arbol,
        "--live",
        "--sin-audio",
        "--doc",
        str(informe),
        "--slugs",
        ",".join(SLUGS[conjunto]),
    ]
    return base + (
        ["--semilla", "42"] if conjunto == "S42" else ["--fases", "C", "--semilla", "43"]
    )


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    ap.add_argument(
        "--brazos", default="base,E", help="los dos brazos, en el orden de la intercalación"
    )
    ap.add_argument("--tope", type=float, default=0.15, help="gasto máximo en USD")
    args = ap.parse_args()
    brazos = args.brazos.split(",")
    estado_ruta = SALIDA / f"piloto_{'_'.join(brazos)}_estado.json"
    estado_ruta.parent.mkdir(parents=True, exist_ok=True)
    estado = (
        json.loads(estado_ruta.read_text("utf-8"))
        if estado_ruta.exists()
        else {"head": git("rev-parse", "HEAD"), "corridas": {}}
    )
    print(
        f"PILOTO inicio · HEAD {estado['head']} · brazos {brazos} · "
        f"S42 {len(SLUGS['S42'])} perfiles"
        f" + S43 {len(SLUGS['S43'])} · tope US$ {args.tope}",
        flush=True,
    )
    for ciclo in (1, 2):
        for arbol in brazos:
            for conjunto in ("S42", "S43"):
                etiqueta = f"{arbol}_c{ciclo}_{conjunto}"
                if etiqueta in estado["corridas"]:
                    continue
                if (
                    git("status", "--short", "--", "src", "tests")
                    or git("rev-parse", "HEAD") != estado["head"]
                ):
                    print("STOP: cambió HEAD o hay cambios sin commitear en src/tests", flush=True)
                    return 2
                antes = {d.name for d in DATOS.iterdir()}
                log = SALIDA / "logs" / f"piloto_{etiqueta}.log"
                log.parent.mkdir(parents=True, exist_ok=True)
                with log.open("w", encoding="utf-8") as f:
                    proc = subprocess.run(
                        comando(arbol, conjunto, etiqueta),
                        cwd=RAIZ,
                        stdout=f,
                        stderr=subprocess.STDOUT,
                    )
                nuevos = sorted(
                    d
                    for d in {d.name for d in DATOS.iterdir()} - antes
                    if (DATOS / d / "resumen.json").exists()
                )
                if proc.returncode != 0 or len(nuevos) != 1:
                    print(
                        f"STOP: {etiqueta} código {proc.returncode}, directorios nuevos={nuevos}",
                        flush=True,
                    )
                    return 2
                res = json.loads((DATOS / nuevos[0] / "resumen.json").read_text("utf-8"))
                p = res.get("precios", {"entrada": 0.28, "salida": 0.42})
                costo = sum(
                    r["operativo"]["tokens_entrada"] * p["entrada"] / 1e6
                    + r["operativo"]["tokens_salida"] * p["salida"] / 1e6
                    for r in res["resultados"]
                )
                llamadas = sum(r["operativo"]["llamadas"] for r in res["resultados"])
                errores = sum(
                    any(c["estado"] == "error" for c in r["criterios"].values())
                    for r in res["resultados"]
                )
                validas = sum(
                    r["criterios"]["contrato"]["estado"] == "pasa" for r in res["resultados"]
                )
                estado["corridas"][etiqueta] = {
                    "arbol": arbol,
                    "conjunto": conjunto,
                    "ciclo": ciclo,
                    "directorio": nuevos[0],
                    "costo": round(costo, 4),
                    "llamadas": llamadas,
                    "errores": errores,
                }
                estado_ruta.write_text(json.dumps(estado, indent=1), "utf-8")
                total = sum(x["costo"] for x in estado["corridas"].values())
                print(
                    f"RUN {etiqueta:<14} {nuevos[0]} · "
                    f"{validas}/{len(res['resultados'])} válidas · "
                    f"{llamadas} llamadas · US$ {costo:.4f} · acumulado {total:.4f} de {args.tope}",
                    flush=True,
                )
                if total > args.tope:
                    print(f"STOP: gasto US$ {total:.3f} supera el tope de {args.tope}", flush=True)
                    return 3
                if sum(x["errores"] for x in estado["corridas"].values()) >= MAX_ERRORES:
                    print("STOP: errores de la API acumulados", flush=True)
                    return 4
    print(f"PILOTO COMPLETO · estado en {estado_ruta}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
