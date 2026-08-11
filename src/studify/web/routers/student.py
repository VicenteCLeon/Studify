"""Vistas del estudiante (Fase 4).

Los endpoints son **síncronos** (`def`, no `async def`) por la misma decisión de
la Fase 0/1 que rige en `api/routers/`: FastAPI los corre en su threadpool, así
que el I/O bloqueante de SQLAlchemy no bloquea el event loop. Ver AVANCE.md §2.

Estas vistas no reimplementan nada: llaman a la misma lógica que expone la API
(`api.routers.diagnostics`, `vark.rules`, …) y se limitan a renderizarla. Si el
cálculo del perfil cambiara, la pantalla y `POST /api/diagnosticos` cambiarían
juntos, que es la única forma de que la demo y la API no se contradigan.
"""

from decimal import Decimal
from html import escape

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from pydantic import ValidationError
from sqlalchemy.orm import Session

from studify.api.routers.capsules import (
    crear_capsula,
    diagnostico_vigente,
    get_cliente_llm,
)
from studify.api.routers.diagnostics import crear_diagnostico
from studify.api.routers.knowledge import catalogo
from studify.api.schemas import (
    DiagnosticoIn,
    EstudianteIn,
    RespuestaItemIn,
)
from studify.api.schemas_capsulas import CapsulaIn
from studify.db.models import (
    Estudiante,
    MicrocapsulaGenerada,
    ObjetivoAprendizaje,
)
from studify.db.session import get_db
from studify.generation.generator import ClienteLLM
from studify.generation.schemas import BloqueContenido
from studify.vark import instrumento
from studify.vark.rules import aplicar_reglas
from studify.vark.scoring import PerfilVark
from studify.web import sesion, textos
from studify.web.deps import templates

router = APIRouter(prefix="/student", tags=["web-student"])

LETRAS = ("a", "b", "c", "d")


# --- Cuestionario VARK --------------------------------------------------------


@router.get("/vark", response_class=HTMLResponse)
def get_vark(request: Request):
    """Muestra los 16 ítems reales del instrumento (cap. 10).

    Las alternativas se leen de `vark/instrumento.py`, que es la definición del
    instrumento y la misma fuente que usa la calificación. Así la pantalla no
    puede desalinearse de la matriz de puntuación: si se corrigiera el texto de
    una alternativa, cambiaría en los dos lugares a la vez.

    **El formulario manda letras, no canales.** Cada alternativa viaja como
    `a|b|c|d` y es el servidor quien traduce esa posición a V/A/R/K
    (`instrumento.canal_por_posicion`). El cap. 17.1 justifica así la tabla
    `respuesta_vark`: la matriz no se filtra al frontend, de modo que los
    perfiles se pueden recalcular sin volver a aplicar el cuestionario.
    """
    items = [
        {
            "numero": numero,
            "enunciado": textos.ENUNCIADOS[numero - 1],
            "alternativas": list(zip(LETRAS, alternativas, strict=True)),
        }
        for numero, alternativas in enumerate(instrumento.ITEMS, start=1)
    ]
    return templates.TemplateResponse(
        request=request,
        name="student/vark.html",
        context={"items": items},
    )


