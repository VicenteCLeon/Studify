"""Punto de entrada de la API.

Arranque:  uvicorn studify.main:app --reload --app-dir src
"""

import os

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import text

from studify.api.routers import capsules, diagnostics, knowledge
from studify.config import get_settings
from studify.db.session import engine
from studify.web import sesion
from studify.web.deps import templates
from studify.web.routers import auth, legal, student, teacher

settings = get_settings()

app = FastAPI(
    title="Studify",
    description=(
        "Generación de micro-aprendizaje adaptativo mediante IA generativa, "
        "con RAG estructurado sobre base de datos relacional y perfilamiento VARK."
    ),
    version="0.1.0",
)

app.include_router(diagnostics.router)
app.include_router(knowledge.router)
app.include_router(capsules.router)
# Los `*_docente` cuelgan del mismo prefijo `/api` pero exigen credenciales:
# curación del material y analítica de la cohorte. Ver `api/routers/knowledge.py`.
app.include_router(knowledge.router_docente)
app.include_router(capsules.router_docente)
app.include_router(student.router)
# Antes que `teacher.router`: `/teacher/login` tiene que resolverse por el
# router abierto y no quedar detrás del guardián del panel.
app.include_router(auth.router)
app.include_router(teacher.router)
# Términos y Privacidad: públicas, se leen antes de aceptar.
app.include_router(legal.router)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
STATIC_DIR = os.path.join(BASE_DIR, "web", "static")
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

PUBLIC_DIR = os.path.join(BASE_DIR, "public")
if os.path.exists(PUBLIC_DIR):
    app.mount("/public", StaticFiles(directory=PUBLIC_DIR), name="public")

@app.get("/", include_in_schema=False, response_class=HTMLResponse)
def index(request: Request):
    """Portada de RepasAi: qué es, cómo funciona y el botón para empezar.

    Solo lee si hay sesión para elegir el llamado a la acción: quien ya
    respondió el cuestionario sigue al catálogo; quien no, va a responderlo.
    """
    return templates.TemplateResponse(
        request=request,
        name="landing.html",
        context={"con_sesion": sesion.estudiante_actual(request) is not None},
    )

@app.get("/health", tags=["infra"])
def health() -> dict:
    """Verifica que la app responde y que la base de datos está alcanzable."""
    db_ok = False
    db_error = None
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        db_ok = True
    except Exception as exc:  # noqa: BLE001 - queremos reportar cualquier fallo de conexión
        db_error = str(exc)

    return {
        "status": "ok" if db_ok else "degraded",
        "app_env": settings.app_env,
        "database": {"reachable": db_ok, "error": db_error},
        "llm": {"model": settings.llm_model, "api_key_configured": bool(settings.llm_api_key)},
    }
