"""Flujo web del estudiante: cuestionario, sesión, perfil, catálogo y visor (Fase 4).

Estos tests comprueban lo que la API no puede comprobar sola: que la **pantalla**
esté servida por el motor real y no por datos de ejemplo. Por eso casi todos
verifican una correspondencia entre lo que hay en Postgres y lo que aparece en
el HTML, en vez de limitarse al código de estado.

Los que tocan la base se saltan solos si Postgres no está levantado, igual que
el resto de la suite (ver `conftest.py`).
"""

import json
import re

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from studify.api.routers.capsules import get_cliente_llm
from studify.db.models import (
    ConfiguracionContenido,
    DiagnosticoVark,
    DocumentoFuente,
    Estudiante,
    Fragmento,
    MicrocapsulaGenerada,
    ObjetivoAprendizaje,
    RespuestaVark,
)
from studify.main import app
from studify.vark import instrumento
from studify.web import sesion
from tests.conftest import necesita_bd


@pytest.fixture
def cliente() -> TestClient:
    return TestClient(app)


@pytest.fixture
def limpiar_estudiantes(db):
    """Borra los estudiantes que cree el test (CASCADE limpia lo demás).

    Sin esto cada corrida dejaría diagnósticos sueltos en la base, que es lo que
    obligó a recargar los 43 reales con `--reset` (ver AVANCE.md §3 ter).
    """
    creados: list[int] = []
    yield creados
    for id_estudiante in creados:
        fila = db.get(Estudiante, id_estudiante)
        if fila is not None:
            db.delete(fila)
    db.commit()


def _id_de_la_cookie(cliente: TestClient) -> int:
    crudo = cliente.cookies.get(sesion.COOKIE_ESTUDIANTE)
    assert crudo is not None, "el cuestionario no dejó sesión iniciada"
    return int(crudo.split(".")[0])


# --- El cuestionario que se muestra es el instrumento real --------------------


def test_vark_muestra_los_16_items_del_instrumento(cliente):
    """La pantalla se arma desde `instrumento.ITEMS`, no desde una copia.

    Si alguien corrigiera el texto de una alternativa en el instrumento, este
    test obliga a que la pantalla lo refleje: una copia paralela en la plantilla
    haría que el estudiante puntúe una alternativa distinta de la que lee.
    """
    html = cliente.get("/student/vark").text
    casillas = re.findall(r'name="q(\d+)" value="([a-d])"', html)

    assert len(casillas) == 64
    assert {int(n) for n, _ in casillas} == set(range(1, 17))
    for numero, alternativas in enumerate(instrumento.ITEMS, start=1):
        for texto in alternativas:
            assert texto in html, f"falta la alternativa del ítem {numero}: {texto!r}"


def test_vark_admite_seleccion_multiple_y_blanco(cliente):
    """Casillas, no botones de radio.

    El cap. 10 permite marcar más de una alternativa por ítem y dejar ítems sin
    responder; con `input type=radio` ninguna de las dos cosas sería expresable,
    y el instrumento aplicado por la web dejaría de ser el mismo que se aplicó
    por Google Forms a los 43 estudiantes ya cargados.
    """
    html = cliente.get("/student/vark").text
    assert 'type="checkbox"' in html
    assert 'name="q1" value="a"' in html
    assert "<input type=\"radio\"" not in html


# --- Sesión -------------------------------------------------------------------


def test_perfil_sin_sesion_redirige_al_cuestionario(cliente):
    respuesta = cliente.get("/student/profile", follow_redirects=False)
    assert respuesta.status_code == 303
    assert respuesta.headers["location"] == "/student/vark"


@pytest.mark.parametrize(
    "valor",
    ["1", "1." + "0" * 64, "abc.def", ""],
    ids=["sin_firma", "firma_falsa", "basura", "vacia"],
)
def test_cookie_manipulada_se_ignora(cliente, valor):
    """Una cookie sin firma válida vale lo mismo que no tener sesión.

    Es lo que impide que alguien vea el perfil y las cápsulas de otro estudiante
    escribiendo su id en las herramientas del navegador.
    """
    cliente.cookies.set(sesion.COOKIE_ESTUDIANTE, valor)
    respuesta = cliente.get("/student/profile", follow_redirects=False)
    assert respuesta.status_code == 303
    assert respuesta.headers["location"] == "/student/vark"