@router.post("/vark")
def post_vark(
    request: Request,
    # Un parámetro por ítem porque el handler es síncrono: `await request.form()`
    # obligaría a declararlo `async def` y a meter la sesión de SQLAlchemy dentro
    # del event loop, que es justo lo que la decisión de stack evita.
    q1: list[str] = Form(default=[]),
    q2: list[str] = Form(default=[]),
    q3: list[str] = Form(default=[]),
    q4: list[str] = Form(default=[]),
    q5: list[str] = Form(default=[]),
    q6: list[str] = Form(default=[]),
    q7: list[str] = Form(default=[]),
    q8: list[str] = Form(default=[]),
    q9: list[str] = Form(default=[]),
    q10: list[str] = Form(default=[]),
    q11: list[str] = Form(default=[]),
    q12: list[str] = Form(default=[]),
    q13: list[str] = Form(default=[]),
    q14: list[str] = Form(default=[]),
    q15: list[str] = Form(default=[]),
    q16: list[str] = Form(default=[]),
    rango_etario: str = Form(default=""),
    genero: str = Form(default=""),
    carrera: str = Form(default=""),
    db: Session = Depends(get_db),
):
    """Califica el cuestionario de verdad y deja al estudiante conectado.

    Reutiliza `crear_diagnostico`, el handler de `POST /api/diagnosticos`: es la
    misma función, no una copia. Persiste en las cuatro entidades del módulo de
    perfilamiento (estudiante, diagnóstico, respuestas individuales y
    configuración de contenido) y devuelve la configuración ya aplicada.

    Los errores se devuelven como HTML con estado 200 y no como 4xx porque HTMX
    solo intercambia contenido en respuestas exitosas: un 422 dejaría al
    estudiante mirando un formulario que no reacciona.
    """
    marcadas = (q1, q2, q3, q4, q5, q6, q7, q8, q9, q10, q11, q12, q13, q14, q15, q16)

    try:
        respuestas = _respuestas_desde_formulario(marcadas)
    except ValueError as exc:
        return _error(str(exc))

    if not any(r.alternativas for r in respuestas):
        return _error(
            "No marcaste ninguna alternativa. Puedes dejar en blanco los ítems "
            "en los que no te reconozcas, pero hace falta al menos una selección "
            "para calcular tu perfil."
        )

    try:
        payload = _armar_payload(request, db, respuestas, rango_etario, genero, carrera)
    except ValidationError:
        # Los límites de `EstudianteIn` (largo de carrera, género, rango etario).
        # El formulario ya los acota con `maxlength`, pero eso es del navegador:
        # un POST armado a mano llegaría igual y sin este guardia daría un 500.
        return _error(
            "Alguno de los datos personales excede el largo permitido. "
            "Puedes dejarlos en blanco: son opcionales."
        )

    try:
        resultado = crear_diagnostico(payload, db)
    except HTTPException as exc:
        return _error(str(exc.detail))

    # 204 + HX-Redirect: HTMX procesa la cabecera y navega, así la URL del
    # navegador queda en /student/profile y el botón «atrás» funciona.
    respuesta = Response(status_code=204)
    respuesta.headers["HX-Redirect"] = "/student/profile"
    sesion.iniciar(respuesta, resultado.id_estudiante)
    return respuesta


def _respuestas_desde_formulario(marcadas: tuple[list[str], ...]) -> list[RespuestaItemIn]:
    """Las casillas de cada ítem → el contrato que espera la API.

    Un ítem puede venir vacío (el cap. 10 permite dejarlo en blanco) o con
    varias alternativas (la selección múltiple es parte del diseño del
    instrumento, no una anomalía).
    """
    respuestas: list[RespuestaItemIn] = []
    for numero, letras in enumerate(marcadas, start=1):
        limpias = [letra.strip().lower() for letra in letras if letra.strip()]
        for letra in limpias:
            if letra not in LETRAS:
                raise ValueError(
                    f"el ítem {numero} trae una alternativa desconocida: '{letra}'"
                )
        if len(set(limpias)) != len(limpias):
            raise ValueError(f"el ítem {numero} trae alternativas repetidas")
        respuestas.append(RespuestaItemIn(num_pregunta=numero, alternativas=limpias))
    return respuestas


def _armar_payload(
    request: Request,
    db: Session,
    respuestas: list[RespuestaItemIn],
    rango_etario: str,
    genero: str,
    carrera: str,
) -> DiagnosticoIn:
    """Decide si el diagnóstico es de un estudiante nuevo o de uno ya conectado.

    Repetir el cuestionario con la sesión abierta agrega un diagnóstico al mismo
    estudiante en vez de crear uno nuevo. Importa para el A/B de la Fase 5: si
    cada intento creara una persona distinta, la cohorte quedaría inflada con
    duplicados y las cápsulas de un mismo estudiante repartidas entre varios
    identificadores.
    """
    id_actual = sesion.estudiante_actual(request)
    if id_actual is not None and db.get(Estudiante, id_actual) is not None:
        return DiagnosticoIn(id_estudiante=id_actual, respuestas=respuestas)

    return DiagnosticoIn(
        estudiante=EstudianteIn(
            rango_etario=rango_etario.strip() or None,
            genero=genero.strip() or None,
            carrera=carrera.strip() or None,
        ),
        respuestas=respuestas,
    )


def _error(mensaje: str) -> HTMLResponse:
    """Aviso para el contenedor de errores del formulario.

    El mensaje se escapa porque algunos citan lo que el estudiante envió (la
    alternativa desconocida, por ejemplo). Sin escapar, un POST armado a mano con
    `q1=<script>…` devolvería ese script dentro del HTML y el navegador lo
    ejecutaría: es la vía clásica de XSS reflejado, y aquí además hay una cookie
    de sesión que robar.
    """
    return HTMLResponse(
        f'<div class="alerta alerta-error" role="alert">{escape(mensaje)}</div>'
    )


