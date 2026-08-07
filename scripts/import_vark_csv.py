"""Carga los diagnósticos VARK reales exportados desde Google Forms.

    python scripts/import_vark_csv.py data/data_cuestionarios_43.csv
    python scripts/import_vark_csv.py data/data_cuestionarios_43.csv --dry-run
    python scripts/import_vark_csv.py data/data_cuestionarios_43.csv --reset

Formato esperado (el que exporta Google Forms):

    col 0    Marca temporal
    col 1-4  sociodemográficos (rango etario, género, carrera, año)
    col 5-20 los 16 ítems del instrumento VARK

Las selecciones múltiples dentro de un ítem vienen separadas por `;`, y los
ítems sin responder vienen vacíos — ambas cosas son parte del diseño del
instrumento (cap. 10), no anomalías del archivo.

Persiste en las cuatro entidades del módulo de perfilamiento: `estudiante`,
`diagnostico_vark`, `respuesta_vark` y `configuracion_contenido`.
"""

from __future__ import annotations

import argparse
import csv
import sys
from collections import Counter
from pathlib import Path

# Permite ejecutar el script directamente sin instalar el paquete.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from studify.db.models import (  # noqa: E402
    ConfiguracionContenido,
    DiagnosticoVark,
    Estudiante,
    RespuestaVark,
)
from studify.db.session import SessionLocal  # noqa: E402
from studify.vark.instrumento import canal_de  # noqa: E402
from studify.vark.rules import aplicar_reglas  # noqa: E402
from studify.vark.scoring import ErrorDiagnosticoVacio, Seleccion, calificar  # noqa: E402

COL_MARCA = 0
COL_RANGO_ETARIO = 1
COL_GENERO = 2
COL_CARRERA = 3
COL_ANO = 4
COL_PRIMER_ITEM = 5
TOTAL_ITEMS = 16

# Carreras que el cap. 16.1 agrupa como "área de Ingeniería en Informática".
# Se comparan normalizadas (minúsculas, sin tildes) porque el campo era de
# texto libre en el formulario y llegó con variantes de tipeo.
CARRERAS_INFORMATICA = {
    "ingenieria en informatica",
    "ingenieria civil informatica",
    "ingenieria civil en ciencia de datos",
}

_TILDES = str.maketrans("áéíóúÁÉÍÓÚ", "aeiouAEIOU")


def normalizar(texto: str) -> str:
    return texto.strip().translate(_TILDES).lower()


def es_informatica(carrera: str) -> bool:
    return normalizar(carrera) in CARRERAS_INFORMATICA


