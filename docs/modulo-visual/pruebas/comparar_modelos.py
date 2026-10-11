"""Compara la configuración anterior del LLM con la nueva, tarea por tarea.

    anterior   LLM_MODEL=deepseek-chat, sin enviar `thinking`
    nueva      lo que diga el `.env` (deepseek-flash con LLM_THINKING=disabled)

Para cada objetivo de `data/objetivos.csv` genera, con cada configuración, una
cápsula real (perfil V puro, por el flujo de `generator.generar`) y una
especificación visual (el paso LLM de `generar_specs_llm.py`). Mide éxito,
reparaciones, tokens, costo y segundos.

La configuración nueva se construye sin argumentos, igual que en producción:
si el `.env` o `config.py` están mal, falla aquí. El orden de las dos
configuraciones se alterna entre objetivos, para que el caché de entrada de
DeepSeek no favorezca siempre a la misma.

No escribe en la base de datos ni en `specs_llm/`. Los resultados se acumulan
en `resultados/migracion/comparacion.json`: cada corrida agrega filas. Uso
(desde la raíz del repo):

    python docs/modulo-visual/pruebas/comparar_modelos.py
    python docs/modulo-visual/pruebas/comparar_modelos.py --solo BD-U3-01
"""

import argparse
import json
import logging
import os
import sys
import time
from decimal import Decimal
from pathlib import Path

AQUI = Path(__file__).resolve().parent
RAIZ = AQUI.parents[2]
# `Settings` busca el `.env` en el directorio de trabajo.
os.chdir(RAIZ)
sys.path.insert(0, str(AQUI))

import generar_specs_llm as specs  # noqa: E402
from deepseek_medido import TOPES_USD, ClienteMedido, TopeSuperado, gastado  # noqa: E402
from sqlalchemy import select  # noqa: E402

from studify.config import get_settings  # noqa: E402
from studify.db.models import ObjetivoAprendizaje  # noqa: E402
from studify.db.session import SessionLocal  # noqa: E402
from studify.generation.generator import ErrorGeneracion, generar  # noqa: E402
from studify.rag import orchestrator, retriever  # noqa: E402
from studify.vark.rules import aplicar_reglas  # noqa: E402
from studify.vark.scoring import PerfilVark  # noqa: E402

SALIDA = AQUI / "resultados" / "migracion"
TAREA = "migracion"

# (nombre, modelo, thinking). `None` deja lo que diga la configuración.
CONFIGURACIONES = (
    ("anterior", "deepseek-chat", ""),
    ("nueva", None, None),
)

# USD por millón de tokens en horario valle y sin caché: la vara común para
# comparar costos, porque lo cobrado depende de qué prompt quedó en caché.
VALLE_ENTRADA, VALLE_SALIDA = 0.15, 0.60


def _medidas(llamadas: list[dict], segundos: float) -> dict:
    entrada = sum(f["tokens_entrada"] for f in llamadas)
    salida = sum(f["tokens_salida"] for f in llamadas)
    return {
        "llamadas": len(llamadas),
        "tokens_entrada": entrada,
        "tokens_entrada_cache": sum(f["tokens_entrada_cache"] for f in llamadas),
        "tokens_salida": salida,
        "tokens_razonamiento": sum(f["tokens_razonamiento"] for f in llamadas),
        "segundos": round(segundos, 2),
        "costo_usd": sum(f["costo_usd"] for f in llamadas),
        "costo_usd_sin_cache": (entrada * VALLE_ENTRADA + salida * VALLE_SALIDA) / 1_000_000,
        "modelo_respondido": llamadas[-1]["modelo_respondido"] if llamadas else None,
        "fin": [f["fin"] for f in llamadas],
    }


def probar_capsula(cliente: ClienteMedido, objetivo, fragmentos) -> dict:
    config = aplicar_reglas(PerfilVark(v=Decimal(100), a=Decimal(0), r=Decimal(0), k=Decimal(0)))
    prompt = orchestrator.construir(
        objetivo=objetivo, fragmentos=fragmentos, config=config, modelo=cliente.modelo
    )
    primera = len(cliente.llamadas)
    inicio = time.perf_counter()
    try:
        resultado = generar(prompt, cliente=cliente)
    except ErrorGeneracion as exc:
        fila = {"valida": False, "errores_por_intento": exc.errores_por_intento}
    else:
        capsula = resultado.capsula
        fila = {
            "valida": True,
            "reparaciones": resultado.intentos - 1,
            "errores_por_intento": resultado.errores_por_intento,
            "titulo": capsula.titulo,
            "palabras": capsula.palabras_contenido(),
            "bloques": [b.tipo for b in capsula.representacion_adaptativa],
            "capsula": capsula.model_dump(mode="json"),
        }
    return fila | _medidas(cliente.llamadas[primera:], time.perf_counter() - inicio)