# --- Perfil -------------------------------------------------------------------


@router.get("/profile", response_class=HTMLResponse)
def get_profile(request: Request, db: Session = Depends(get_db)):
    """El vector VARK real del estudiante conectado y su configuración.

    Muestra las dos mitades del cap. 11: el **vector porcentual** que se guardó
    (tabla 17.2) y la **configuración de contenido** que las reglas derivaron de
    él (tabla 17.4). La segunda es la que de verdad condiciona la cápsula, así
    que se muestra explícita: es lo que permite comprobar en la demo que la
    adaptación existe antes siquiera de generar contenido.

    La jerarquía (canal primario, secundario, modalidad) se **recalcula** desde
    el vector en vez de leerse de una columna, porque el cap. 17.2 prohíbe
    persistir la etiqueta del perfil: derivarla siempre es lo que garantiza que
    no pueda quedar desincronizada.
    """
    id_estudiante = sesion.estudiante_actual(request)
    if id_estudiante is None:
        return _sin_sesion()

    if db.get(Estudiante, id_estudiante) is None:
        # Cookie de una base que ya no está (p. ej. tras un `--reset`).
        respuesta = _sin_sesion()
        sesion.cerrar(respuesta)
        return respuesta

    diagnostico = diagnostico_vigente(db, id_estudiante)
    if diagnostico is None:
        return _sin_sesion()

    perfil = PerfilVark(
        v=diagnostico.porcentaje_v,
        a=diagnostico.porcentaje_a,
        r=diagnostico.porcentaje_r,
        k=diagnostico.porcentaje_k,
    )
    config = aplicar_reglas(perfil)
    jerarquia = config.jerarquia

    # La fila persistida es la que la generación referencia por FK
    # (`microcapsula_generada.id_config`); las reglas son función pura del
    # vector, así que sus valores coinciden, pero se muestra la guardada para
    # que la pantalla no pueda diferir de lo que el motor va a usar.
    fila = diagnostico.configuracion

    explicacion = textos.EXPLICACION_CANAL[jerarquia.canal_primario]
    if jerarquia.es_multimodal:
        explicacion = f"{explicacion} {textos.EXPLICACION_MULTIMODAL}"

    contexto = {
        "canales": _barras(perfil),
        "canal_principal": textos.NOMBRE_CANAL[jerarquia.canal_primario],
        "jerarquia": jerarquia,
        "nombre_canal": textos.NOMBRE_CANAL,
        "modalidad": _modalidad(jerarquia),
        "explicacion": explicacion,
        "config": {
            "recursos_visuales": fila.recursos_visuales
            if fila
            else config.recursos_visuales,
            "palabras_texto": fila.palabras_texto if fila else config.palabras_texto,
            "componentes_practicos": fila.componentes_practicos
            if fila
            else config.componentes_practicos,
            "tono": textos.NOMBRE_TONO.get(config.tono_narrativo, config.tono_narrativo),
            "pesos": {
                "texto": config.pesos.texto,
                "visual": config.pesos.visual,
                "narrativo": config.pesos.narrativo,
                "practico": config.pesos.practico,
            },
        },
        "directivas": [textos.glosa_directiva(d) for d in config.directivas],
        "id_diagnostico": diagnostico.id_diagnostico,
    }
    return templates.TemplateResponse(
        request=request, name="student/profile.html", context=contexto
    )


def _sin_sesion() -> RedirectResponse:
    """Sin diagnóstico no hay nada que mostrar: se manda a responderlo."""
    return RedirectResponse(url="/student/vark", status_code=303)


def _barras(perfil: PerfilVark) -> list[dict]:
    """Los cuatro canales ordenados de mayor a menor, listos para pintar."""
    valores: dict[str, Decimal] = perfil.como_dict()
    ordenados = sorted(valores.items(), key=lambda kv: (-kv[1], "VARK".index(kv[0])))
    return [
        {
            "canal": canal,
            "nombre": textos.NOMBRE_CANAL[canal],
            "color": textos.COLOR_CANAL[canal],
            "ancho": f"{porcentaje:.2f}",
            "texto": f"{porcentaje:.1f}".replace(".", ","),
        }
        for canal, porcentaje in ordenados
    ]


