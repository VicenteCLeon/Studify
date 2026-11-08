"""Datos para el análisis del estudio A/B (punto 2d).

El piloto compara dos grupos: experimental (rol `estudiante`, cápsula adaptada
a su perfil VARK) y control (rol `control`, cápsula básica sin adaptación).
Lo que protegen estos tests:

- que las métricas del panel no mezclen a los dos grupos en una sola cifra;
- que el historial de `/api/capsulas` diga de qué grupo es cada cápsula;
- que la exportación de intentos sirva para el análisis sin sacar del sistema
  datos que identifiquen a nadie, y que no se pueda bajar sin sesión docente.

Requieren Postgres (se saltan solos si no está).
"""

import csv
import io
from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient

from studify.db.models import (
    Estudiante,
    InteraccionQuiz,
    MicrocapsulaGenerada,
    ObjetivoAprendizaje,
)
from studify.main import app
from studify.web.routers.teacher import _rendimiento_actividades
from tests.conftest import necesita_bd
from tests.test_interaccion_quiz import CONTENIDO, CUESTIONARIO, QUIZ_CORREGIBLE

pytestmark = necesita_bd

CARRERA_PRUEBA = "Ingeniería Informática (test análisis)"
# Empieza con «=»: si la exportación no lo escapa, Excel lo ejecuta como fórmula.
TEMA = "=HIPERVINCULO(\"http://x\") Dependencias funcionales"
CODIGO = "TEST-ANALISIS-01"

COLUMNAS = [
    "id_estudiante",
    "rol",
    "codigo_objetivo",
    "tema",
    "id_capsula",
    "tipo_actividad",
    "numero_intento",
    "es_primer_intento",
    "es_correcta",
    "aciertos",
    "total_preguntas",
    "fecha",
]


def _fecha(dia: int, mes: int = 3) -> datetime:
    # Al mediodía UTC, lejos del cambio de día en cualquier zona horaria, y en
    # 2001 para que el filtro por fecha aísle estas filas de las del autor.
    return datetime(2001, mes, dia, 12, 0, tzinfo=UTC)


@pytest.fixture
def escenario(db):
    """Un objetivo y un estudiante de cada grupo.

    - Experimental: `quiz_mc` acertado al primer intento (5-mar) y un
      cuestionario 3 de 4 (10-mar).
    - Control: `quiz_mc` fallado (20-mar) y reintentado con acierto (2-abr).
    """
    objetivo = ObjetivoAprendizaje(
        codigo_objetivo=CODIGO,
        asignatura="Bases de Datos (test análisis)",
        unidad="Unidad 3",
        tema=TEMA,
        descripcion="Reconocer dependencias funcionales.",
        estado="activo",
    )
    experimental = Estudiante(
        carrera=CARRERA_PRUEBA,
        rol="estudiante",
        google_sub="sub-secreto-experimental",
        google_email="experimental.secreto@mail.pucv.cl",
        google_nombre="Nombre Secreto Experimental",
    )
    control = Estudiante(
        carrera=CARRERA_PRUEBA,
        rol="control",
        google_sub="sub-secreto-control",
        google_email="control.secreto@mail.pucv.cl",
        google_nombre="Nombre Secreto Control",
    )
    db.add_all([objetivo, experimental, control])
    db.flush()

    def capsula(estudiante, quiz):
        return MicrocapsulaGenerada(
            id_estudiante=estudiante.id_estudiante,
            id_objetivo=objetivo.id_objetivo,
            titulo="Dependencias funcionales",
            contenido_json={"contenido": CONTENIDO},
            mini_quiz_json=quiz,
            estado_validacion="validada",
        )

    exp_mc = capsula(experimental, QUIZ_CORREGIBLE)
    exp_cuestionario = capsula(experimental, CUESTIONARIO)
    ctl_mc = capsula(control, QUIZ_CORREGIBLE)
    db.add_all([exp_mc, exp_cuestionario, ctl_mc])
    db.flush()

    db.add_all(
        [
            InteraccionQuiz(
                id_capsula=exp_mc.id_capsula,
                numero_intento=1,
                alternativa_seleccionada=0,
                es_correcta=True,
                fecha_respuesta=_fecha(5),
            ),
            InteraccionQuiz(
                id_capsula=exp_cuestionario.id_capsula,
                numero_intento=1,
                es_correcta=False,
                aciertos=3,
                total_preguntas=4,
                fecha_respuesta=_fecha(10),
            ),
            InteraccionQuiz(
                id_capsula=ctl_mc.id_capsula,
                numero_intento=1,
                alternativa_seleccionada=1,
                es_correcta=False,
                fecha_respuesta=_fecha(20),
            ),
            InteraccionQuiz(
                id_capsula=ctl_mc.id_capsula,
                numero_intento=2,
                alternativa_seleccionada=0,
                es_correcta=True,
                fecha_respuesta=_fecha(2, mes=4),
            ),
        ]
    )
    db.commit()

    yield {
        "objetivo": objetivo,
        "experimental": experimental,
        "control": control,
        "exp_mc": exp_mc,
        "exp_cuestionario": exp_cuestionario,
        "ctl_mc": ctl_mc,
    }

    ids = [c.id_capsula for c in (exp_mc, exp_cuestionario, ctl_mc)]
    db.query(InteraccionQuiz).filter(InteraccionQuiz.id_capsula.in_(ids)).delete(
        synchronize_session=False
    )
    db.query(MicrocapsulaGenerada).filter(
        MicrocapsulaGenerada.id_capsula.in_(ids)
    ).delete(synchronize_session=False)
    db.commit()
    db.delete(objetivo)
    for est in db.query(Estudiante).filter(Estudiante.carrera == CARRERA_PRUEBA):
        db.delete(est)
    db.commit()


