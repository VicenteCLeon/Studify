"""Vistas del estudiante (Fase 4).

Los endpoints son **síncronos** (`def`, no `async def`) por la misma decisión de
la Fase 0/1 que rige en `api/routers/`: FastAPI los corre en su threadpool, así
que el I/O bloqueante de SQLAlchemy no bloquea el event loop. Ver AVANCE.md §2.

Estas vistas no reimplementan nada: llaman a la misma lógica que expone la API
(`api.routers.diagnostics`, `vark.rules`, …) y se limitan a renderizarla. Si el
cálculo del perfil cambiara, la pantalla y `POST /api/diagnosticos` cambiarían
juntos, que es la única forma de que la demo y la API no se contradigan.
"""

import logging
from decimal import Decimal
from html import escape

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session

from studify.api.routers.capsules import (
    crear_capsula,
    diagnostico_vigente,
    get_cliente_llm,
    registrar_quiz,
)
from studify.api.routers.diagnostics import crear_diagnostico
from studify.api.routers.knowledge import catalogo
from studify.api.schemas import (
    DiagnosticoIn,
    EstudianteIn,
    RespuestaItemIn,
)
from studify.api.schemas_capsulas import CapsulaIn, InteraccionQuizIn
from studify.db.models import (
    DiagnosticoVark,
    Estudiante,
    Fragmento,
    MicrocapsulaGenerada,
    ObjetivoAprendizaje,
)
from studify.db.session import get_db
from studify.generation.generator import ClienteLLM
from studify.generation.schemas import BloqueContenido
from studify.vark import instrumento
from studify.vark.rules import aplicar_reglas
from studify.vark.scoring import PerfilVark
from studify.web import consentimiento, sesion, textos
from studify.web.deps import templates

logger = logging.getLogger(__name__)

