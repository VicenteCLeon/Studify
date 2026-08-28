"""Punto de entrada de la API.

Arranque:  uvicorn studify.main:app --reload --app-dir src
"""

import os

from fastapi import FastAPI, HTTPException, status
from fastapi.responses import FileResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import text

from studify.api.routers import capsules, diagnostics, knowledge, panel, ui
from studify.config import get_settings
from studify.db.session import engine
from studify.web.routers import auth, student, teacher

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
# Lo que la interfaz necesita y antes vivía dentro de los handlers Jinja:
# instrumento, sesión del estudiante, perfil legible y corrección del quiz.
app.include_router(ui.router)
# Los `*_docente` cuelgan del mismo prefijo `/api` pero exigen credenciales:
# curación del material y analítica de la cohorte. Ver `api/routers/knowledge.py`.
app.include_router(knowledge.router_docente)
app.include_router(capsules.router_docente)
app.include_router(panel.router)
app.include_router(auth.router_api)
app.include_router(student.router)
# Antes que `teacher.router`: `/teacher/login` tiene que resolverse por el
# router abierto y no quedar detrás del guardián del panel.
app.include_router(auth.router)
app.include_router(teacher.router)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
STATIC_DIR = os.path.join(BASE_DIR, "web", "static")
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

# La SPA de React, compilada por Vite a `web/spa/` (ver `frontend/vite.config.ts`).
# Se sirve desde el **mismo origen** que la API a propósito: así la sesión sigue
# viajando en la cookie `httpOnly` firmada que ya existe, en vez de tener que
# pasar a un token en `localStorage` —que cualquier XSS podría leer— y sin
# necesidad de abrir CORS.
SPA_DIR = os.path.join(BASE_DIR, "web", "spa")
SPA_INDEX = os.path.join(SPA_DIR, "index.html")
HAY_SPA = os.path.isfile(SPA_INDEX)

if HAY_SPA:
    app.mount(
        "/assets",
        StaticFiles(directory=os.path.join(SPA_DIR, "assets")),
        name="spa-assets",
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
        "spa": {"construida": HAY_SPA},
    }


# --- La SPA, al final de todo -------------------------------------------------
#
# Va **después** de todos los routers a propósito: FastAPI resuelve por orden de
# registro, así que `/api/*`, `/student/*`, `/teacher/*`, `/docs` y `/health`
# ganan sobre este comodín. Solo lo que ninguno reclamó llega acá.
#
# El comodín es necesario porque React Router maneja las rutas en el cliente: si
# alguien recarga la página estando en `/docente/analiticas`, el navegador le
# pide esa URL al servidor, que no tiene una vista para ella. Devolver el
# `index.html` deja que el router del cliente resuelva la ruta, que es el
# comportamiento estándar de una SPA con rutas "limpias" (sin `#`).


@app.get("/{ruta_spa:path}", include_in_schema=False)
def servir_spa(ruta_spa: str):
    """Entrega la SPA para cualquier ruta que no reclamó otro router."""
    # Un `/api/...` que llegó hasta acá es una ruta que no existe. Devolverle el
    # `index.html` le daría a un cliente de API un **200 con HTML dentro**, y el
    # cliente creería que la llamada funcionó — el mismo modo de fallo que se
    # evitó en `auth.requiere_docente_api` al no reusar el 303 de la web. Un 404
    # es lo que corresponde, y de paso hace visible un método equivocado (un GET
    # a un endpoint que solo acepta POST cae justo acá).
    if ruta_spa.startswith("api/"):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No existe el endpoint /{ruta_spa}.",
        )

    if not HAY_SPA:
        # La interfaz Jinja sigue montada y funcionando, así que un repositorio
        # recién clonado (sin `npm run build`) no queda sin UI: se le manda al
        # flujo de siempre en vez de darle un 404 sin explicación.
        return RedirectResponse(url="/student/vark")
    return FileResponse(SPA_INDEX)
