"""Verificación del punto 1c contra el modelo real: 6 perfiles con `actividad_aplicada`.

Reutiliza `scripts/probar_perfiles_vark.ejecutar_perfil` (mismos criterios de la
batería, incluido «ejercicios»), sin audio y sin escribir docs/PRUEBAS_VARK.md.
Se ejecuta desde la raíz del repo. Sin --live no llama al LLM: solo muestra el
prompt de cada perfil y la actividad exigida.

    python scripts/verificar_1c_k.py            # en seco, sin costo
    python scripts/verificar_1c_k.py --live     # 6 generaciones (≤ 18 llamadas)
"""

import json
import sys
from datetime import datetime
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path[:0] = [str(RAIZ / "src"), str(RAIZ / "scripts")]

import probar_perfiles_vark as bateria  # noqa: E402
from sqlalchemy import select  # noqa: E402

from studify.config import get_settings  # noqa: E402
from studify.db.models import ObjetivoAprendizaje  # noqa: E402
from studify.db.session import SessionLocal, engine  # noqa: E402
from studify.rag import orchestrator  # noqa: E402
from studify.rag.retriever import recuperar  # noqa: E402
from studify.vark.rules import aplicar_reglas  # noqa: E402

OBJETIVO = bateria.OBJETIVO_POR_DEFECTO  # BD-U3-02, el de la batería del 03-oct
PERFILES = [
    bateria.Perfil("K", "K100", a=0, r=0, k=100),
    bateria.Perfil("K", "A5-R5-K90", a=5, r=5, k=90),
    bateria.Perfil("K", "A30-R10-K60", a=30, r=10, k=60),
    bateria.Perfil("K", "A10-R40-K50", a=10, r=40, k=50),
    bateria.Perfil("K", "V30-A10-R10-K50", v=30, a=10, r=10, k=50),
    # Regla de respaldo: p_K < 40, pero la directiva sale igual.
    bateria.Perfil("K", "A23-R38-K39", a=23, r=38, k=39),
]


def main() -> int:
    live = "--live" in sys.argv
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    engine.echo = False
    ajustes = get_settings()
    with SessionLocal() as db:
        objetivo = db.scalar(
            select(ObjetivoAprendizaje).where(ObjetivoAprendizaje.codigo_objetivo == OBJETIVO)
        )
        if objetivo is None:
            print(f"No existe el objetivo {OBJETIVO} en esta base", file=sys.stderr)
            return 1

        def obtener_fragmentos(config):
            return recuperar(
                db, id_objetivo=objetivo.id_objetivo,
                canal_primario=config.jerarquia.canal_primario,
            )

        print(f"Objetivo {objetivo.codigo_objetivo} · modelo {ajustes.llm_model} · "
              f"reintentos {ajustes.llm_max_repair_attempts}")
        for p in PERFILES:
            config = aplicar_reglas(p.vark())
            maestro = orchestrator.construir(
                objetivo=objetivo, fragmentos=obtener_fragmentos(config),
                config=config, modelo=ajustes.llm_model,
            )
            print(f"  {p.nombre:<18} actividad_requerida={maestro.actividad_requerida} "
                  f"fragmentos={len(maestro.fragmentos)} huella={maestro.huella[:12]}")
            assert maestro.actividad_requerida == "flashcards_y_quiz", p.nombre
        if not live:
            print("\nEn seco: no se llamó al LLM. Agrega --live para generar.")
            return 0

        from studify.generation.generator import ClienteOpenAILike

        cliente = ClienteOpenAILike()
        dir_corrida = RAIZ / "data/pruebas_vark" / f"{datetime.now():%Y%m%d-%H%M%S}_1c_K"
        dir_corrida.mkdir(parents=True, exist_ok=True)
        resultados = []
        for i, p in enumerate(PERFILES, start=1):
            print(f"[{i}/{len(PERFILES)}] {p.nombre} …", flush=True)
            r = bateria.ejecutar_perfil(
                p, objetivo=objetivo, obtener_fragmentos=obtener_fragmentos,
                cliente=cliente, sintetizar=None, dir_corrida=dir_corrida,
                modelo=ajustes.llm_model,
            )
            resultados.append(r)
            actividad = None
            capsula = r.get("artefactos", {}).get("capsula")
            if capsula:
                actividad = json.loads(Path(capsula).read_text("utf-8"))["actividad"]["tipo"]
            print(f"    veredicto={r['veredicto']} intentos={r.get('intentos')} "
                  f"actividad={actividad} contrato={r['criterios']['contrato']['estado']} "
                  f"ejercicios={r['criterios']['ejercicios']['estado']}", flush=True)
            (dir_corrida / "resumen.json").write_text(
                json.dumps(resultados, ensure_ascii=False, indent=2, default=str), "utf-8"
            )
        validas = sum(r["criterios"]["contrato"]["estado"] == "pasa" for r in resultados)
        primera = sum(r.get("intentos") == 1 for r in resultados)
        print(f"\nVálidas {validas}/{len(resultados)} · a la primera {primera} · "
              f"resultados en {dir_corrida}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
