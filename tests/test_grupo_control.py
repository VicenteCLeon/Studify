"""El grupo control: registro propio y cápsula básica, sin personalización VARK.

Desde el 04-nov-2026 el control no usa PERFIL_CONTROL para generar: recibe un
resumen del material y un `quiz_mc` (ver tests/test_control_neutro.py).
"""

import csv
import re
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select

from studify.db.models import DiagnosticoVark, Estudiante, MicrocapsulaGenerada
from studify.main import app
from studify.vark.scoring import PerfilVark
from studify.web import sesion
from tests import test_api_capsulas as pruebas_capsulas
from tests.conftest import necesita_bd

# Reutilizan el material curado y el doble del LLM de las pruebas del motor.
escenario = pruebas_capsulas.escenario
cliente_falso = pruebas_capsulas.cliente_falso
navegador_de_estudiante = pruebas_capsulas.navegador_de


def test_perfil_control_es_fijo_y_suma_cien():
    from studify.vark.perfiles import PERFIL_CONTROL, perfil_de_contenido

    control = SimpleNamespace(rol="control")
    assert PerfilVark(
        Decimal("19.12"), Decimal("27.11"), Decimal("25.56"), Decimal("28.21")
    ) == PERFIL_CONTROL
    assert PERFIL_CONTROL.total == 100
    # Ni la falta de diagnóstico ni un perfil individual extremo lo alteran.
    assert perfil_de_contenido(control, None) == PERFIL_CONTROL
    assert perfil_de_contenido(control, _diagnostico(100, 0, 0, 0)) == PERFIL_CONTROL


def _diagnostico(v, a, r, k):
    return SimpleNamespace(
        porcentaje_v=Decimal(v), porcentaje_a=Decimal(a),
        porcentaje_r=Decimal(r), porcentaje_k=Decimal(k),
    )


def test_estudiante_comun_conserva_su_perfil_individual():
    from studify.vark.perfiles import perfil_de_contenido

    comun = SimpleNamespace(rol="estudiante")
    assert perfil_de_contenido(comun, _diagnostico(100, 0, 0, 0)).v == 100
    assert perfil_de_contenido(comun, _diagnostico(0, 0, 0, 100)).k == 100
    assert perfil_de_contenido(comun, None) is None


@necesita_bd
def test_entrada_control_reutiliza_aceptacion_y_no_ofrece_cuestionario():
    from tests.identidad_web import control_google_sin_registro

    cliente = TestClient(app)
    id_control = control_google_sin_registro(cliente)
    try:
        html = cliente.get("/student/control").text
        assert "data-aceptacion" in html
        assert "data-requiere-acepto" in html
        assert 'name="acepto"' in html
        assert 'name="q1"' not in html
        assert 'href="/student/vark"' not in html
    finally:
        _borrar_estudiante(id_control)


def _borrar_estudiante(id_estudiante: int) -> None:
    from studify.db.session import SessionLocal

    with SessionLocal() as db:
        estudiante = db.get(Estudiante, id_estudiante)
        if estudiante is not None:
            db.delete(estudiante)
            db.commit()


def test_perfil_control_reproduce_promedio_de_los_43():
    from scripts.import_vark_csv import leer_selecciones
    from studify.vark.perfiles import PERFIL_CONTROL
    from studify.vark.scoring import PuntajesVark, calificar, normalizar_a_porcentajes

    archivo = Path(__file__).resolve().parents[1] / "data/data_cuestionarios_43.csv"
    if not archivo.is_file():
        pytest.skip("el CSV original no se versiona")
    with archivo.open(encoding="utf-8-sig", newline="") as entrada:
        filas = list(csv.reader(entrada))[1:]
    perfiles = []
    for fila in filas:
        if not any(fila):
            continue
        selecciones, errores = leer_selecciones(fila)
        assert not errores
        perfiles.append(calificar(selecciones)[1])
    assert len(perfiles) == 43
    # Las sumas en centésimas permiten reutilizar el reparto de resto mayor.
    sumas = [int(sum(p.como_dict()[c] for p in perfiles) * 100) for c in "VARK"]
    assert normalizar_a_porcentajes(PuntajesVark(*sumas)) == PERFIL_CONTROL