def leer_selecciones(fila: list[str]) -> tuple[list[Seleccion], list[str]]:
    """Extrae las selecciones VARK de una fila. Devuelve (selecciones, no_mapeadas)."""
    selecciones: list[Seleccion] = []
    no_mapeadas: list[str] = []

    for offset in range(TOTAL_ITEMS):
        celda = fila[COL_PRIMER_ITEM + offset].strip()
        if not celda:
            continue  # ítem en blanco: permitido por el cap. 10
        for texto in celda.split(";"):
            texto = texto.strip()
            if not texto:
                continue
            mapeo = canal_de(texto)
            if mapeo is None:
                no_mapeadas.append(texto)
                continue
            num_pregunta, letra, canal = mapeo
            selecciones.append(Seleccion(num_pregunta, letra, canal))

    return selecciones, no_mapeadas


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("csv", type=Path, help="CSV exportado desde Google Forms")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="calcula y muestra el resumen sin escribir en la base de datos",
    )
    parser.add_argument(
        "--reset",
        action="store_true",
        help="borra los estudiantes existentes antes de cargar (CASCADE)",
    )
    args = parser.parse_args()

    if not args.csv.exists():
        print(f"ERROR: no existe {args.csv}", file=sys.stderr)
        return 1

    with args.csv.open(encoding="utf-8") as fh:
        filas = list(csv.reader(fh))

    encabezado, datos = filas[0], filas[1:]
    if len(encabezado) < COL_PRIMER_ITEM + TOTAL_ITEMS:
        print(
            f"ERROR: el CSV tiene {len(encabezado)} columnas; se esperaban al menos "
            f"{COL_PRIMER_ITEM + TOTAL_ITEMS} (5 sociodemográficas + 16 ítems)",
            file=sys.stderr,
        )
        return 1

    print(f"Leyendo {args.csv}  ->  {len(datos)} respuestas")

    procesados = []
    errores = []
    for i, fila in enumerate(datos, start=2):  # fila 1 es el encabezado
        selecciones, no_mapeadas = leer_selecciones(fila)
        if no_mapeadas:
            errores.append(
                f"  fila {i}: {len(no_mapeadas)} alternativa(s) fuera de la matriz "
                f"de puntuación -> {no_mapeadas[0]!r}"
            )
            continue
        try:
            puntajes, perfil = calificar(selecciones)
        except ErrorDiagnosticoVacio:
            errores.append(f"  fila {i}: sin ninguna selección en los 16 ítems")
            continue
        procesados.append(
            {
                "fila": i,
                "rango_etario": fila[COL_RANGO_ETARIO].strip() or None,
                "genero": fila[COL_GENERO].strip() or None,
                "carrera": fila[COL_CARRERA].strip() or None,
                "selecciones": selecciones,
                "puntajes": puntajes,
                "perfil": perfil,
                "config": aplicar_reglas(perfil),
            }
        )

    if errores:
        print(f"\n{len(errores)} fila(s) con problemas:")
        for e in errores:
            print(e)

    if not procesados:
        print("\nNo hay nada que cargar.", file=sys.stderr)
        return 1

    resumen(procesados)

    if args.dry_run:
        print("\n--dry-run: no se escribió nada en la base de datos.")
        return 0

    with SessionLocal() as db:
        if args.reset:
            borrados = db.query(Estudiante).delete()
            db.commit()
            print(f"\n--reset: {borrados} estudiante(s) borrado(s) (CASCADE).")

        for reg in procesados:
            # ano_ingreso queda en None a propósito: la tabla 17.1 lo define
            # como "año de ingreso a la universidad", pero el formulario
            # preguntó el **año de carrera** ("4° año o superior (semestres
            # 7+)"). Derivar uno del otro sería inventar un dato que no se
            # recolectó. Ver la nota sobre este desajuste en AVANCE.md §7.
            est = Estudiante(
                rango_etario=reg["rango_etario"],
                genero=reg["genero"],
                carrera=reg["carrera"],
                ano_ingreso=None,
            )
            db.add(est)
            db.flush()

            p, perfil, config = reg["puntajes"], reg["perfil"], reg["config"]
            diag = DiagnosticoVark(
                id_estudiante=est.id_estudiante,
                puntaje_v=p.v,
                puntaje_a=p.a,
                puntaje_r=p.r,
                puntaje_k=p.k,
                porcentaje_v=perfil.v,
                porcentaje_a=perfil.a,
                porcentaje_r=perfil.r,
                porcentaje_k=perfil.k,
            )
            db.add(diag)
            db.flush()

            db.add_all(
                RespuestaVark(
                    id_diagnostico=diag.id_diagnostico,
                    num_pregunta=s.num_pregunta,
                    alternativa=s.alternativa,
                    canal_mapeado=s.canal,
                )
                for s in reg["selecciones"]
            )
            db.add(
                ConfiguracionContenido(
                    id_diagnostico=diag.id_diagnostico,
                    peso_texto=config.pesos.texto,
                    peso_visual=config.pesos.visual,
                    peso_narrativo=config.pesos.narrativo,
                    peso_practico=config.pesos.practico,
                    recursos_visuales=config.recursos_visuales,
                    palabras_texto=config.palabras_texto,
                    componentes_practicos=config.componentes_practicos,
                    audio_activo=config.audio_activo,
                    tono_narrativo=config.tono_narrativo,
                    canales_activos=config.canales_activos,
                )
            )

        db.commit()
        print(f"\nCargados {len(procesados)} diagnósticos en la base de datos.")

    return 0


def resumen(procesados: list[dict]) -> None:
    """Reproduce las tablas 16.1–16.3 del informe con los datos cargados."""
    info = [r for r in procesados if r["carrera"] and es_informatica(r["carrera"])]

    print()
    print("=" * 70)
    print(f"MUESTRA: n={len(procesados)}   Ing. Informática: n={len(info)}")
    print("=" * 70)

    for etiqueta, subset in [
        (f"Muestra total (n={len(procesados)})", procesados),
        (f"Ing. Informática (n={len(info)})", info),
    ]:
        if not subset:
            continue
        n = len(subset)
        prom = {
            canal: sum(getattr(r["puntajes"], canal.lower()) for r in subset) / n
            for canal in "VARK"
        }
        orden = sorted("VARK", key=lambda c: -prom[c])
        print(f"\n--- {etiqueta} ---")
        print("  Promedios por dimensión (tabla 16.3):")
        for canal in "VARK":
            print(f"    {canal}: {prom[canal]:5.2f}")
        print(f"  Jerarquía de canales: {' > '.join(orden)}")

        print("  Distribución de perfiles (tabla 16.2):")
        dist = Counter(r["config"].jerarquia.etiqueta for r in subset)
        for perfil_etq, cuenta in dist.most_common():
            tipo = "Unimodal" if "+" not in perfil_etq else "Multimodal"
            print(f"    {perfil_etq:10} {cuenta:3}  ({cuenta / n * 100:4.1f}%)  {tipo}")

    print()
    print("--- Configuración de contenido generada ---")
    tonos = Counter(r["config"].tono_narrativo for r in procesados)
    print(f"  tono_narrativo: {dict(tonos.most_common())}")
    palabras = [r["config"].palabras_texto for r in procesados]
    print(
        f"  palabras_texto: min={min(palabras)} max={max(palabras)} "
        f"media={sum(palabras) / len(palabras):.0f}"
    )
    visuales = Counter(r["config"].recursos_visuales for r in procesados)
    print(f"  recursos_visuales: {dict(sorted(visuales.items()))}")
    practicos = Counter(r["config"].componentes_practicos for r in procesados)
    print(f"  componentes_practicos: {dict(sorted(practicos.items()))}")

    total_sel = [r["puntajes"].total for r in procesados]
    print(
        f"  selecciones por persona: min={min(total_sel)} max={max(total_sel)} "
        f"media={sum(total_sel) / len(total_sel):.1f} (sobre 16 ítems)"
    )


if __name__ == "__main__":
    raise SystemExit(main())