def _modalidad(jerarquia) -> str:
    if jerarquia.es_multimodal:
        return "Multimodal"
    if jerarquia.es_bimodal:
        return "Bimodal"
    return "Unimodal"


# --- Catálogo -----------------------------------------------------------------


@router.get("/catalog", response_class=HTMLResponse)
def get_catalog(request: Request, db: Session = Depends(get_db)):
    """El árbol asignatura → unidad → tema, con material real detrás.

    Usa `catalogo`, el mismo handler de `GET /api/catalogo`, y con su valor por
    defecto `solo_con_material=True`: **un objetivo sin fragmentos validados no
    se muestra**. Es la regla de diseño de la Fase 2 y no un detalle de
    presentación — ofrecer un tema sin material curado llevaría al estudiante a
    un error de generación o, peor, a contenido inventado (cap. 12/13).
    """
    id_estudiante = sesion.estudiante_actual(request)
    if id_estudiante is None or db.get(Estudiante, id_estudiante) is None:
        return _sin_sesion()

    asignaturas = catalogo(solo_con_material=True, db=db)
    return templates.TemplateResponse(
        request=request,
        name="student/catalog.html",
        context={"asignaturas": asignaturas},
    )


# --- Visor de microcápsulas ---------------------------------------------------


@router.get("/viewer/{id_objetivo}", response_class=HTMLResponse)
def get_viewer(
    request: Request,
    id_objetivo: int,
    db: Session = Depends(get_db),
    cliente: ClienteLLM | None = Depends(get_cliente_llm),
):
    """Genera (o recupera del caché) la cápsula del objetivo para este estudiante.

    El parámetro de la ruta es el **objetivo de aprendizaje**, no una cápsula:
    el estudiante elige un tema del catálogo y el sistema decide si hay que
    generar o si ya existe una cápsula con la misma huella. Toda esa política
    —caché en dos niveles, versionado— vive en `crear_capsula`, que es el mismo
    handler de `POST /api/capsulas`; acá solo se renderiza lo que devuelve.
    """
    id_estudiante = sesion.estudiante_actual(request)
    if id_estudiante is None or db.get(Estudiante, id_estudiante) is None:
        return _sin_sesion()

    objetivo = db.get(ObjetivoAprendizaje, id_objetivo)
    if objetivo is None:
        return _capsula_no_disponible(
            request,
            objetivo=None,
            titulo="Ese tema no existe",
            mensaje=f"No hay ningún objetivo de aprendizaje con el id {id_objetivo}.",
        )

    try:
        capsula = crear_capsula(
            CapsulaIn(id_estudiante=id_estudiante, id_objetivo=id_objetivo),
            regenerar=False,
            db=db,
            cliente=cliente,
        )
    except HTTPException as exc:
        titulo, mensaje = _explicar_fallo(exc)
        return _capsula_no_disponible(
            request, objetivo=objetivo, titulo=titulo, mensaje=mensaje
        )

    return templates.TemplateResponse(
        request=request,
        name="student/viewer.html",
        context={
            "objetivo": objetivo,
            "capsula": capsula,
            "bloques": _preparar_bloques(capsula.contenido),
            # `indice_correcta` y `retroalimentacion` NO viajan al navegador: si
            # fueran al HTML, la respuesta correcta estaría en el código fuente
            # de la página y el quiz dejaría de medir nada.
            "actividad": {
                "tipo": capsula.actividad.tipo,
                "pregunta": capsula.actividad.pregunta,
                "alternativas": capsula.actividad.alternativas,
            },
        },
    )