def _token_control(cliente) -> str:
    html = cliente.get("/student/control").text
    return re.search(r'name="token_sesion" value="([^"]+)"', html).group(1)


@pytest.fixture
def navegador_control(db):
    """Cuenta control de Google que completa su registro por HTTP.

    Desde el punto 2a no hay alta local: la cuenta la crea Google
    (`control_google_sin_registro`) y el formulario real de `/student/control`
    registra los datos opcionales y la aceptación. Limpia solo su id.
    """
    from tests.identidad_web import control_google_sin_registro

    cliente = TestClient(app)
    id_estudiante = control_google_sin_registro(cliente)
    respuesta = cliente.post("/student/control", data={
        "acepto": "si", "token_sesion": _token_control(cliente),
    })
    assert respuesta.status_code == 204, respuesta.text
    try:
        yield cliente, id_estudiante
    finally:
        db.expire_all()
        estudiante = db.get(Estudiante, id_estudiante)
        if estudiante is not None:
            db.delete(estudiante)
            db.commit()


@necesita_bd
def test_registro_control_sin_diagnostico_con_aceptacion(db, navegador_control):
    from studify.web import consentimiento

    cliente, id_estudiante = navegador_control
    estudiante = db.get(Estudiante, id_estudiante)
    assert estudiante.rol == "control"
    assert not estudiante.diagnosticos
    assert not consentimiento.pendientes(db, id_estudiante)
    assert cliente.get("/student/catalog").status_code == 200
    datos = cliente.get("/mis-datos/exportar").json()
    assert datos["estudiante"]["rol"] == "control"
    assert datos["diagnosticos_vark"] == []


@necesita_bd
@pytest.mark.parametrize("ruta", ["/student/vark", "/student/vark?modo=actualizar"])
def test_control_no_accede_al_cuestionario(navegador_control, ruta):
    cliente, _ = navegador_control
    respuesta = cliente.get(ruta, follow_redirects=False)
    assert respuesta.status_code == 303
    assert respuesta.headers["location"] == "/student/profile"


@necesita_bd
@pytest.mark.parametrize("modo", ["nuevo", "actualizar", ""])
def test_control_no_se_personaliza_con_post_manual(db, navegador_control, modo):
    cliente, id_estudiante = navegador_control
    antes = db.scalar(select(func.count()).select_from(Estudiante))
    respuesta = cliente.post(
        "/student/vark", data={"q1": "a", "acepto": "si", "modo": modo, "rol": "estudiante"}
    )
    assert respuesta.status_code == 403
    db.expire_all()
    assert db.get(Estudiante, id_estudiante).rol == "control"
    assert db.scalar(select(func.count()).select_from(Estudiante)) == antes
    assert not db.get(Estudiante, id_estudiante).diagnosticos


@necesita_bd
def test_control_tampoco_admite_diagnostico_por_api(db, navegador_control, http_docente):
    _, id_estudiante = navegador_control
    respuesta = http_docente.post(
        "/api/diagnosticos",
        json={"id_estudiante": id_estudiante, "respuestas": [
            {"num_pregunta": 1, "alternativas": ["a"]},
        ]},
    )
    assert respuesta.status_code == 403
    assert db.scalar(select(func.count()).select_from(DiagnosticoVark).where(
        DiagnosticoVark.id_estudiante == id_estudiante
    )) == 0