# Todas las vistas del estudiante exigen haber aceptado la versión vigente de
# los Términos y la Política, salvo el cuestionario, que es donde se aceptan
# (ver `web/consentimiento.py`).
router = APIRouter(
    prefix="/student",
    tags=["web-student"],
    dependencies=[Depends(consentimiento.exigir_vigente)],
)

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
    acepto: str = Form(default=""),
    consiento_genero: str = Form(default=""),
    db: Session = Depends(get_db),
):
    """Califica el cuestionario de verdad y deja al estudiante conectado.

    **Antes de calificar nada exige la aceptación** de los Términos y la
    Política (la casilla del primer paso, que nunca viene marcada). El botón
    del formulario ya queda deshabilitado sin ella, pero eso es del navegador:
    sin esta comprobación un POST armado a mano crearía un estudiante sin
    consentimiento registrado. Por la misma razón, el género —dato sensible—
    solo se acepta con su casilla de consentimiento propia.

    Reutiliza `crear_diagnostico`, el handler de `POST /api/diagnosticos`: es la
    misma función, no una copia. Persiste en las cuatro entidades del módulo de
    perfilamiento (estudiante, diagnóstico, respuestas individuales y
    configuración de contenido) y devuelve la configuración ya aplicada.

    Los errores se devuelven como HTML con estado 200 y no como 4xx porque HTMX
    solo intercambia contenido en respuestas exitosas: un 422 dejaría al
    estudiante mirando un formulario que no reacciona.
    """
    marcadas = (q1, q2, q3, q4, q5, q6, q7, q8, q9, q10, q11, q12, q13, q14, q15, q16)

    if acepto != "si":
        return _error(
            "Para calcular tu perfil tienes que aceptar los Términos y Condiciones "
            "y la Política de Privacidad (la casilla del primer paso)."
        )
    if genero.strip() and consiento_genero != "si":
        return _error(
            "Elegiste un género, pero no marcaste la casilla que autoriza su uso. "
            "Márcala o deja el género en «Prefiero no decirlo»: es opcional."
        )

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

    # El género solo se guardó si el estudiante es nuevo (`_armar_payload`
    # ignora los datos personales de quien ya tiene sesión), y solo entonces
    # hay un consentimiento de género que registrar.
    consentimiento.registrar(
        db,
        resultado.id_estudiante,
        genero=payload.estudiante is not None and payload.estudiante.genero is not None,
    )

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
                raise ValueError(f"el ítem {numero} trae una alternativa desconocida: '{letra}'")
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
    return HTMLResponse(f'<div class="alerta alerta-error" role="alert">{escape(mensaje)}</div>')


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

    estudiante = db.get(Estudiante, id_estudiante)
    if estudiante is None:
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
            "recursos_visuales": fila.recursos_visuales if fila else config.recursos_visuales,
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
        # La narración solo existe con audio activo (p_A ≥ 25 %): sin ella, el
        # selector de voz no tendría nada que cambiar.
        "audio_activo": config.audio_activo,
        "voz_actual": _voz_actual(estudiante),
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
            request,
            objetivo=objetivo,
            titulo=titulo,
            mensaje=mensaje,
            # Solo un fallo del modelo puede salir distinto al reintentar; sin
            # material o sin credencial, ofrecer "intentar de nuevo" engaña.
            reintentable=exc.status_code == 502,
        )

    diag = db.scalars(
        select(DiagnosticoVark)
        .where(DiagnosticoVark.id_estudiante == id_estudiante)
        .order_by(DiagnosticoVark.id_diagnostico.desc())
    ).first()
    audio_activo = False
    if diag:
        p = PerfilVark(
            v=diag.porcentaje_v, a=diag.porcentaje_a, r=diag.porcentaje_r, k=diag.porcentaje_k
        )
        config = aplicar_reglas(p)
        audio_activo = config.audio_activo

    return templates.TemplateResponse(
        request=request,
        name="student/viewer.html",
        context={
            "objetivo": objetivo,
            "capsula": capsula,
            "bloques": _preparar_bloques(capsula.bloques_legibles()),
            "referencias": _referencias(db, capsula.fuentes),
            "audio_activo": audio_activo,
            # El selector de voz es del estudiante dueño: solo existe en su visor.
            "mostrar_selector_voz": True,
            "voz_actual": _voz_actual(db.get(Estudiante, id_estudiante)),
            # `indice_correcta` y `retroalimentacion` NO viajan al navegador: si
            # fueran al HTML, la respuesta correcta estaría en el código fuente
            # de la página y el quiz dejaría de medir nada.
            "actividad": {
                "tipo": capsula.actividad.tipo,
                "pregunta": capsula.actividad.pregunta,
                "alternativas": capsula.actividad.alternativas,
                "tarjetas": [
                    {"anverso": t.anverso, "reverso": t.reverso}
                    for t in getattr(capsula.actividad, "tarjetas", [])
                ],
                "preguntas": [
                    {
                        "indice": i,
                        "enunciado": p.enunciado,
                        "alternativas": p.alternativas,
                    }
                    for i, p in enumerate(getattr(capsula.actividad, "preguntas", []))
                ],
            },
        },
    )


