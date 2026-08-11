"""Carga el catálogo de objetivos de aprendizaje desde un CSV.

El catálogo se carga a mano y no se infiere desde los documentos: es
información curricular institucional (cap. 12), y dejar que un LLM invente los
objetivos de una asignatura destruiría el «determinismo curricular» que
justifica todo el modelo relacional del cap. 13.

Formato del CSV (encabezado obligatorio, separador coma, codificación UTF-8):

    codigo_objetivo,asignatura,unidad,tema,descripcion,nivel_taxonomico
    BD-U3-01,Bases de Datos,Unidad 3: Normalización,Primera forma normal,...,aplicar

`codigo_objetivo` es la clave natural: volver a cargar el mismo archivo
actualiza los objetivos existentes en vez de duplicarlos, para que corregir una
descripción no obligue a limpiar la tabla.

Uso:
    python scripts/cargar_objetivos.py data/objetivos_bd.csv
    python scripts/cargar_objetivos.py data/objetivos_bd.csv --dry-run
"""

import argparse
import csv
import sys
from pathlib import Path

# Permite ejecutar el script sin instalar el paquete (python scripts/...).
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from sqlalchemy import select  # noqa: E402

from studify.db.models import ObjetivoAprendizaje  # noqa: E402
from studify.db.session import SessionLocal  # noqa: E402

COLUMNAS_REQUERIDAS = {"codigo_objetivo", "asignatura", "unidad", "tema"}

# Límites de la tabla 17.5, para fallar con un mensaje claro en vez de con un
# error de Postgres a mitad de la carga.
LARGOS = {
    "codigo_objetivo": 30,
    "asignatura": 100,
    "unidad": 100,
    "tema": 150,
    "nivel_taxonomico": 50,
}


def leer_csv(ruta: Path) -> list[dict[str, str]]:
    with ruta.open(encoding="utf-8-sig", newline="") as fh:
        lector = csv.DictReader(fh)
        faltantes = COLUMNAS_REQUERIDAS - set(lector.fieldnames or [])
        if faltantes:
            raise SystemExit(
                f"al CSV le faltan columnas obligatorias: {', '.join(sorted(faltantes))}"
            )
        filas = [
            {k: (v or "").strip() for k, v in fila.items() if k is not None}
            for fila in lector
        ]

    for numero, fila in enumerate(filas, start=2):  # 1 es el encabezado
        for columna in sorted(COLUMNAS_REQUERIDAS):
            if not fila.get(columna):
                raise SystemExit(f"fila {numero}: '{columna}' no puede ir vacío")
        for columna, maximo in LARGOS.items():
            valor = fila.get(columna) or ""
            if len(valor) > maximo:
                raise SystemExit(
                    f"fila {numero}: '{columna}' tiene {len(valor)} caracteres y "
                    f"el máximo es {maximo}"
                )

    codigos = [f["codigo_objetivo"] for f in filas]
    repetidos = sorted({c for c in codigos if codigos.count(c) > 1})
    if repetidos:
        raise SystemExit(f"códigos repetidos dentro del CSV: {', '.join(repetidos)}")

    return filas


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("csv", type=Path, help="ruta del CSV con los objetivos")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="valida y muestra lo que haría, sin escribir en la base",
    )
    args = parser.parse_args()

    if not args.csv.exists():
        raise SystemExit(f"no existe el archivo {args.csv}")

    filas = leer_csv(args.csv)
    print(f"CSV válido: {len(filas)} objetivos")

    with SessionLocal() as db:
        existentes = {
            o.codigo_objetivo: o
            for o in db.scalars(
                select(ObjetivoAprendizaje).where(
                    ObjetivoAprendizaje.codigo_objetivo.in_(
                        [f["codigo_objetivo"] for f in filas]
                    )
                )
            ).all()
        }

        nuevos = actualizados = 0
        for fila in filas:
            objetivo = existentes.get(fila["codigo_objetivo"])
            datos = {
                "asignatura": fila["asignatura"],
                "unidad": fila["unidad"],
                "tema": fila["tema"],
                "descripcion": fila.get("descripcion") or None,
                "nivel_taxonomico": fila.get("nivel_taxonomico") or None,
            }
            if objetivo is None:
                nuevos += 1
                if not args.dry_run:
                    db.add(
                        ObjetivoAprendizaje(
                            codigo_objetivo=fila["codigo_objetivo"],
                            estado="activo",
                            **datos,
                        )
                    )
            else:
                actualizados += 1
                if not args.dry_run:
                    for campo, valor in datos.items():
                        setattr(objetivo, campo, valor)

        if args.dry_run:
            print(f"[dry-run] se crearían {nuevos} y se actualizarían {actualizados}")
            return

        db.commit()
        print(f"Listo: {nuevos} creados, {actualizados} actualizados")


if __name__ == "__main__":
    main()