@necesita_bd
def test_perfil_control_explica_origen_y_no_ofrece_personalizar(navegador_control):
    cliente, _ = navegador_control
    respuesta = cliente.get("/student/profile")
    assert respuesta.status_code == 200
    assert "43" in respuesta.text
    assert "Perfil general" in respuesta.text
    assert 'href="/student/vark"' not in respuesta.text
    assert 'href="/student/vark"' not in cliente.get("/mis-datos").text
    # La cápsula del control ya no sigue una configuración VARK: no se muestra.
    assert "Cómo se construirán tus microcápsulas" not in respuesta.text
    assert "Lo que incluirá cada cápsula" not in respuesta.text
    assert "recursos visuales" not in respuesta.text


@necesita_bd
def test_registro_control_exige_aceptacion_y_consentimiento_de_genero(db):
    from tests.identidad_web import control_google_sin_registro

    cliente = TestClient(app)
    id_control = control_google_sin_registro(cliente)
    try:
        antes = db.scalar(select(func.count()).select_from(Estudiante))
        for datos in (
            {}, {"acepto": "si", "genero": "Femenino"},
            {"acepto": "si", "carrera": "x" * 81},
        ):
            respuesta = cliente.post(
                "/student/control", data=datos | {"token_sesion": _token_control(cliente)},
            )
            assert respuesta.status_code == 200
            assert "alerta-error" in respuesta.text
        assert db.scalar(select(func.count()).select_from(Estudiante)) == antes
        db.expire_all()
        assert not db.get(Estudiante, id_control).aceptaciones
    finally:
        _borrar_estudiante(id_control)


@necesita_bd
def test_sin_alta_local_del_control(db):
    """Punto 2a: los dos grupos entran solo con Google."""
    cliente = TestClient(app)
    antes = db.scalar(select(func.count()).select_from(Estudiante))

    entrada = cliente.get("/student/control", follow_redirects=False)
    alta = cliente.post("/student/control", data={"acepto": "si"})

    assert entrada.status_code == 303
    assert entrada.headers["location"] == "/student/login?rol=control"
    assert alta.status_code == 403
    assert not cliente.cookies.get(sesion.COOKIE_ESTUDIANTE)
    assert db.scalar(select(func.count()).select_from(Estudiante)) == antes


@necesita_bd
def test_registro_control_no_cambia_rol_de_sesion_abierta(navegador_control):
    cliente, id_estudiante = navegador_control
    respuesta = cliente.post("/student/control", data={"acepto": "si"})
    assert respuesta.status_code == 409
    assert int(cliente.cookies.get(sesion.COOKIE_ESTUDIANTE).split(".")[0]) == id_estudiante


@necesita_bd
def test_computador_compartido_conserva_entrada_control(db, navegador_control):
    """«Soy otra persona» desde el control lleva al acceso Google con Control elegido."""
    cliente, id_primero = navegador_control
    html = cliente.get("/student/control").text
    assert "/student/salir?grupo=control" in html
    salida = cliente.post(
        "/student/salir?grupo=control", data={"motivo": "otra_persona"}, follow_redirects=False,
    )
    assert salida.headers["location"] == "/student/control"
    assert not cliente.cookies.get(sesion.COOKIE_ESTUDIANTE)
    entrada = cliente.get("/student/control", follow_redirects=False)
    assert entrada.headers["location"] == "/student/login?rol=control"
    login = cliente.get(entrada.headers["location"]).text
    assert re.search(r'value="control"[^>]*checked', login)
    assert db.get(Estudiante, id_primero).rol == "control"


@necesita_bd
def test_registro_comun_conserva_personalizacion_e_ignora_rol_del_formulario(db):
    from tests.identidad_web import enviar_vark

    cliente = TestClient(app)
    respuesta = enviar_vark(cliente, data={
        "acepto": "si", "q1": "a", "rol": "control",
    })
    assert respuesta.status_code == 204
    id_estudiante = int(cliente.cookies.get(sesion.COOKIE_ESTUDIANTE).split(".")[0])
    try:
        estudiante = db.get(Estudiante, id_estudiante)
        assert estudiante.rol == "estudiante"
        assert len(estudiante.diagnosticos) == 1
        assert 'href="/student/vark"' in cliente.get("/student/profile").text
        assert cliente.post("/student/control", data={"acepto": "si"}).status_code == 409
        db.refresh(estudiante)
        assert estudiante.rol == "estudiante"
    finally:
        db.delete(db.get(Estudiante, id_estudiante))
        db.commit()