@necesita_bd
def test_la_cookie_no_es_legible_por_scripts(cliente, limpiar_estudiantes):
    respuesta = cliente.post("/student/vark", data={"q1": ["a"]})
    limpiar_estudiantes.append(_id_de_la_cookie(cliente))

    cabecera = respuesta.headers.get("set-cookie", "")
    assert "httponly" in cabecera.lower()
    assert "samesite=lax" in cabecera.lower()


# --- Calificación y persistencia ---------------------------------------------


@necesita_bd
def test_el_cuestionario_persiste_el_diagnostico_completo(
    cliente, db, limpiar_estudiantes
):
    """Las cuatro entidades del módulo de perfilamiento, desde el formulario.

    Un ítem en blanco (el 16) y tres con selección múltiple, para que el caso
    probado sea el del instrumento real y no uno simplificado.
    """
    datos = {f"q{n}": ["d"] for n in range(1, 16)}
    datos["q1"] = ["d", "b"]
    datos["q2"] = ["d", "b"]
    datos["q3"] = ["d", "c"]
    datos["carrera"] = "Ingeniería Civil Informática"

    respuesta = cliente.post("/student/vark", data=datos)

    assert respuesta.status_code == 204
    assert respuesta.headers["HX-Redirect"] == "/student/profile"

    id_estudiante = _id_de_la_cookie(cliente)
    limpiar_estudiantes.append(id_estudiante)

    estudiante = db.get(Estudiante, id_estudiante)
    assert estudiante.carrera == "Ingeniería Civil Informática"

    diagnostico = db.scalars(
        select(DiagnosticoVark).where(DiagnosticoVark.id_estudiante == id_estudiante)
    ).one()
    # 15 ítems con la alternativa kinestésica + 3 marcas extra (A, A, R).
    assert (diagnostico.puntaje_v, diagnostico.puntaje_a) == (0, 2)
    assert (diagnostico.puntaje_r, diagnostico.puntaje_k) == (1, 15)

    respuestas = db.scalars(
        select(RespuestaVark).where(
            RespuestaVark.id_diagnostico == diagnostico.id_diagnostico
        )
    ).all()
    assert len(respuestas) == 18, "cada alternativa marcada es una fila (tabla 17.3)"
    assert 16 not in {r.num_pregunta for r in respuestas}, "el ítem 16 iba en blanco"

    config = db.scalar(
        select(ConfiguracionContenido).where(
            ConfiguracionContenido.id_diagnostico == diagnostico.id_diagnostico
        )
    )
    assert config is not None
    assert config.tono_narrativo == "practico"
    assert config.componentes_practicos == 3


@necesita_bd
def test_el_perfil_muestra_el_vector_y_la_configuracion_guardados(
    cliente, db, limpiar_estudiantes
):
    """La pantalla tiene que decir lo mismo que la base, no un valor de ejemplo."""
    cliente.post("/student/vark", data={f"q{n}": ["c"] for n in range(1, 17)})
    id_estudiante = _id_de_la_cookie(cliente)
    limpiar_estudiantes.append(id_estudiante)

    diagnostico = db.scalars(
        select(DiagnosticoVark).where(DiagnosticoVark.id_estudiante == id_estudiante)
    ).one()
    config = diagnostico.configuracion

    html = cliente.get("/student/profile").text

    # Perfil puramente lector/escritor: 100% en R y el máximo de extensión.
    assert "Lectura / Escritura" in html
    assert "100,0%" in html
    assert str(config.palabras_texto) in html
    assert f"Diagnóstico #{diagnostico.id_diagnostico}" in html
    # Las directivas que el prompt maestro va a recibir, en lenguaje legible.
    assert "Glosario de términos clave" in html


