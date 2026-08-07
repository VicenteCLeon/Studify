"""Punto de entrada de la API.

Arranque:  uvicorn studify.main:app --reload --app-dir src
"""

from fastapi import FastAPI
from sqlalchemy import text

from studify.api.routers import diagnostics
from studify.config import get_settings
from studify.db.session import engine

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