def _filas_del_tema(db) -> list[dict]:
    return [f for f in _rendimiento_actividades(db) if f["tema"] == TEMA]


def _leer_csv(respuesta) -> list[dict]:
    texto = respuesta.content.decode("utf-8-sig")
    return list(csv.DictReader(io.StringIO(texto)))


def _del_escenario(filas: list[dict], escenario) -> list[dict]:
    ids = {
        str(escenario[k].id_capsula) for k in ("exp_mc", "exp_cuestionario", "ctl_mc")
    }
    return [f for f in filas if f["id_capsula"] in ids]


# --- Métricas del panel separadas por grupo ------------------------------------


def test_las_metricas_separan_al_grupo_control_del_experimental(db, escenario):
    filas = _filas_del_tema(db)

    assert [f["rol"] for f in filas] == ["control", "estudiante"]
    control, experimental = filas

    assert control["alumnos"] == 1
    assert control["unica"] == {"primeras": 1, "aciertos": 0, "porcentaje": 0.0}
    assert control["cuestionario"]["primeras"] == 0
    assert control["reintentos"] == 1

    assert experimental["alumnos"] == 1
    assert experimental["unica"] == {"primeras": 1, "aciertos": 1, "porcentaje": 100.0}
    assert experimental["cuestionario"] == {"primeras": 1, "promedio": 75.0}
    assert experimental["reintentos"] == 0


def test_el_panel_muestra_una_fila_por_grupo(http_docente, escenario):
    html = http_docente.get("/teacher/analytics").text

    assert '<td data-label="Grupo">Control</td>' in html
    assert '<td data-label="Grupo">Experimental</td>' in html


def test_el_panel_nombra_los_grupos_como_el_login(http_docente, escenario):
    """«Control» y «Experimental», como en /student/login; ya no «Personalizado»."""
    html = http_docente.get("/teacher/analytics").text

    assert "Personalizado" not in html
    assert '<td data-label="Grupo de estudio">Experimental</td>' in html
    assert '<td data-label="Grupo de estudio">Control</td>' in html


def test_el_panel_enlaza_la_exportacion_de_intentos(http_docente, escenario):
    assert 'href="/teacher/exportar/intentos.csv"' in http_docente.get(
        "/teacher/analytics"
    ).text


# --- Grupo en el historial de la API -----------------------------------------


def test_el_historial_de_la_api_trae_el_grupo(http_docente, escenario):
    for clave, rol in (("experimental", "estudiante"), ("control", "control")):
        respuesta = http_docente.get(
            "/api/capsulas",
            params={"id_estudiante": escenario[clave].id_estudiante},
        )
        assert respuesta.status_code == 200
        assert respuesta.json()
        assert {c["rol"] for c in respuesta.json()} == {rol}


def test_el_historial_de_la_api_exige_docente(escenario):
    respuesta = TestClient(app).get("/api/capsulas")

    assert respuesta.status_code == 401


# --- Exportación CSV de intentos ---------------------------------------------


def test_la_exportacion_exige_sesion_docente(escenario):
    respuesta = TestClient(app).get(
        "/teacher/exportar/intentos.csv", follow_redirects=False
    )

    assert respuesta.status_code == 303
    assert respuesta.headers["location"] == (
        "/teacher/login?next=/teacher/exportar/intentos.csv"
    )


def test_la_exportacion_es_un_csv_descargable(http_docente, escenario):
    respuesta = http_docente.get("/teacher/exportar/intentos.csv")

    assert respuesta.status_code == 200
    assert respuesta.headers["content-type"].startswith("text/csv")
    assert "attachment" in respuesta.headers["content-disposition"]
    assert "intentos" in respuesta.headers["content-disposition"]
    # BOM: sin él, Excel abre el UTF-8 como Latin-1 y rompe los acentos.
    assert respuesta.content.startswith(b"\xef\xbb\xbf")
    encabezado = respuesta.content.decode("utf-8-sig").splitlines()[0]
    assert encabezado.split(",") == COLUMNAS