@necesita_bd
def test_responder_de_nuevo_agrega_un_diagnostico_al_mismo_estudiante(
    cliente, db, limpiar_estudiantes
):
    """Repetir el cuestionario no crea una persona nueva.

    Si lo hiciera, la cohorte del A/B de la Fase 5 quedaría inflada con
    duplicados y las cápsulas de un mismo estudiante repartidas entre varios
    identificadores.
    """
    cliente.post("/student/vark", data={f"q{n}": ["a"] for n in range(1, 17)})
    id_estudiante = _id_de_la_cookie(cliente)
    limpiar_estudiantes.append(id_estudiante)

    cliente.post("/student/vark", data={f"q{n}": ["c"] for n in range(1, 17)})

    assert _id_de_la_cookie(cliente) == id_estudiante
    diagnosticos = db.scalars(
        select(DiagnosticoVark).where(DiagnosticoVark.id_estudiante == id_estudiante)
    ).all()
    assert len(diagnosticos) == 2

    # El perfil que se muestra es el más reciente, igual que el que usaría
    # `POST /api/capsulas` para generar.
    assert "Lectura / Escritura" in cliente.get("/student/profile").text


# --- Entradas inválidas: avisos, nunca un 500 --------------------------------


@pytest.mark.parametrize(
    ("datos", "fragmento_del_mensaje"),
    [
        ({}, "No marcaste ninguna alternativa"),
        ({"q1": ["z"]}, "alternativa desconocida"),
        ({"q1": ["a"], "carrera": "x" * 200}, "excede el largo permitido"),
    ],
    ids=["todo_en_blanco", "alternativa_inexistente", "carrera_muy_larga"],
)
def test_entradas_invalidas_devuelven_aviso_html(cliente, datos, fragmento_del_mensaje):
    """HTMX solo intercambia contenido en respuestas exitosas.

    Un 422 dejaría al estudiante mirando un formulario que no reacciona, así que
    el error viaja como HTML con estado 200.
    """
    respuesta = cliente.post("/student/vark", data=datos)
    assert respuesta.status_code == 200
    assert "alerta-error" in respuesta.text
    assert fragmento_del_mensaje in respuesta.text


def test_el_aviso_de_error_no_devuelve_lo_enviado_sin_escapar(cliente):
    """XSS reflejado: el mensaje cita la alternativa recibida.

    Sin escapar, un POST con `q1=<script>…` haría que el navegador ejecutara ese
    script dentro de la página — y hay una cookie de sesión que robar.
    """
    respuesta = cliente.post(
        "/student/vark", data={"q1": ["<script>alert(1)</script>"]}
    )
    assert respuesta.status_code == 200
    assert "<script>" not in respuesta.text
    assert "&lt;script&gt;" in respuesta.text


# --- Catálogo y visor ---------------------------------------------------------
#
# El LLM se sustituye por un cliente falso con `dependency_overrides`, igual que
# en `test_api_capsulas.py`: estas pruebas miden el renderizado y la corrección
# del quiz, no la calidad del modelo, así que no necesitan credencial ni red.

ASIGNATURA_PRUEBA = "Bases de Datos (test web)"
CARRERA_PRUEBA = "Carrera de prueba (test web)"

TEXTO_FUENTE = (
    "La normalización organiza los atributos de una base de datos relacional "
    "para reducir la redundancia y evitar anomalías al insertar, actualizar o "
    "eliminar filas. Una dependencia parcial aparece cuando un atributo no "
    "clave depende solo de una parte de la clave primaria compuesta. Mientras "
    "exista esa dependencia, la tabla no está en segunda forma normal y el "
    "mismo valor se repetirá en muchas filas distintas del sistema. Al separar "
    "ese atributo en su propia tabla, cualquier corrección se hace una sola vez "
    "y queda reflejada en todas las consultas que la utilizan después."
)

# Cápsula que ejercita las cuatro formas de renderizado del visor (párrafo,
# lista, tabla y glosario) repartidas en los pasos de la estructura pedagógica.
ACTIVACION_DE_PRUEBA = "¿Te ha tocado corregir el mismo dato en muchas filas a la vez?"

CONCEPTO_DE_PRUEBA = (
    "Una dependencia parcial ocurre cuando un atributo que no pertenece "
    "a la clave primaria depende solamente de una parte de esa clave "
    "compuesta, y no de la clave completa. Mientras esa dependencia "
    "exista, la tabla incumple la segunda forma normal y el mismo dato "
    "queda repetido en muchas filas, de modo que cualquier corrección "
    "hay que aplicarla en todas ellas. El remedio consiste en trasladar "
    "el atributo a una tabla propia junto con la porción de clave de la "
    "que realmente depende, dejando una clave foránea en la tabla "
    "original para no perder información."
)