@necesita_bd
def test_control_genera_sin_diagnostico_sin_audio_y_con_actividades(
    db, escenario, navegador_control, cliente_falso, http_docente
):
    cliente, id_estudiante = navegador_control
    objetivo = escenario["objetivo"].id_objetivo
    respuesta = cliente.post("/api/capsulas", json={
        "id_estudiante": id_estudiante, "id_objetivo": objetivo,
        "rol": "estudiante", "perfil": {"v": 100, "a": 0, "r": 0, "k": 0},
    })
    assert respuesta.status_code == 201, respuesta.text
    capsula = respuesta.json()
    fila = db.get(MicrocapsulaGenerada, capsula["id_capsula"])
    assert fila.id_config is None  # No se fabrica un diagnóstico de los 43 para esta persona.
    assert cliente_falso.llamadas == 1
    # Cápsula básica: título, objetivo, resumen, quiz_mc y fuentes.
    assert capsula["activacion"] == ""
    assert capsula["representacion_adaptativa"] == []
    assert capsula["ejemplo"] is None
    assert capsula["actividad"]["tipo"] == "quiz_mc"
    assert fila.contenido_json["representacion_adaptativa"] == []
    visor = cliente.get(f"/student/viewer/{objetivo}")
    assert visor.status_code == 200
    assert 'id="paso-activacion"' not in visor.text
    assert 'id="paso-desarrollo"' not in visor.text
    assert 'id="paso-concepto"' in visor.text
    # El control no tiene narración (04-nov-2026): ni widget ni selector de voz.
    assert 'class="capsula-audio"' not in visor.text
    assert "Voz de la narración" not in visor.text
    assert "generate-audio" not in visor.text
    assert "Ver perfil general" in visor.text
    assert cliente_falso.llamadas == 1  # El visor también utiliza el caché genérico.
    quiz = cliente.post(f"/api/capsulas/{capsula['id_capsula']}/quiz", json={
        "id_estudiante": id_estudiante, "alternativa_seleccionada": 0,
    })
    assert quiz.status_code == 201, quiz.text
    assert quiz.json()["es_correcta"] is True
    assert "Control" in http_docente.get("/teacher/analytics").text


# --- Sin audio en el grupo control (punto 1b) --------------------------------


@pytest.fixture
def sintesis_prohibida(monkeypatch):
    """Falla si alguien intenta sintetizar: el control no tiene narración."""
    from studify.media import audio

    def _no(*_a, **_k):
        pytest.fail("se intentó sintetizar la narración de una cápsula del control")

    monkeypatch.setattr(audio, "generar_audio", _no)


@necesita_bd
def test_narracion_de_capsula_control_es_403_tambien_para_el_docente(
    db, escenario, navegador_control, cliente_falso, http_docente, sintesis_prohibida
):
    cliente, id_control = navegador_control
    capsula = cliente.post("/api/capsulas", json={
        "id_estudiante": id_control, "id_objetivo": escenario["objetivo"].id_objetivo,
    }).json()
    ruta = f"/student/viewer/{capsula['id_capsula']}/generate-audio"

    assert cliente.post(ruta).status_code == 403
    assert http_docente.post(ruta).status_code == 403


@necesita_bd
def test_control_no_guarda_preferencia_de_voz(db, navegador_control):
    cliente, id_control = navegador_control

    for cabeceras in ({}, {"HX-Request": "true"}):
        respuesta = cliente.post(
            "/student/preferencias/voz", data={"voz": "masculina-rapida"},
            headers=cabeceras, follow_redirects=False,
        )
        assert respuesta.status_code == 403
    db.expire_all()
    estudiante = db.get(Estudiante, id_control)
    assert (estudiante.voz_genero, estudiante.voz_modo) == (None, None)