def test_la_exportacion_trae_una_fila_por_intento(http_docente, escenario):
    filas = _del_escenario(
        _leer_csv(http_docente.get("/teacher/exportar/intentos.csv")), escenario
    )
    exp = str(escenario["experimental"].id_estudiante)
    ctl = str(escenario["control"].id_estudiante)

    # En orden de fecha; la columna «fecha» no se compara (depende de la zona).
    sin_fecha = [{k: v for k, v in f.items() if k != "fecha"} for f in filas]
    tema = "'" + TEMA
    assert sin_fecha == [
        {
            "id_estudiante": exp, "rol": "estudiante", "codigo_objetivo": CODIGO,
            "tema": tema, "id_capsula": str(escenario["exp_mc"].id_capsula),
            "tipo_actividad": "quiz_mc", "numero_intento": "1",
            "es_primer_intento": "1", "es_correcta": "1",
            "aciertos": "", "total_preguntas": "",
        },
        {
            "id_estudiante": exp, "rol": "estudiante", "codigo_objetivo": CODIGO,
            "tema": tema, "id_capsula": str(escenario["exp_cuestionario"].id_capsula),
            "tipo_actividad": "flashcards_y_quiz", "numero_intento": "1",
            "es_primer_intento": "1", "es_correcta": "",
            "aciertos": "3", "total_preguntas": "4",
        },
        {
            "id_estudiante": ctl, "rol": "control", "codigo_objetivo": CODIGO,
            "tema": tema, "id_capsula": str(escenario["ctl_mc"].id_capsula),
            "tipo_actividad": "quiz_mc", "numero_intento": "1",
            "es_primer_intento": "1", "es_correcta": "0",
            "aciertos": "", "total_preguntas": "",
        },
        {
            "id_estudiante": ctl, "rol": "control", "codigo_objetivo": CODIGO,
            "tema": tema, "id_capsula": str(escenario["ctl_mc"].id_capsula),
            "tipo_actividad": "quiz_mc", "numero_intento": "2",
            "es_primer_intento": "0", "es_correcta": "1",
            "aciertos": "", "total_preguntas": "",
        },
    ]
    assert filas[0]["fecha"].startswith("2001-03-05")


def test_la_exportacion_no_trae_datos_personales(http_docente, escenario):
    texto = http_docente.get("/teacher/exportar/intentos.csv").content.decode(
        "utf-8-sig"
    )

    for clave in ("experimental", "control"):
        est = escenario[clave]
        for dato in (est.google_sub, est.google_email, est.google_nombre):
            assert dato not in texto
    for columna in ("nombre", "correo", "email", "google_sub", "carrera"):
        assert columna not in texto.splitlines()[0]


def test_la_exportacion_escapa_los_textos_que_parecen_formulas(http_docente, escenario):
    filas = _del_escenario(
        _leer_csv(http_docente.get("/teacher/exportar/intentos.csv")), escenario
    )

    assert filas
    for fila in filas:
        assert fila["tema"] == "'" + TEMA
        for valor in fila.values():
            assert not valor.startswith(("=", "+", "-", "@"))


# --- Filtro por fecha --------------------------------------------------------


def test_la_exportacion_filtra_desde_una_fecha(http_docente, escenario):
    respuesta = http_docente.get(
        "/teacher/exportar/intentos.csv", params={"desde": "2001-03-20"}
    )

    assert respuesta.status_code == 200
    filas = _del_escenario(_leer_csv(respuesta), escenario)
    assert [(f["rol"], f["numero_intento"]) for f in filas] == [
        ("control", "1"),
        ("control", "2"),
    ]


def test_la_exportacion_filtra_hasta_una_fecha_inclusive(http_docente, escenario):
    respuesta = http_docente.get(
        "/teacher/exportar/intentos.csv",
        params={"desde": "2001-03-01", "hasta": "2001-03-20"},
    )

    assert respuesta.status_code == 200
    filas = _leer_csv(respuesta)
    # Con el rango en 2001 solo quedan las filas del escenario; el 20-mar entra.
    assert [(f["rol"], f["tipo_actividad"]) for f in filas] == [
        ("estudiante", "quiz_mc"),
        ("estudiante", "flashcards_y_quiz"),
        ("control", "quiz_mc"),
    ]


@pytest.mark.parametrize(
    "params",
    [
        {"desde": "08-11-2026"},
        {"hasta": "2026-13-01"},
        {"desde": "ayer"},
        {"desde": "2001-04-01", "hasta": "2001-03-01"},
    ],
)
def test_una_fecha_invalida_es_400_con_mensaje(http_docente, escenario, params):
    respuesta = http_docente.get("/teacher/exportar/intentos.csv", params=params)

    assert respuesta.status_code == 400
    assert "AAAA-MM-DD" in respuesta.text or "posterior" in respuesta.text