BLOQUES_DE_PRUEBA = [
    {
        "tipo": "tabla",
        "encabezado": "Antes y después",
        "cuerpo": [
            ["Situación", "Consecuencia"],
            ["Con dependencia parcial", "El dato se repite en cada fila"],
            ["Sin dependencia parcial", "El dato se corrige una sola vez"],
        ],
    },
    {
        "tipo": "glosario",
        "encabezado": "Términos",
        "cuerpo": [
            ["Clave compuesta", "clave primaria formada por dos o más atributos"],
            ["Clave foránea", "atributo que referencia la clave de otra tabla"],
        ],
    },
]

EJEMPLO_DE_PRUEBA = {
    "tipo": "lista_pasos",
    "encabezado": "Cómo corregirla",
    "cuerpo": [
        "Identifica la clave primaria completa de la tabla original.",
        "Revisa cada atributo no clave y pregúntate de qué parte depende.",
        "Traslada los atributos dependientes a una tabla nueva.",
        "Deja una clave foránea que apunte a esa tabla nueva.",
    ],
}

PREGUNTA = "¿Cuándo una tabla incumple la segunda forma normal?"
ALTERNATIVAS = [
    "Cuando un atributo no clave depende de parte de la clave",
    "Cuando la tabla tiene más de cinco columnas",
    "Cuando la clave primaria es un número entero",
]
INDICE_CORRECTA = 0
RETROALIMENTACION = "El atributo debe depender de la clave primaria completa."


class ClienteFalso:
    """Modelo simulado: responde en español y cita los fragmentos recibidos.

    Los ids se leen del prompt en vez de fijarse a mano porque los asigna la
    base en cada corrida, y un id inventado haría que el validador rechazara la
    cápsula por la regla 5 (citas alucinadas) — un fallo que no tiene nada que
    ver con lo que estos tests miden.
    """

    modelo = "modelo-de-prueba-web"

    def responder(self, mensajes) -> str:
        ids = [int(n) for n in re.findall(r"id_fragmento: (\d+)", mensajes[1].contenido)]
        return json.dumps(
            {
                "titulo": "Dependencias parciales y segunda forma normal",
                "objetivo_aprendizaje": "Reconocer y corregir dependencias parciales.",
                "activacion": ACTIVACION_DE_PRUEBA,
                "concepto_central": CONCEPTO_DE_PRUEBA,
                "representacion_adaptativa": BLOQUES_DE_PRUEBA,
                "ejemplo": EJEMPLO_DE_PRUEBA,
                "actividad": {
                    "tipo": "quiz_mc",
                    "pregunta": PREGUNTA,
                    "alternativas": ALTERNATIVAS,
                    "indice_correcta": INDICE_CORRECTA,
                    "retroalimentacion": RETROALIMENTACION,
                },
                "fuentes": [{"id_fragmento": ids[0], "documento": "x", "pagina": 1}],
            },
            ensure_ascii=False,
        )


@pytest.fixture
def llm_falso():
    app.dependency_overrides[get_cliente_llm] = ClienteFalso
    yield
    app.dependency_overrides.pop(get_cliente_llm, None)


@pytest.fixture
def sin_credencial():
    """El estado real de la máquina de trabajo: `LLM_API_KEY` vacío."""
    app.dependency_overrides[get_cliente_llm] = lambda: None
    yield
    app.dependency_overrides.pop(get_cliente_llm, None)