def probar_spec(cliente: ClienteMedido, contrato, objetivo, fragmentos) -> dict:
    esquema, esquema_texto, sistema, plantilla = contrato
    usuario = specs.armar_usuario(plantilla, objetivo, fragmentos, esquema_texto)
    primera = len(cliente.llamadas)
    inicio = time.perf_counter()
    resultado = specs.generar_spec(
        cliente,
        sistema,
        usuario,
        esquema,
        {f.id_fragmento for f in fragmentos},
        get_settings().llm_max_repair_attempts,
    )
    spec = resultado["spec"]
    fila = {
        "valida": resultado["valida"],
        "reparaciones": resultado["reparaciones"],
        "errores_por_intento": [i["errores"] for i in resultado["detalle_intentos"]],
        "advertencias": resultado["advertencias"],
        "tipo_de_diagrama": spec["tipo_de_diagrama"] if spec else None,
        "nodos": len(spec["nodos"]) if spec else None,
        "spec": spec,
    }
    return fila | _medidas(cliente.llamadas[primera:], time.perf_counter() - inicio)


def _fila_md(codigo: str, tarea: str, nombre: str, f: dict) -> str:
    if f["valida"]:
        exito = "a la primera" if f["reparaciones"] == 0 else f"{f['reparaciones']} reparación"
    else:
        exito = "**falló**"
    que = (
        f"{f.get('palabras')} palabras"
        if tarea == "cápsula"
        else f"`{f.get('tipo_de_diagrama')}`, {f.get('nodos')} nodos"
    )
    return (
        f"| {codigo} | {tarea} | {nombre} | {exito} | {que if f['valida'] else '—'} | "
        f"{f['tokens_entrada']} + {f['tokens_salida']} | {f['tokens_razonamiento']} | "
        f"{f['costo_usd_sin_cache']:.5f} | {f['costo_usd']:.5f} | {f['segundos']:.1f} |"
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--solo", action="append", help="código de objetivo (repetible)")
    parser.add_argument(
        "--invertir", action="store_true", help="empieza por la configuración nueva"
    )
    args = parser.parse_args()
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)

    contrato = specs.cargar_contrato()
    clientes = {
        nombre: ClienteMedido(modelo=modelo, thinking=thinking, tarea=TAREA)
        for nombre, modelo, thinking in CONFIGURACIONES
    }
    for nombre, cliente in clientes.items():
        print(f"{nombre}: modelo {cliente.modelo} · thinking: {cliente.thinking or 'no se envía'}")

    with SessionLocal() as db:
        objetivos = db.scalars(select(ObjetivoAprendizaje)).all()
        material = {
            o.codigo_objetivo: (o, retriever.recuperar(db, id_objetivo=o.id_objetivo))
            for o in objetivos
            if not args.solo or o.codigo_objetivo in args.solo
        }

    filas: list[dict] = []
    detenido = None
    try:
        for i, (codigo, (objetivo, fragmentos)) in enumerate(sorted(material.items())):
            orden = list(clientes.items())
            if (i + args.invertir) % 2:
                orden.reverse()
            for nombre, cliente in orden:
                for tarea, probar in (
                    ("cápsula", lambda c: probar_capsula(c, objetivo, fragmentos)),  # noqa: B023
                    ("especificación", lambda c: probar_spec(c, contrato, objetivo, fragmentos)),  # noqa: B023
                ):
                    cliente.etiqueta = f"migracion:{tarea}:{codigo}:{nombre}"
                    fila = probar(cliente)
                    fila |= {
                        "codigo_objetivo": codigo,
                        "tarea": tarea,
                        "configuracion": nombre,
                        "modelo_pedido": cliente.modelo,
                        "thinking": cliente.thinking,
                    }
                    filas.append(fila)
                    print(_fila_md(codigo, tarea, nombre, fila))
    except TopeSuperado as exc:
        detenido = str(exc)
        print(f"DETENIDO: {exc}")

    SALIDA.mkdir(parents=True, exist_ok=True)
    registro = SALIDA / "comparacion.json"
    if registro.exists():
        filas = json.loads(registro.read_text(encoding="utf-8"))["filas"] + filas
    registro.write_text(
        json.dumps({"detenido": detenido, "filas": filas}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    md = [
        "| Objetivo | Tarea | Configuración | Éxito | Resultado | Tokens (entrada + salida) | "
        "De razonamiento | US$ sin caché (valle) | US$ cobrado | Segundos |",
        "|---|---|---|---|---|--:|--:|--:|--:|--:|",
    ]
    filas.sort(key=lambda f: (f["codigo_objetivo"], f["tarea"], f["configuracion"]))
    md += [_fila_md(f["codigo_objetivo"], f["tarea"], f["configuracion"], f) for f in filas]
    (SALIDA / "comparacion.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    print(
        f"gastado en esta tarea: US${gastado(tarea=TAREA):.4f} de US${TOPES_USD[TAREA]:.2f} · "
        f"en total: US${gastado():.4f}"
    )
    return 2 if detenido else 0


if __name__ == "__main__":
    raise SystemExit(main())