@router.post("/viewer/{id_capsula}/submit", response_class=HTMLResponse)
def submit_activity(
    request: Request,
    id_capsula: int,
    answer: str = Form(default=""),
    db: Session = Depends(get_db),
):
    """Corrige la actividad de cierre contra el JSON guardado de la cápsula.

    Ojo con el parámetro: acá `{id_capsula}` es la **cápsula**, no el objetivo,
    porque la respuesta correcta vive en `mini_quiz_json` de la fila concreta
    que el estudiante tiene en pantalla. La corrección se hace en el servidor
    contra ese JSON y no contra nada que haya viajado al navegador.
    """
    id_estudiante = sesion.estudiante_actual(request)
    fila = db.get(MicrocapsulaGenerada, id_capsula)

    # Se comprueba el dueño para que la respuesta correcta de una cápsula no se
    # pueda sondear con peticiones a ids ajenos.
    if fila is None or id_estudiante is None or fila.id_estudiante != id_estudiante:
        return _error("Esta actividad no está disponible en tu sesión.")

    quiz = fila.mini_quiz_json or {}

    if quiz.get("tipo") == "intentalo_tu":
        # No hay respuesta única que corregir: se muestra la esperada para que
        # el estudiante contraste lo que escribió.
        return _feedback(
            request,
            estado="esperada",
            titulo="Respuesta esperada",
            retroalimentacion=quiz.get("retroalimentacion", ""),
        )

    indice_correcta = quiz.get("indice_correcta")
    alternativas = quiz.get("alternativas") or []
    if indice_correcta is None:
        return _error("Esta cápsula no tiene una actividad corregible.")

    if not answer.isdigit():
        return _error("Selecciona una alternativa antes de revisar.")

    acerto = int(answer) == indice_correcta
    correcta = (
        alternativas[indice_correcta] if 0 <= indice_correcta < len(alternativas) else ""
    )
    return _feedback(
        request,
        estado="ok" if acerto else "error",
        titulo="¡Correcto!" if acerto else "No es esa",
        retroalimentacion=quiz.get("retroalimentacion", ""),
        correcta=None if acerto else correcta,
    )


def _preparar_bloques(contenido: list[BloqueContenido]) -> list[dict]:
    """Normaliza cada bloque a una forma que la plantilla sabe dibujar.

    El contrato admite tres formas de `cuerpo` (texto, lista y matriz de filas)
    y siete tipos de bloque; decidir cuál es cuál en Jinja obligaría a meter
    lógica de tipos en la plantilla. Se resuelve acá y la plantilla queda con un
    `if` por forma.
    """
    preparados: list[dict] = []
    for bloque in contenido:
        cuerpo = bloque.cuerpo
        if isinstance(cuerpo, str):
            forma = "texto"
        elif cuerpo and all(isinstance(fila, list) for fila in cuerpo):
            forma = "filas"
        else:
            forma = "lista"
        preparados.append(
            {
                "tipo": bloque.tipo,
                "encabezado": bloque.encabezado,
                "forma": forma,
                "cuerpo": cuerpo,
                "ordenada": bloque.tipo == "lista_pasos",
            }
        )
    return preparados


def _explicar_fallo(exc: HTTPException) -> tuple[str, str]:
    """Traduce el error del endpoint a algo que el estudiante entienda.

    Los tres casos son distintos y conviene que se distingan en pantalla: falta
    la credencial (problema de configuración), falta material curado (problema
    del docente) o el modelo no logró producir una cápsula válida en los
    reintentos (problema de generación, y una métrica del criterio de término de
    la Fase 3).
    """
    if exc.status_code == 503:
        return (
            "Falta configurar el modelo de lenguaje",
            "El sistema no tiene credencial del LLM (`LLM_API_KEY` en el .env), "
            "así que no puede generar cápsulas nuevas. Las que ya estén "
            "generadas se siguen mostrando.",
        )
    if exc.status_code == 502:
        return (
            "El modelo no logró una cápsula válida",
            "La respuesta no pasó la validación en ninguno de los reintentos. "
            "Puedes volver a intentarlo; si se repite, hay que revisar el "
            "prompt o el material del tema.",
        )
    if exc.status_code == 422:
        return (
            "Este tema todavía no tiene material curado",
            "No hay fragmentos validados asociados a este objetivo, y el "
            "sistema no genera contenido sin material institucional que lo "
            "respalde.",
        )
    return ("No se pudo preparar la cápsula", str(exc.detail))


def _capsula_no_disponible(
    request: Request, *, objetivo, titulo: str, mensaje: str
) -> HTMLResponse:
    return templates.TemplateResponse(
        request=request,
        name="student/capsula_no_disponible.html",
        context={"objetivo": objetivo, "titulo": titulo, "mensaje": mensaje},
        status_code=200,
    )


def _feedback(
    request: Request,
    *,
    estado: str,
    titulo: str,
    retroalimentacion: str,
    correcta: str | None = None,
) -> HTMLResponse:
    """Fragmento de retroalimentación para HTMX.

    Va por plantilla y no por f-string porque el texto lo escribió el modelo:
    Jinja lo escapa solo, y una cápsula que contenga `<` o `&` no rompe la
    página ni inyecta nada.
    """
    return templates.TemplateResponse(
        request=request,
        name="student/_feedback.html",
        context={
            "estado": estado,
            "titulo": titulo,
            "retroalimentacion": retroalimentacion,
            "correcta": correcta,
        },
    )