@pytest.fixture
def material(db):
    """Un objetivo con material validado y otro sin nada curado.

    El segundo es el que importa: sirve para comprobar que el catálogo lo
    esconde y que el visor no intenta generar sobre la nada.
    """
    con_material = ObjetivoAprendizaje(
        codigo_objetivo="TEST-WEB-01",
        asignatura=ASIGNATURA_PRUEBA,
        unidad="Unidad 3",
        tema="Segunda forma normal",
        descripcion="Reconocer dependencias parciales.",
        estado="activo",
    )
    sin_material = ObjetivoAprendizaje(
        codigo_objetivo="TEST-WEB-02",
        asignatura=ASIGNATURA_PRUEBA,
        unidad="Unidad 3",
        tema="Tercera forma normal",
        estado="activo",
    )
    db.add_all([con_material, sin_material])
    db.flush()

    documento = DocumentoFuente(
        titulo="Apunte de prueba (web)",
        formato="pdf",
        hash_archivo="hash-de-prueba-web-estudiante",
        estado_curacion="validado",
    )
    db.add(documento)
    db.flush()

    db.add(
        Fragmento(
            id_documento=documento.id_documento,
            id_objetivo=con_material.id_objetivo,
            numero_fragmento=1,
            tipo_fragmento="texto",
            contenido_texto=TEXTO_FUENTE,
            pagina_inicio=12,
            pagina_fin=12,
            estado_validacion="validado",
        )
    )
    db.commit()

    yield {"con_material": con_material, "sin_material": sin_material}

    # Las cápsulas tienen FK RESTRICT contra el objetivo: primero ellas.
    db.query(MicrocapsulaGenerada).filter(
        MicrocapsulaGenerada.id_objetivo.in_(
            [con_material.id_objetivo, sin_material.id_objetivo]
        )
    ).delete(synchronize_session=False)
    db.commit()
    db.delete(documento)
    db.delete(con_material)
    db.delete(sin_material)
    db.commit()


@pytest.fixture
def estudiante_conectado(cliente, limpiar_estudiantes):
    """Un estudiante con perfil kinestésico, creado por el propio cuestionario."""
    cliente.post(
        "/student/vark",
        data={f"q{n}": ["d"] for n in range(1, 17)} | {"carrera": CARRERA_PRUEBA},
    )
    id_estudiante = _id_de_la_cookie(cliente)
    limpiar_estudiantes.append(id_estudiante)
    return id_estudiante


@necesita_bd
def test_el_catalogo_oculta_los_temas_sin_material_validado(
    cliente, estudiante_conectado, material
):
    """La regla de la Fase 2, ahora visible en pantalla.

    Un tema sin fragmentos validados no puede producir una cápsula fundamentada;
    ofrecerlo llevaría al estudiante a un error o a contenido inventado.
    """
    html = cliente.get("/student/catalog").text

    assert "Segunda forma normal" in html
    assert "TEST-WEB-01" in html
    assert "Tercera forma normal" not in html
    assert f"/student/viewer/{material['con_material'].id_objetivo}" in html


@necesita_bd
def test_el_catalogo_sin_sesion_manda_al_cuestionario(cliente):
    respuesta = cliente.get("/student/catalog", follow_redirects=False)
    assert respuesta.status_code == 303
    assert respuesta.headers["location"] == "/student/vark"


@necesita_bd
def test_el_visor_renderiza_los_bloques_del_contrato(
    cliente, db, estudiante_conectado, material, llm_falso
):
    """Cada `tipo` de bloque se dibuja con la estructura que le corresponde.

    Es el trabajo que faltaba según AVANCE §6.2: el visor tenía un HTML fijo y
    tenía que pasar a recorrer `contenido` según el tipo de cada bloque.
    """
    html = cliente.get(f"/student/viewer/{material['con_material'].id_objetivo}").text

    assert "Dependencias parciales y segunda forma normal" in html
    # Párrafo, lista ordenada, tabla y glosario, cada uno en su etiqueta.
    assert '<ol class="lista-bloque">' in html
    assert '<table class="table">' in html
    assert '<dl class="glosario">' in html
    assert "Identifica la clave primaria completa de la tabla original." in html
    assert "El dato se repite en cada fila" in html
    assert "clave primaria formada por dos o más atributos" in html

    # La trazabilidad del cap. 13, a la vista del estudiante.
    fragmento = db.scalars(
        select(Fragmento).where(
            Fragmento.id_objetivo == material["con_material"].id_objetivo
        )
    ).one()
    assert f"#{fragmento.id_fragmento}" in html
    assert "Apunte de prueba (web)" in html