@necesita_bd
def test_perfil_control_sin_selector_de_voz(navegador_control):
    cliente, _ = navegador_control
    html = cliente.get("/student/profile").text

    assert "Voz de la narración" not in html
    assert 'id="voz-guardada"' not in html


def _experimental_con_aceptacion(db, perfil: PerfilVark) -> Estudiante:
    """Estudiante con diagnóstico que ya aceptó los documentos vigentes."""
    from studify.web import consentimiento

    estudiante = pruebas_capsulas._estudiante_con_perfil(db, perfil)
    consentimiento.registrar(db, estudiante.id_estudiante)
    return estudiante


@necesita_bd
@pytest.mark.parametrize(
    ("vector", "con_audio"),
    [((0, 0, 0, 100), False), ((20, 30, 25, 25), True), ((25, 25, 25, 25), True)],
)
def test_experimental_conserva_audio_segun_p_a(
    db, escenario, cliente_falso, navegador_de_estudiante, vector, con_audio
):
    """La regla del experimental no cambia: narración con p_A ≥ 25 %."""
    perfil = PerfilVark(*(Decimal(x) for x in vector))
    estudiante = _experimental_con_aceptacion(db, perfil)
    cliente = navegador_de_estudiante(estudiante.id_estudiante)

    visor = cliente.get(f"/student/viewer/{escenario['objetivo'].id_objetivo}").text
    perfil_html = cliente.get("/student/profile").text

    assert ('class="capsula-audio"' in visor) is con_audio
    assert ("Voz de la narración" in visor) is con_audio
    assert ("Voz de la narración" in perfil_html) is con_audio


@necesita_bd
def test_experimental_puede_pedir_narracion_y_guardar_su_voz(
    db, escenario, cliente_falso, navegador_de_estudiante, monkeypatch
):
    from studify.media import audio

    pedidos = []

    def _falsa(texto, destino, language="es", *, preferencia=None):
        pedidos.append(destino.name)
        raise audio.ErrorAudio("síntesis falsa del test")  # no deja WAV en public/

    monkeypatch.setattr(audio, "generar_audio", _falsa)
    estudiante = _experimental_con_aceptacion(
        db, PerfilVark(*(Decimal(x) for x in (20, 30, 25, 25)))
    )
    cliente = navegador_de_estudiante(estudiante.id_estudiante)
    capsula = cliente.post("/api/capsulas", json={
        "id_estudiante": estudiante.id_estudiante,
        "id_objetivo": escenario["objetivo"].id_objetivo,
    }).json()

    narracion = cliente.post(f"/student/viewer/{capsula['id_capsula']}/generate-audio")
    voz = cliente.post(
        "/student/preferencias/voz", data={"voz": "masculina-rapida"},
        follow_redirects=False,
    )

    assert narracion.status_code == 200
    assert len(pedidos) == 1
    assert voz.status_code == 303
    db.expire_all()
    assert db.get(Estudiante, estudiante.id_estudiante).voz_modo == "rapida"


@necesita_bd
def test_cache_control_se_comparte_solo_entre_controles(
    db, escenario, navegador_control, cliente_falso, http_docente
):
    from studify.vark.perfiles import PERFIL_CONTROL

    cliente, id_control = navegador_control
    objetivo = escenario["objetivo"].id_objetivo
    # Un estudiante personalizado con el mismo vector no presta su caché al control.
    comun = pruebas_capsulas._estudiante_con_perfil(db, PERFIL_CONTROL)
    normal = http_docente.post("/api/capsulas", json={
        "id_estudiante": comun.id_estudiante, "id_objetivo": objetivo,
    })
    assert normal.status_code == 201
    primera = cliente.post("/api/capsulas", json={
        "id_estudiante": id_control, "id_objetivo": objetivo,
    })
    assert primera.status_code == 201
    assert primera.json()["origen"] == "generada"
    assert cliente_falso.llamadas == 2
    otro = Estudiante(rol="control")
    db.add(otro)
    db.commit()
    try:
        segunda = http_docente.post("/api/capsulas", json={
            "id_estudiante": otro.id_estudiante, "id_objetivo": objetivo,
        })
        assert segunda.status_code == 201
        assert segunda.json()["origen"] == "cache_compartido"
        assert segunda.json()["id_estudiante"] == otro.id_estudiante
        assert cliente_falso.llamadas == 2
    finally:
        db.delete(otro)
        db.commit()