@router.post("/viewer/{id_capsula}/generate-audio", response_class=HTMLResponse)
def generate_capsule_audio(
    request: Request,
    id_capsula: int,
    texto_override: str = Form(default=""),
    db: Session = Depends(get_db),
):
    """Genera (o recupera) la narración de la cápsula en local (`media/audio.py`).

    **Quién puede pedirlo.** La síntesis ocupa la CPU por segundos (y por
    minutos con XTTS), así que no queda abierta:

    - una cápsula guardada (`id_capsula > 0`) la narra solo su dueño o el
      docente, y **siempre con el texto de la base**: `texto_override` se
      ignora, porque si no cualquiera con sesión podría hacerle decir a esa voz
      lo que quisiera;
    - la cápsula del simulador (`id_capsula == 0`) no está en la base, así que
      su texto viene en el formulario; por eso es solo del docente.

    **Con qué voz.** La que eligió el **dueño de la cápsula** (`estudiante.voz_*`),
    también cuando la pide el docente: así oye lo mismo que el estudiante. Sin
    preferencia guardada, y en el simulador, Dora. El nombre del archivo lleva la
    voz, para que cambiar de voz no siga sirviendo el audio de la anterior.
    """
    import hashlib
    from pathlib import Path

    from studify.media import audio

    es_docente = sesion.es_docente(request)
    texto = ""
    preferencia = audio.PreferenciaVoz()
    if id_capsula > 0:
        fila = db.get(MicrocapsulaGenerada, id_capsula)
        if fila is None or (
            not es_docente and fila.id_estudiante != sesion.estudiante_actual(request)
        ):
            raise HTTPException(status_code=404, detail=f"no existe la cápsula {id_capsula}")
        if fila.contenido_json:
            concepto = fila.contenido_json.get("concepto_central", "")
            activacion = fila.contenido_json.get("activacion", "")
            texto = f"{activacion} {concepto}".strip()
        dueno = db.get(Estudiante, fila.id_estudiante)
        if dueno is not None:
            preferencia = audio.preferencia_guardada(dueno.voz_genero, dueno.voz_modo)
    else:
        if not es_docente:
            raise HTTPException(status_code=403, detail="el audio del simulador es del docente")
        texto = texto_override.strip()
    clave = audio.clave_de_voz(audio.resolver_voz(preferencia))

    public_audio_dir = Path("src/studify/public/audio")
    public_audio_dir.mkdir(parents=True, exist_ok=True)

    if not texto:
        texto = "Esta es una microcápsula adaptativa sintetizada con IA para el canal auditivo."

    if id_capsula > 0:
        filename = f"capsula_{id_capsula}__{clave}.wav"
    else:
        h = hashlib.md5(texto.encode("utf-8")).hexdigest()[:8]
        filename = f"capsula_sim_{h}__{clave}.wav"

    audio_file = public_audio_dir / filename
    web_audio_url = f"/public/audio/{filename}"

    if not audio_file.exists():
        try:
            audio.generar_audio(texto, audio_file, preferencia=preferencia)
        except Exception as exc:
            logger.error("Error al generar audio (%s): %s", clave, exc)
            return templates.TemplateResponse(
                request=request,
                name="student/_audio.html",
                context={"error": str(exc)},
            )

    return templates.TemplateResponse(
        request=request,
        name="student/_audio.html",
        context={"url": web_audio_url},
    )


# Las cuatro opciones del selector de voz, como "<voz_genero>-<voz_modo>". Lo
# que se guarda es el género **de la voz** y el modo, nunca un nombre de voz: si
# cambia el motor, el estudiante conserva lo que eligió (ver media/audio.py).
OPCIONES_VOZ = tuple(valor for valor, *_ in textos.OPCIONES_VOZ)


def _voz_actual(estudiante: Estudiante) -> str:
    """La opción del selector que corresponde a la preferencia guardada (o Dora)."""
    from studify.media.audio import preferencia_guardada

    preferencia = preferencia_guardada(estudiante.voz_genero, estudiante.voz_modo)
    return f"{preferencia.genero}-{preferencia.modo}"


