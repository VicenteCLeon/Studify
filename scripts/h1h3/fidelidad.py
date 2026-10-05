"""Compara el prompt de una variante contra los `prompt.txt` guardados de corridas reales.

    python scripts/h1h3/fidelidad.py <variante|repo> <corrida> [<corrida> ...]

Sirve para comprobar que una variante reconstruida reproduce, byte a byte, lo que se midió.
Las únicas diferencias esperadas son las de cambios posteriores a esas corridas.
Necesita la BD y el `.env`.
"""

import difflib
import re
import sys
from decimal import Decimal
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
variante = sys.argv[1]
sys.path.insert(
    0, str(RAIZ / "src") if variante == "repo" else str(RAIZ / "data" / "h1h3" / variante / "src")
)

import studify  # noqa: E402

print("studify desde:", Path(studify.__file__).parent, flush=True)

from sqlalchemy import select  # noqa: E402

from studify.db.models import ObjetivoAprendizaje  # noqa: E402
from studify.db.session import SessionLocal, engine  # noqa: E402
from studify.rag import orchestrator  # noqa: E402
from studify.rag.retriever import recuperar  # noqa: E402
from studify.vark.rules import aplicar_reglas  # noqa: E402
from studify.vark.scoring import PerfilVark  # noqa: E402

engine.echo = False
cache: dict = {}
iguales = distintos = 0
lineas_distintas: dict[str, int] = {}

with SessionLocal() as db:
    obj = db.scalar(
        select(ObjetivoAprendizaje).where(ObjetivoAprendizaje.codigo_objetivo == "BD-U3-02")
    )
    for corrida in sys.argv[2:]:
        for p in sorted((RAIZ / "data" / "pruebas_vark" / corrida).glob("*/prompt.txt")):
            a, r, k = map(int, re.search(r"A(\d+)-R(\d+)-K(\d+)", p.parent.name).groups())
            config = aplicar_reglas(
                PerfilVark(v=Decimal(0), a=Decimal(a), r=Decimal(r), k=Decimal(k))
            )
            canal = config.jerarquia.canal_primario
            if canal not in cache:
                cache[canal] = recuperar(db, id_objetivo=obj.id_objetivo, canal_primario=canal)
            m = orchestrator.construir(
                objetivo=obj, fragmentos=cache[canal], config=config, modelo="deepseek-chat"
            )
            mio = f"### SISTEMA\n{m.sistema}\n\n### USUARIO\n{m.usuario}\n"
            guardado = p.read_text("utf-8").replace("\r\n", "\n")
            if mio == guardado:
                iguales += 1
                continue
            distintos += 1
            for linea in difflib.unified_diff(
                guardado.splitlines(), mio.splitlines(), lineterm="", n=0
            ):
                if linea[:1] in "+-" and linea[:3] not in ("+++", "---"):
                    lineas_distintas[linea[:110]] = lineas_distintas.get(linea[:110], 0) + 1
print(f"\niguales byte a byte: {iguales} | distintos: {distintos}")
for linea, n in sorted(lineas_distintas.items(), key=lambda x: -x[1]):
    print(f"  x{n}  {linea}")