@necesita_bd
def test_diagnostico_individual_no_cambia_generacion_control(
    db, escenario, navegador_control, cliente_falso, monkeypatch
):
    from studify.api.routers import capsules
    from studify.vark.perfiles import VARIANTE_CONTROL

    cliente, id_estudiante = navegador_control
    # Incluso un diagnóstico agregado por un proceso externo no habilita personalización.
    diagnostico = DiagnosticoVark(
        id_estudiante=id_estudiante, puntaje_v=16, puntaje_a=0, puntaje_r=0, puntaje_k=0,
        porcentaje_v=100, porcentaje_a=0, porcentaje_r=0, porcentaje_k=0,
    )
    db.add(diagnostico)
    db.commit()
    assert cliente.get(f"/api/diagnosticos/{diagnostico.id_diagnostico}").status_code == 403
    construir = capsules.orchestrator.construir
    recuperar = capsules.recuperar
    configuraciones, variantes, canales = [], [], []

    def capturar(**kwargs):
        configuraciones.append(kwargs["config"])
        variantes.append(kwargs["variante"])
        return construir(**kwargs)

    def recuperar_espiado(db, **kwargs):
        canales.append(kwargs.get("canal_primario"))
        return recuperar(db, **kwargs)

    monkeypatch.setattr(capsules.orchestrator, "construir", capturar)
    monkeypatch.setattr(capsules, "recuperar", recuperar_espiado)
    monkeypatch.setattr(
        capsules, "aplicar_reglas",
        lambda *_: pytest.fail("el control no pasa por las reglas VARK"),
    )
    for regenerar in (False, True):
        respuesta = cliente.post("/api/capsulas", params={"regenerar": regenerar}, json={
            "id_estudiante": id_estudiante,
            "id_objetivo": escenario["objetivo"].id_objetivo,
        })
        assert respuesta.status_code == 201
    # Sin configuración VARK, sin canal para ordenar fragmentos y en su variante.
    assert configuraciones == [None, None]
    assert canales == [None, None]
    assert variantes == [VARIANTE_CONTROL] * 2
    assert cliente_falso.llamadas == 2


@necesita_bd
def test_capsula_del_control_anterior_no_se_reutiliza(
    db, escenario, navegador_control, cliente_falso
):
    """Las cápsulas `control-cohorte43-v1` quedan en la base, pero no se sirven."""
    from studify.rag import orchestrator
    from studify.rag.retriever import recuperar
    from studify.vark.perfiles import PERFIL_CONTROL, VERSION_PERFIL_CONTROL
    from studify.vark.rules import aplicar_reglas
    from tests.material import capsula_valida

    cliente, id_control = navegador_control
    objetivo = escenario["objetivo"]
    config = aplicar_reglas(PERFIL_CONTROL)
    anterior = orchestrator.construir(
        objetivo=objetivo,
        fragmentos=recuperar(
            db, id_objetivo=objetivo.id_objetivo,
            canal_primario=config.jerarquia.canal_primario,
        ),
        config=config, modelo="modelo-de-prueba", variante=VERSION_PERFIL_CONTROL,
    )
    completa = capsula_valida()
    otro = Estudiante(rol="control")
    db.add(otro)
    db.flush()
    db.add(MicrocapsulaGenerada(
        id_estudiante=otro.id_estudiante, id_objetivo=objetivo.id_objetivo,
        titulo=completa["titulo"],
        contenido_json={k: v for k, v in completa.items() if k != "actividad"},
        mini_quiz_json=completa["actividad"], huella_generacion=anterior.huella,
        modelo_llm="modelo-de-prueba",
    ))
    db.commit()
    try:
        respuesta = cliente.post("/api/capsulas", json={
            "id_estudiante": id_control, "id_objetivo": objetivo.id_objetivo,
        })
        assert respuesta.status_code == 201, respuesta.text
        assert respuesta.json()["origen"] == "generada"
        assert respuesta.json()["representacion_adaptativa"] == []
        assert cliente_falso.llamadas == 1
    finally:
        db.query(MicrocapsulaGenerada).filter(
            MicrocapsulaGenerada.id_estudiante == otro.id_estudiante
        ).delete()
        db.delete(otro)
        db.commit()