@necesita_bd
def test_el_visor_no_filtra_la_respuesta_correcta(
    cliente, estudiante_conectado, material, llm_falso
):
    """Ni `indice_correcta` ni la retroalimentación pueden viajar al navegador.

    Si estuvieran en el HTML, la respuesta estaría en el código fuente de la
    página y el quiz dejaría de medir nada.
    """
    html = cliente.get(f"/student/viewer/{material['con_material'].id_objetivo}").text

    assert PREGUNTA in html
    for alternativa in ALTERNATIVAS:
        assert alternativa in html
    assert "indice_correcta" not in html
    assert RETROALIMENTACION not in html


@necesita_bd
def test_el_quiz_se_corrige_contra_el_json_guardado(
    cliente, db, estudiante_conectado, material, llm_falso
):
    id_objetivo = material["con_material"].id_objetivo
    cliente.get(f"/student/viewer/{id_objetivo}")

    fila = db.scalars(
        select(MicrocapsulaGenerada).where(
            MicrocapsulaGenerada.id_objetivo == id_objetivo
        )
    ).one()
    assert fila.mini_quiz_json["indice_correcta"] == INDICE_CORRECTA

    acierto = cliente.post(
        f"/student/viewer/{fila.id_capsula}/submit", data={"answer": "0"}
    )
    assert acierto.status_code == 200
    assert "¡Correcto!" in acierto.text
    assert RETROALIMENTACION in acierto.text

    fallo = cliente.post(
        f"/student/viewer/{fila.id_capsula}/submit", data={"answer": "2"}
    )
    assert "No es esa" in fallo.text
    # Al fallar sí se revela la correcta: es la retroalimentación formativa.
    assert ALTERNATIVAS[INDICE_CORRECTA] in fallo.text


@necesita_bd
def test_no_se_puede_sondear_la_respuesta_de_una_capsula_ajena(
    cliente, db, estudiante_conectado, material, llm_falso
):
    """Sin la comprobación de dueño, bastaría iterar ids para sacar las respuestas."""
    id_objetivo = material["con_material"].id_objetivo
    cliente.get(f"/student/viewer/{id_objetivo}")
    fila = db.scalars(
        select(MicrocapsulaGenerada).where(
            MicrocapsulaGenerada.id_objetivo == id_objetivo
        )
    ).one()

    intruso = TestClient(app)
    respuesta = intruso.post(
        f"/student/viewer/{fila.id_capsula}/submit", data={"answer": "0"}
    )
    assert respuesta.status_code == 200
    assert "no está disponible en tu sesión" in respuesta.text
    assert RETROALIMENTACION not in respuesta.text
    assert ALTERNATIVAS[INDICE_CORRECTA] not in respuesta.text


@necesita_bd
def test_un_tema_sin_material_no_intenta_generar(
    cliente, estudiante_conectado, material, llm_falso
):
    html = cliente.get(f"/student/viewer/{material['sin_material'].id_objetivo}").text
    assert "todavía no tiene material curado" in html


@necesita_bd
def test_sin_credencial_del_llm_se_explica_en_pantalla(
    cliente, estudiante_conectado, material, sin_credencial
):
    """Es el estado real mientras `LLM_API_KEY` siga vacío (AVANCE §6.0).

    La pantalla tiene que distinguirlo de «no hay material»: uno lo arregla el
    equipo con una credencial y el otro el docente curando.
    """
    html = cliente.get(f"/student/viewer/{material['con_material'].id_objetivo}").text
    assert "Falta configurar el modelo de lenguaje" in html


@necesita_bd
def test_la_segunda_visita_al_mismo_tema_sale_del_cache(
    cliente, db, estudiante_conectado, material, llm_falso
):
    """Abrir la cápsula dos veces no vuelve a pagarle al modelo."""
    id_objetivo = material["con_material"].id_objetivo

    primera = cliente.get(f"/student/viewer/{id_objetivo}").text
    assert "Generada para ti" in primera

    segunda = cliente.get(f"/student/viewer/{id_objetivo}").text
    assert "Recuperada de caché" in segunda

    capsulas = db.scalars(
        select(MicrocapsulaGenerada).where(
            MicrocapsulaGenerada.id_objetivo == id_objetivo
        )
    ).all()
    assert len(capsulas) == 1, "el caché no debía crear una fila nueva"
