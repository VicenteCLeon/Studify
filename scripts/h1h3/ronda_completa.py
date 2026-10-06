"""Ronda completa de la ronda 4: base y E sobre S42, S43 y S45, 2 corridas por brazo y conjunto.

    python scripts/h1h3/ronda_completa.py [--brazos base,E] [--tope 1.40]

Orden: 2 ciclos de [S42 base, S42 E, S43 base, S43 E, S45 base, S45 E]. S45 es la Fase C con 24
mezclas de semilla 45. Todo con --sin-audio y --doc fuera de `docs/`. Se detiene si un brazo supera
el doble de su costo esperado, si el gasto total pasa el tope, si se acumulan 3 errores de la
API o si `src/` o `tests/` tienen cambios sin commitear o cambió el HEAD. El estado queda en
data/h1h3/ (ignorado por git) y permite reanudar. Los veredictos los calcula
`comparar_h1h3.py --veredicto-ronda3 --brazos E --ganador E`.
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

# Costo esperado por corrida (US$): S42 y S43 medidos en la ronda 2; S45 estimado por perfiles.
ESPERADO = {
    "base": {"S42": 0.046, "S43": 0.0105, "S45": 0.037},
    "E": {"S42": 0.052, "S43": 0.013, "S45": 0.042},
}
ARGS_CONJUNTO = {
    "S42": ["--semilla", "42"],
    "S43": ["--fases", "C", "--semilla", "43"],
    "S45": ["--fases", "C", "--n-aleatorias", "24", "--semilla", "45"],
}


def git(*args: str) -> str:
    return subprocess.run(["git", *args], cwd=RAIZ, capture_output=True, text=True).stdout.strip()


def comando(arbol: str, conjunto: str, etiqueta: str) -> list[str]:
    informe = SALIDA / "informes" / f"ronda_{etiqueta}.md"
    informe.parent.mkdir(parents=True, exist_ok=True)
    return [
        sys.executable,
        "scripts/h1h3/correr_brazo.py",
        arbol,
        "--live",
        "--sin-audio",
        "--doc",
        str(informe),
        *ARGS_CONJUNTO[conjunto],
    ]


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    ap.add_argument("--brazos", default="base,E")
    ap.add_argument("--tope", type=float, default=1.40)
    args = ap.parse_args()
    brazos = args.brazos.split(",")
    estado_ruta = SALIDA / f"ronda_completa_{'_'.join(brazos)}_estado.json"
    estado = (
        json.loads(estado_ruta.read_text("utf-8"))
        if estado_ruta.exists()
        else {"head": git("rev-parse", "HEAD"), "corridas": {}}
    )
    total_corridas = 2 * 3 * len(brazos)
    print(
        f"RONDA inicio · HEAD {estado['head']} · brazos {brazos} · {total_corridas} corridas · "
        f"ya hechas: {len(estado['corridas'])} · tope US$ {args.tope}",
        flush=True,
    )
    for ciclo in (1, 2):
        for conjunto in ("S42", "S43", "S45"):
            for arbol in brazos:
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
                log = SALIDA / "logs" / f"ronda_{etiqueta}.log"
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
                corridas = list(estado["corridas"].values())
                total = sum(x["costo"] for x in corridas)
                print(
                    f"RUN {etiqueta:<14} {nuevos[0]} · "
                    f"{validas}/{len(res['resultados'])} válidas · "
                    f"{llamadas} llamadas · US$ {costo:.4f} · acumulado {total:.3f} de {args.tope}",
                    flush=True,
                )
                por_brazo = {
                    b: sum(x["costo"] for x in corridas if x["arbol"] == b) for b in brazos
                }
                esperado = {
                    b: sum(ESPERADO[b][x["conjunto"]] for x in corridas if x["arbol"] == b)
                    for b in brazos
                }
                for b in brazos:
                    if por_brazo[b] > 2 * esperado[b]:
                        print(
                            f"STOP: el brazo {b} gastó US$ {por_brazo[b]:.3f}, más del doble de lo "
                            f"esperado (US$ {esperado[b]:.3f})",
                            flush=True,
                        )
                        return 3
                if total > args.tope:
                    print(
                        f"STOP: gasto total US$ {total:.3f} supera el tope de {args.tope}",
                        flush=True,
                    )
                    return 3
                if sum(x["errores"] for x in corridas) >= MAX_ERRORES:
                    print("STOP: errores de la API acumulados", flush=True)
                    return 4
                if conjunto == "S45" and arbol == brazos[-1]:
                    print(
                        f"== CICLO {ciclo} COMPLETO · gasto US$ {total:.3f} de {args.tope} · "
                        "por brazo: " + ", ".join(f"{b}={g:.3f}" for b, g in por_brazo.items()),
                        flush=True,
                    )
    print(f"RONDA COMPLETA · estado en {estado_ruta}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
