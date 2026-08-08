from fastapi import APIRouter, Request, Form
from fastapi.responses import HTMLResponse, Response
from typing import Optional

from studify.web.deps import templates

router = APIRouter(prefix="/student", tags=["web-student"])

@router.get("/vark", response_class=HTMLResponse)
async def get_vark(request: Request):
    """Muestra el cuestionario VARK."""
    return templates.TemplateResponse(request=request, name="student/vark.html")

@router.post("/vark")
async def process_vark(
    request: Request,
    q1: Optional[str] = Form(None),
    q2: Optional[str] = Form(None)
):
    """Procesa el cuestionario simulado y redirige al perfil."""
    # Aquí iría la lógica real. Por ahora, forzamos un redirect con HTMX
    response = Response(status_code=204)
    response.headers["HX-Redirect"] = "/student/profile"
    return response

@router.get("/profile", response_class=HTMLResponse)
async def get_profile(request: Request):
    """Muestra los resultados del perfil (mock)."""
    scores = {"V": 10, "A": 20, "R": 60, "K": 10}
    context = {
        "request": request,
        "main_style_name": "Lectura / Escritura",
        "scores": scores,
        "explanation": "Prefieres la información presentada en forma de palabras. Las listas, diarios, diccionarios y textos son tu mejor herramienta para aprender."
    }
    return templates.TemplateResponse(request=request, name="student/profile.html", context=context)

@router.get("/catalog", response_class=HTMLResponse)
async def get_catalog(request: Request):
    """Muestra el catálogo de temas (mock)."""
    subjects = [
        {
            "name": "Introducción a la Programación",
            "units": [
                {
                    "name": "Conceptos Básicos",
                    "learning_objectives": [
                        {"id": 1, "title": "Variables y Tipos de Datos"},
                        {"id": 2, "title": "Estructuras de Control"}
                    ]
                }
            ]
        }
    ]
    return templates.TemplateResponse(request=request, name="student/catalog.html", context={"subjects": subjects})

@router.get("/viewer/{capsule_id}", response_class=HTMLResponse)
async def get_viewer(request: Request, capsule_id: int):
    """Muestra una microcápsula específica (mock)."""
    capsule = {
        "id": capsule_id,
        "title": "Variables en Python",
        "learning_style": "Lectura / Escritura",
        "oa_id": 1,
        "content": "<p>Una variable en Python es un espacio en memoria para guardar datos. A diferencia de otros lenguajes, no necesitas declarar su tipo previamente.</p><ul><li>Usa nombres descriptivos.</li><li>Se asignan usando el signo <code>=</code>.</li></ul>",
        "activity": {
            "question": "¿Cuál es la sintaxis correcta para asignar el valor 10 a una variable llamada 'edad'?",
            "options": [
                {"text": "int edad = 10;"},
                {"text": "edad := 10"},
                {"text": "edad = 10"}
            ]
        }
    }
    return templates.TemplateResponse(request=request, name="student/viewer.html", context={"capsule": capsule})

@router.post("/viewer/{capsule_id}/submit", response_class=HTMLResponse)
async def submit_activity(request: Request, capsule_id: int, answer: str = Form(...)):
    """Procesa la respuesta del quiz y devuelve retroalimentación."""
    # Mock: Asumimos que la opción 2 (índice 2) es correcta.
    if answer == "2":
        html = """
        <div class="p-4 bg-green-100 text-green-800 border border-green-300 rounded-md" style="background-color: var(--success-bg); color: var(--success); padding: 1rem; border-radius: var(--radius-md);">
            <strong>¡Correcto!</strong> En Python la asignación es directa usando el operador = sin declarar el tipo.
        </div>
        """
    else:
        html = """
        <div class="p-4 bg-red-100 text-red-800 border border-red-300 rounded-md" style="background-color: var(--danger-bg); color: var(--danger); padding: 1rem; border-radius: var(--radius-md);">
            <strong>Incorrecto.</strong> Revisa el texto: Python no usa palabras reservadas como 'int' para variables simples ni el operador := para asignación básica.
        </div>
        """
    return HTMLResponse(content=html)
