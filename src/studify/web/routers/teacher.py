from fastapi import APIRouter, Request, UploadFile, File
from fastapi.responses import HTMLResponse

from studify.web.deps import templates

router = APIRouter(prefix="/teacher", tags=["web-teacher"])

# Simulación de base de datos en memoria para los fragmentos
MOCK_FRAGMENTS = {
    1: {"id": 1, "source_file": "Clase_1_Intro.pdf", "page": 4, "text": "Python es un lenguaje interpretado y de tipado dinámico. No requiere compilación previa.", "status": "pending"},
    2: {"id": 2, "source_file": "Clase_1_Intro.pdf", "page": 5, "text": "Las listas en Python son colecciones ordenadas y mutables de elementos que pueden ser de distintos tipos.", "status": "pending"}
}

@router.get("/curation", response_class=HTMLResponse)
async def get_curation(request: Request):
    """Muestra el panel de curación (mock)."""
    fragments = [f for f in MOCK_FRAGMENTS.values() if f["status"] == "pending"]
    return templates.TemplateResponse(request=request, name="teacher/curation.html", context={"fragments": fragments})

@router.post("/curation/upload", response_class=HTMLResponse)
async def upload_document(request: Request, file: UploadFile = File(...)):
    """Simula la carga de un documento para el sistema RAG."""
    # En la realidad aquí se llamaría al servicio de ingestión.
    html = f"""
    <div style="background-color: var(--success-bg); color: var(--success); padding: 1rem; border-radius: var(--radius-md);">
        <strong>Éxito:</strong> Archivo '{file.filename}' subido e ingresado a la cola de procesamiento.
    </div>
    """
    return HTMLResponse(content=html)

@router.post("/curation/{fragment_id}/approve", response_class=HTMLResponse)
async def approve_fragment(request: Request, fragment_id: int):
    """Aprueba un fragmento (simulado)."""
    if fragment_id in MOCK_FRAGMENTS:
        MOCK_FRAGMENTS[fragment_id]["status"] = "approved"
    
    # Devolvemos la fila actualizada o simplemente un mensaje de "Aprobado"
    html = f"""
    <tr id="fragment-{fragment_id}">
        <td colspan="4" class="text-center" style="background-color: var(--success-bg); color: var(--success);">
            ✓ Fragmento {fragment_id} aprobado e indexado exitosamente.
        </td>
    </tr>
    """
    return HTMLResponse(content=html)

@router.post("/curation/{fragment_id}/reject", response_class=HTMLResponse)
async def reject_fragment(request: Request, fragment_id: int):
    """Rechaza un fragmento (simulado)."""
    if fragment_id in MOCK_FRAGMENTS:
        MOCK_FRAGMENTS[fragment_id]["status"] = "rejected"
    
    html = f"""
    <tr id="fragment-{fragment_id}">
        <td colspan="4" class="text-center" style="background-color: var(--danger-bg); color: var(--danger);">
            ✗ Fragmento {fragment_id} descartado.
        </td>
    </tr>
    """
    return HTMLResponse(content=html)
