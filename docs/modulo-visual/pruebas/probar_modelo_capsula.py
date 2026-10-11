"""Comprueba que el modelo configurado en `LLM_MODEL` genera una cápsula real.

Recorre el flujo existente sin la capa web ni la persistencia: reglas VARK →
`retriever.recuperar` (fragmentos validados de la base) → `orchestrator.construir`
(prompt maestro) → `generation.generator.generar` (modo JSON, validador y hasta
dos reparaciones). Lo único distinto es el cliente: `ClienteMedido` hereda del
real y además anota tokens y costo.

No escribe en la base de datos.

Uso (desde la raíz del repo):

    python docs/modulo-visual/pruebas/probar_modelo_capsula.py
    python docs/modulo-visual/pruebas/probar_modelo_capsula.py --objetivo PROG-U1-02 --canal K
"""

import argparse
import json
import logging
import os
import sys
from decimal import Decimal
from pathlib import Path

AQUI = Path(__file__).resolve().parent
RAIZ = AQUI.parents[2]
# `Settings` busca el `.env` en el directorio de trabajo.
os.chdir(RAIZ)
sys.path.insert(0, str(AQUI))

from deepseek_medido import ClienteMedido, TopeSuperado, gastado  # noqa: E402
from sqlalchemy import select  # noqa: E402

from studify.config import get_settings  # noqa: E402
from studify.db.models import ObjetivoAprendizaje  # noqa: E402
from studify.db.session import SessionLocal  # noqa: E402
from studify.generation.generator import ErrorGeneracion, generar  # noqa: E402
from studify.rag import orchestrator, retriever  # noqa: E402
from studify.vark.rules import aplicar_reglas  # noqa: E402
from studify.vark.scoring import PerfilVark  # noqa: E402

SALIDA = AQUI / "resultados" / "llm"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--objetivo", default="BD-U3-01")
    parser.add_argument("--canal", default="V", choices=["V", "A", "R", "K"])
    parser.add_argument("--modelo", help="por defecto, el de LLM_MODEL")
    parser.add_argument("--reintentos", type=int, help="por defecto, LLM_MAX_REPAIR_ATTEMPTS")
    parser.add_argument("--tarea", default="validacion", help="a qué tope se carga el gasto")
    parser.add_argument(
        "--thinking",
        choices=["enabled", "disabled", ""],
        help="razonamiento del modelo; por defecto, el de LLM_THINKING",
    )
    args = parser.parse_args()
    # En `dev` el motor de SQLAlchemy imprime cada consulta.
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)

    ajustes = get_settings()
    perfil = PerfilVark(**{c.lower(): Decimal(100 if c == args.canal else 0) for c in "VARK"})
    config = aplicar_reglas(perfil)

    with SessionLocal() as db:
        objetivo = db.scalar(
            select(ObjetivoAprendizaje).where(ObjetivoAprendizaje.codigo_objetivo == args.objetivo)
        )
        if objetivo is None:
            print(f"no existe el objetivo {args.objetivo} en la base")
            return 1
        fragmentos = retriever.recuperar(
            db,
            id_objetivo=objetivo.id_objetivo,
            canal_primario=config.jerarquia.canal_primario,
        )

    prompt = orchestrator.construir(
        objetivo=objetivo,
        fragmentos=fragmentos,
        config=config,
        modelo=args.modelo or ajustes.llm_model,
    )
    cliente = ClienteMedido(
        etiqueta=f"capsula:{args.objetivo}:{args.canal}",
        modelo=args.modelo,
        thinking=args.thinking,
        tarea=args.tarea,
    )
    print(
        f"modelo: {cliente.modelo} · modo JSON: {ajustes.llm_json_mode} · "
        f"max_tokens: {ajustes.llm_max_tokens} · thinking: {cliente.thinking or 'no se envía'}"
    )
    print(f"objetivo: {args.objetivo} · perfil {args.canal} puro · {len(fragmentos)} fragmentos")

    informe: dict = {
        "modelo": cliente.modelo,
        "objetivo": args.objetivo,
        "canal": args.canal,
        "max_tokens": ajustes.llm_max_tokens,
        "thinking": cliente.thinking,
    }
    try:
        resultado = generar(prompt, cliente=cliente, max_reintentos=args.reintentos)
    except TopeSuperado as exc:
        print(f"DETENIDO: {exc}")
        return 2
    except ErrorGeneracion as exc:
        print(f"FALLÓ: {exc}")
        informe |= {"valida": False, "errores_por_intento": exc.errores_por_intento}
    else:
        capsula = resultado.capsula
        print(f"VÁLIDA en {resultado.intentos} intento(s), {resultado.segundos:.1f} s")
        print(f"título: {capsula.titulo}")
        print(f"palabras: {capsula.palabras_contenido()} · bloques: "
              f"{[b.tipo for b in capsula.representacion_adaptativa]}")
        informe |= {
            "valida": True,
            "intentos": resultado.intentos,
            "reparaciones": resultado.intentos - 1,
            "errores_por_intento": resultado.errores_por_intento,
            "segundos": round(resultado.segundos, 2),
            "capsula": capsula.model_dump(mode="json"),
        }

    informe["llamadas"] = cliente.llamadas
    informe["costo_usd"] = sum(f["costo_usd"] for f in cliente.llamadas)
    for f in cliente.llamadas:
        print(
            f"  llamada: {f['tokens_entrada']} tokens de entrada ({f['tokens_entrada_cache']} en "
            f"caché), {f['tokens_salida']} de salida ({f['tokens_razonamiento']} de razonamiento), "
            f"fin={f['fin']}, {f['segundos']} s, US${f['costo_usd']:.6f} ({f['tarifa']})"
        )
    print(f"costo de esta prueba: US${informe['costo_usd']:.6f} · acumulado: US${gastado():.6f}")
    variante = f"_thinking-{cliente.thinking}" if cliente.thinking else ""
    salida = SALIDA / f"capsula_{cliente.modelo}_max{ajustes.llm_max_tokens}{variante}.json"
    salida.parent.mkdir(parents=True, exist_ok=True)
    salida.write_text(json.dumps(informe, ensure_ascii=False, indent=2), encoding="utf-8")
    return 0 if informe.get("valida") else 1


if __name__ == "__main__":
    raise SystemExit(main())