@router.post("/preferencias/voz", response_class=HTMLResponse)
def guardar_preferencia_voz(
    request: Request,
    voz: str = Form(...),
    contexto: str = Form(default="perfil"),
    id_capsula: int = Form(default=0),
    uid: str = Form(default=""),
    db: Session = Depends(get_db),
):
    """Guarda la voz con que el estudiante quiere oír sus narraciones.

    El estudiante sale **solo de la cookie firmada**: el formulario no trae
    `id_estudiante`, así que nadie puede cambiar la preferencia de otro.

    Con HTMX responde un fragmento: en el visor, el widget de audio, que vuelve
    a pedir la narración con la voz nueva; en el perfil, un aviso. Sin
    JavaScript, redirige de vuelta a la página donde estaba el selector.
    """
    id_estudiante = sesion.estudiante_actual(request)
    estudiante = db.get(Estudiante, id_estudiante) if id_estudiante is not None else None
    if estudiante is None:
        return _sin_sesion()
    if voz not in OPCIONES_VOZ:
        raise HTTPException(status_code=422, detail="opción de voz desconocida")

    estudiante.voz_genero, estudiante.voz_modo = voz.split("-")
    db.commit()

    fila = None
    if contexto == "visor" and id_capsula > 0:
        fila = db.get(MicrocapsulaGenerada, id_capsula)
        if fila is None or fila.id_estudiante != id_estudiante:
            raise HTTPException(status_code=404, detail=f"no existe la cápsula {id_capsula}")

    if request.headers.get("HX-Request") != "true":
        destino = f"/student/viewer/{fila.id_objetivo}" if fila else "/student/profile"
        return RedirectResponse(url=destino, status_code=303)

    if fila is not None:
        return templates.TemplateResponse(
            request=request,
            name="student/_audio_widget.html",
            context={"audio_id": fila.id_capsula, "uid": uid or fila.id_capsula},
        )
    return templates.TemplateResponse(
        request=request,
        name="student/_voz_guardada.html",
        context={"nombre_voz": textos.NOMBRE_VOZ[voz]},
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
        # el estudiante contraste lo que escribió. Se registra igual —sin
        # acierto ni alternativa— porque si no, los objetivos con actividad
        # aplicada (los perfiles K) no aparecerían nunca en el panel del
        # docente, como si nadie los hubiera trabajado.
        _registrar_intento(db, fila, alternativa=None, acerto=None)
        return _feedback(
            request,
            estado="esperada",
            titulo="Respuesta esperada",
            retroalimentacion=quiz.get("retroalimentacion", ""),
        )

    if quiz.get("tipo") == "flashcards":
        # Actividad kinestésica de memorización y práctica activa.
        _registrar_intento(db, fila, alternativa=None, acerto=True)
        return _feedback(
            request,
            estado="ok",
            titulo="¡Sesión de Flashcards completada!",
            retroalimentacion="Has ejercitado el recuerdo activo (Active Recall) de los conceptos fundamentales. ¡Excelente trabajo de práctica kinestésica!",
        )

    if quiz.get("tipo") in ("quiz_multi", "flashcards_y_quiz"):
        preguntas = quiz.get("preguntas") or []
        if not preguntas:
            return _error("Esta cápsula no tiene preguntas configuradas.")

        partes = [p.strip() for p in answer.split(",") if p.strip()]
        if len(partes) < len(preguntas):
            return _error(f"Por favor responde las {len(preguntas)} preguntas antes de revisar.")

        aciertos = 0
        detalles = []
        for i, preg in enumerate(preguntas):
            correcta_idx = preg.get("indice_correcta", 0)
            alts = preg.get("alternativas") or []
            seleccion = int(partes[i]) if (i < len(partes) and partes[i].isdigit()) else -1
            es_correcta = seleccion == correcta_idx
            if es_correcta:
                aciertos += 1
            corr_txt = alts[correcta_idx] if 0 <= correcta_idx < len(alts) else ""
            detalles.append(
                {
                    "enunciado": preg.get("enunciado", f"Pregunta {i + 1}"),
                    "es_correcta": es_correcta,
                    "correcta_texto": corr_txt,
                    "explicacion": preg.get("explicacion", ""),
                }
            )

        todos_bien = aciertos == len(preguntas)
        _registrar_intento(db, fila, alternativa=None, acerto=todos_bien)
        return _feedback(
            request,
            estado="ok" if todos_bien else "esperada",
            titulo=f"Cuestionario finalizado: {aciertos} de {len(preguntas)} respuestas correctas",
            retroalimentacion="Revisa las explicaciones de cada pregunta para consolidar los conceptos clave.",
            detalles=detalles,
        )

    indice_correcta = quiz.get("indice_correcta")
    alternativas = quiz.get("alternativas") or []
    if indice_correcta is None:
        return _error("Esta cápsula no tiene una actividad corregible.")

    if not answer.isdigit():
        return _error("Selecciona una alternativa antes de revisar.")

    acerto = int(answer) == indice_correcta
    _registrar_intento(db, fila, alternativa=int(answer), acerto=acerto)

    correcta = alternativas[indice_correcta] if 0 <= indice_correcta < len(alternativas) else ""
    return _feedback(
        request,
        estado="ok" if acerto else "error",
        titulo="¡Correcto!" if acerto else "No es esa",
        retroalimentacion=quiz.get("retroalimentacion", ""),
        correcta=None if acerto else correcta,
    )


def _registrar_intento(
    db: Session,
    fila: MicrocapsulaGenerada,
    *,
    alternativa: int | None,
    acerto: bool | None,
) -> None:
    """Deja el intento en la base para el panel del docente (Fase 5).

    Se llama al mismo handler de `POST /api/capsulas/{id}/quiz`, que es quien
    numera el intento y comprueba el dueño de la cápsula.

    El 404 y el 403 de ese handler no pueden darse acá: `submit_activity` ya
    verificó ambas cosas antes de corregir. Lo único que puede fallar es el 409
    de dos peticiones simultáneas —el doble clic—, y en ese caso el intento que
    llegó primero ya quedó registrado. Perder el duplicado no vale interrumpirle
    la retroalimentación al estudiante.
    """
    try:
        registrar_quiz(
            id_capsula=fila.id_capsula,
            payload=InteraccionQuizIn(
                id_estudiante=fila.id_estudiante,
                alternativa_seleccionada=alternativa,
                es_correcta=acerto,
            ),
            db=db,
        )
    except HTTPException:
        logger.warning("no se pudo registrar el intento de la cápsula %s", fila.id_capsula)


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


def _referencias(db: Session, fuentes) -> list[dict]:
    """Las fuentes de la cápsula, numeradas y con el texto del fragmento citado.

    La cita del contrato (`Fuente`) trae solo id, documento y página: mostrar
    además el fragmento es lo que permite al estudiante comprobar de dónde sale
    cada idea sin salir de la cápsula. Es una lectura por clave primaria de los
    mismos fragmentos que `validator.py` ya verificó; no cambia nada de la
    generación. Si un fragmento ya no estuviera (base reseteada), la referencia
    se muestra igual, sin extracto.
    """
    ids = [fuente.id_fragmento for fuente in fuentes]
    textos_por_id = {}
    if ids:
        textos_por_id = dict(
            db.execute(
                select(Fragmento.id_fragmento, Fragmento.contenido_texto).where(
                    Fragmento.id_fragmento.in_(ids)
                )
            ).all()
        )
    return [
        {
            "numero": numero,
            "id_fragmento": fuente.id_fragmento,
            "documento": fuente.documento,
            "pagina": fuente.pagina,
            "texto": textos_por_id.get(fuente.id_fragmento),
        }
        for numero, fuente in enumerate(fuentes, start=1)
    ]


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
    request: Request, *, objetivo, titulo: str, mensaje: str, reintentable: bool = False
) -> HTMLResponse:
    return templates.TemplateResponse(
        request=request,
        name="student/capsula_no_disponible.html",
        context={
            "objetivo": objetivo,
            "titulo": titulo,
            "mensaje": mensaje,
            "reintentable": reintentable,
        },
        status_code=200,
    )


def _feedback(
    request: Request,
    *,
    estado: str,
    titulo: str,
    retroalimentacion: str,
    correcta: str | None = None,
    detalles: list[dict] | None = None,
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
            "detalles": detalles,
        },
    )
