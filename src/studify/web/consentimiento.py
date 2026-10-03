"""Aceptación de los Términos y la Política de Privacidad (marco legal, 02-oct-2026).

Tres piezas, y nada más:

- `pendientes()` dice qué documentos le falta aceptar a un estudiante **en su
  versión vigente** (`web/legal.py`). Subir la versión de un documento lo deja
  pendiente para todos, que es justamente cómo se vuelve a pedir.
- `registrar()` guarda la aceptación: una fila por documento y versión, con la
  hora del servidor en UTC.
- `exigir_vigente` es el guardián de las vistas del estudiante: con aceptación
  pendiente, a `/aceptar` antes de seguir.

Está separado de `sesion.py` a propósito: la sesión dice *quién* es el
visitante y esto dice *qué aceptó*. Cuando el proyecto pase a identificar con
Google Identity, la sesión cambia y esto sigue colgando de `id_estudiante`.
"""

import logging
from datetime import UTC, datetime

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from studify.db.models import AceptacionLegal, Estudiante
from studify.db.session import get_db
from studify.web import legal, sesion

logger = logging.getLogger(__name__)

RUTA_ACEPTAR = "/aceptar"

# Las vistas del estudiante que **no** exigen aceptación previa: el cuestionario
# es donde se acepta por primera vez (la casilla está en su primer paso).
RUTAS_SIN_ACEPTACION = frozenset({"/student/vark"})


def pendientes(db: Session, id_estudiante: int) -> list[legal.Documento]:
    """Los documentos cuya versión vigente este estudiante no ha aceptado."""
    aceptadas = set(
        db.execute(
            select(AceptacionLegal.documento, AceptacionLegal.version).where(
                AceptacionLegal.id_estudiante == id_estudiante
            )
        ).all()
    )
    return [d for d in legal.DOCUMENTOS if (d.clave, d.version) not in aceptadas]


def registrar(
    db: Session,
    id_estudiante: int,
    documentos: tuple[legal.Documento, ...] | None = None,
    *,
    genero: bool = False,
) -> None:
    """Deja constancia de la aceptación, con la hora del servidor en UTC.

    Es idempotente: aceptar dos veces la misma versión (un doble clic, dos
    pestañas) no falla ni duplica, gracias a la restricción única y a
    `ON CONFLICT DO NOTHING`.

    `genero=True` registra además el consentimiento expreso para el dato
    sensible de género, contra la versión vigente de la Política.

    Sin `documentos`, registra todos en su versión vigente. Se lee al llamar y
    no como valor por defecto del parámetro, que quedaría fijo al importar.
    """
    if documentos is None:
        documentos = legal.DOCUMENTOS
    ahora = datetime.now(UTC)
    filas = [
        {
            "id_estudiante": id_estudiante,
            "documento": d.clave,
            "version": d.version,
            "aceptado_en": ahora,
        }
        for d in documentos
    ]
    if genero:
        filas.append(
            {
                "id_estudiante": id_estudiante,
                "documento": "genero",
                "version": legal.PRIVACIDAD.version,
                "aceptado_en": ahora,
            }
        )
    if not filas:
        return
    db.execute(insert(AceptacionLegal).values(filas).on_conflict_do_nothing())
    db.commit()


def destino_seguro(destino: str | None) -> str:
    """Acota el `next` de `/aceptar` a las vistas del estudiante.

    Mismo cuidado que el login del docente: `next` viene en la URL, y sin
    esto `/aceptar?next=https://sitio-falso` sería un redirector abierto.
    """
    if not destino or not destino.startswith("/student/") or destino.startswith("//"):
        return "/student/catalog"
    return destino


def exigir_vigente(request: Request, db: Session = Depends(get_db)) -> None:
    """Guardián de `/student/*`: sin aceptación vigente, a `/aceptar`.

    Va en el `APIRouter` del estudiante y no handler por handler, igual que el
    del docente: una vista nueva queda cubierta por el solo hecho de colgar de
    ese router. Sin sesión no hace nada —cada vista ya manda al cuestionario,
    que es donde se acepta— y tampoco sobre las rutas de `RUTAS_SIN_ACEPTACION`.
    """
    if request.url.path in RUTAS_SIN_ACEPTACION:
        return

    id_estudiante = sesion.estudiante_actual(request)
    if id_estudiante is None or db.get(Estudiante, id_estudiante) is None:
        return

    if not pendientes(db, id_estudiante):
        return

    destino = RUTA_ACEPTAR
    if request.method == "GET":
        destino = f"{RUTA_ACEPTAR}?next={request.url.path}"

    # Mismo motivo que en `auth.requiere_docente`: HTMX seguiría un 303 dentro
    # del XHR y pegaría la pantalla de aceptación dentro de un fragmento.
    if request.headers.get("HX-Request") == "true":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Hay documentos legales nuevos por aceptar.",
            headers={"HX-Redirect": destino},
        )
    raise HTTPException(
        status_code=status.HTTP_303_SEE_OTHER,
        detail="Hay documentos legales nuevos por aceptar.",
        headers={"Location": destino},
    )
