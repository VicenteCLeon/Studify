import os
from typing import Any

from fastapi import Request
from fastapi.templating import Jinja2Templates

from studify.web import sesion, textos

# Obtener ruta absoluta para evitar problemas al ejecutar desde distintos directorios
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
TEMPLATES_DIR = os.path.join(BASE_DIR, "templates")


def _contexto_global(request: Request) -> dict[str, Any]:
    """Lo que toda plantilla necesita sin que cada handler se acuerde de pasarlo.

    `es_docente` decide qué pestañas dibuja la cabecera compartida
    (`base.html`). Pasarlo vista por vista significaría que cualquier pantalla
    nueva que lo olvidara le mostraría la cabecera de estudiante a un docente
    conectado: un fallo silencioso, puramente visual, que nadie notaría hasta
    estar en una demo. Como procesador de contexto no hay nada que recordar.
    """
    return {"es_docente": sesion.es_docente(request)}


templates = Jinja2Templates(
    directory=TEMPLATES_DIR, context_processors=[_contexto_global]
)

# Constantes de presentación que los macros de `components/` necesitan aun
# cuando se importan sin contexto. El nombre de cada canal sale del mismo
# `textos` que usan los routers, así un chip VARK no puede decir algo distinto
# de la barra del perfil.
templates.env.globals["NOMBRE_CANAL"] = textos.NOMBRE_CANAL