@necesita_bd
def test_capsula_basica_en_historial_docente_mis_datos_y_exportacion(
    db, escenario, navegador_control, cliente_falso, http_docente
):
    cliente, id_control = navegador_control
    objetivo = escenario["objetivo"].id_objetivo
    capsula = cliente.post("/api/capsulas", json={
        "id_estudiante": id_control, "id_objetivo": objetivo,
    }).json()
    assert capsula["representacion_adaptativa"] == []

    panel = http_docente.get("/teacher/analytics")
    assert panel.status_code == 200
    assert f"#{capsula['id_capsula']}" in panel.text
    historial = http_docente.get("/api/capsulas", params={"id_estudiante": id_control})
    assert historial.status_code == 200
    assert [c["id_capsula"] for c in historial.json()] == [capsula["id_capsula"]]
    leida = http_docente.get(f"/api/capsulas/{capsula['id_capsula']}")
    assert leida.status_code == 200
    assert leida.json()["ejemplo"] is None

    assert cliente.get("/mis-datos").status_code == 200
    exportada = cliente.get("/mis-datos/exportar").json()["capsulas"]
    assert exportada[0]["contenido"]["representacion_adaptativa"] == []
    assert exportada[0]["contenido"]["ejemplo"] is None
    assert exportada[0]["actividad"]["tipo"] == "quiz_mc"


@necesita_bd
def test_migracion_rol_es_reversible_y_preserva_estudiantes():
    import runpy
    from uuid import uuid4

    from alembic.migration import MigrationContext
    from alembic.operations import Operations
    from sqlalchemy.exc import IntegrityError

    from studify.db.session import engine

    migracion = runpy.run_path(str(
        Path(__file__).resolve().parents[1]
        / "alembic/versions/f6b2c8d40e53_grupo_control.py"
    ))
    # DDL transaccional en un esquema propio; no requiere CREATEDB ni toca la cohorte.
    with engine.connect() as conn:
        transaccion = conn.begin()
        try:
            esquema = "test_rol_" + uuid4().hex
            conn.exec_driver_sql(f'CREATE SCHEMA "{esquema}"')
            conn.exec_driver_sql(f'SET LOCAL search_path TO "{esquema}"')
            conn.exec_driver_sql("CREATE TABLE estudiante (id integer PRIMARY KEY)")
            conn.exec_driver_sql("INSERT INTO estudiante VALUES (1)")
            with Operations.context(MigrationContext.configure(conn)):
                migracion["upgrade"]()
                assert conn.exec_driver_sql("SELECT rol FROM estudiante").scalar() == "estudiante"
                conn.exec_driver_sql("INSERT INTO estudiante VALUES (2, 'control')")
                with pytest.raises(IntegrityError), conn.begin_nested():
                    conn.exec_driver_sql("INSERT INTO estudiante VALUES (3, 'otro')")
                migracion["downgrade"]()
                assert conn.exec_driver_sql("SELECT count(*) FROM estudiante").scalar() == 2
                migracion["upgrade"]()
                assert conn.exec_driver_sql(
                    "SELECT count(*) FROM estudiante WHERE rol = 'estudiante'"
                ).scalar() == 2
        finally:
            transaccion.rollback()
