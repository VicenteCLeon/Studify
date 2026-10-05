"""Tests de la preferencia de voz del estudiante (Etapa 2 del audio del visor).

Cubren la migración (ida y vuelta en una base temporal), el endpoint que la
guarda, que el visor narre con la voz del **dueño** de la cápsula, la exportación
de «Mis datos» y que la voz jamás se decida leyendo `estudiante.genero`, que es
el dato sociodemográfico sensible.

La síntesis se sustituye por un doble (`audio.generar_audio`): acá importa qué
voz se pide y con qué nombre de archivo, no el audio.
"""

import uuid
from decimal import Decimal
from pathlib import Path

import pytest
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.engine import make_url

from alembic import command
from studify.api.routers.capsules import get_cliente_llm
from studify.config import get_settings
from studify.db.models import (
    DocumentoFuente,
    Estudiante,
    Fragmento,
    MicrocapsulaGenerada,
    ObjetivoAprendizaje,
)
from studify.main import app
from studify.media import audio
from studify.media.audio import PreferenciaVoz, preferencia_guardada
from studify.vark.scoring import PerfilVark
from studify.web import consentimiento, exportacion, sesion
from tests.conftest import necesita_bd
from tests.test_api_capsulas import TEXTO_LARGO, ClienteObediente, _estudiante_con_perfil

RAIZ = Path(__file__).resolve().parents[1]
CARRERA = "Ingeniería Informática (test capsulas)"  # la que limpia `_estudiante_con_perfil`
AUDITIVO = PerfilVark(v=Decimal(0), a=Decimal(60), r=Decimal(20), k=Decimal(20))
# Lo que narra el visor: activación + concepto central de la cápsula del escenario.
ACTIVACION, CONCEPTO = "¿Por qué?", "Porque X → Y."
GUION = f"{ACTIVACION} {CONCEPTO}"


# --- Sin base de datos ----------------------------------------------------------


def test_sin_preferencia_guardada_suena_dora():
    assert preferencia_guardada(None, None) == PreferenciaVoz("femenina", "calidad")
    assert audio.resolver_voz(preferencia_guardada(None, None)).voz == "ef_dora"


def test_la_preferencia_solo_recibe_los_campos_de_voz():
    """Recibe `voz_genero` y `voz_modo`, no la fila: no tiene cómo leer `genero`."""
    import inspect as inspeccion

    assert list(inspeccion.signature(preferencia_guardada).parameters) == [
        "voz_genero",
        "voz_modo",
    ]


def test_el_selector_habla_de_la_voz_y_no_del_genero_de_quien_escucha():
    from studify.web.textos import OPCIONES_VOZ

    textos_visibles = " ".join(" ".join(o[1:]) for o in OPCIONES_VOZ).lower()
    plantilla = (RAIZ / "src/studify/web/templates/student/_selector_voz.html").read_text(
        encoding="utf-8"
    )

    assert "tu género" not in textos_visibles and "tu genero" not in textos_visibles
    assert "tu género" not in plantilla.lower()
    assert all(o[2].startswith("Voz ") for o in OPCIONES_VOZ)


# --- Migración: ida y vuelta --------------------------------------------------------


@necesita_bd
def test_la_migracion_sube_baja_y_vuelve_a_subir(monkeypatch):
    """En una base temporal del mismo servidor: la de desarrollo no se toca."""
    url = make_url(get_settings().database_url)
    nombre = f"studify_test_migracion_{uuid.uuid4().hex[:8]}"
    servidor = create_engine(url.set(database="postgres"), isolation_level="AUTOCOMMIT")
    with servidor.connect() as conn:
        conn.execute(text(f'CREATE DATABASE "{nombre}"'))
    temporal = url.set(database=nombre)
    try:
        monkeypatch.setattr(
            get_settings(), "database_url", temporal.render_as_string(hide_password=False)
        )
        # Sin `alembic.ini`: su `fileConfig` reconfiguraría el logging de la suite.
        cfg = Config()
        cfg.set_main_option("script_location", str(RAIZ / "alembic"))
        motor = create_engine(temporal)

        def columnas() -> set[str]:
            return {c["name"] for c in inspect(motor).get_columns("estudiante")}

        command.upgrade(cfg, "head")
        assert {"voz_genero", "voz_modo"} <= columnas()
        command.downgrade(cfg, "-1")
        assert not {"voz_genero", "voz_modo"} & columnas()
        command.upgrade(cfg, "head")
        assert {"voz_genero", "voz_modo"} <= columnas()

        with motor.begin() as conn:
            conn.execute(text("INSERT INTO estudiante (voz_genero, voz_modo) VALUES (NULL, NULL)"))
            with pytest.raises(Exception, match="ck_estudiante_voz_genero"), conn.begin_nested():
                conn.execute(text("INSERT INTO estudiante (voz_genero) VALUES ('otra')"))
        motor.dispose()
    finally:
        with servidor.connect() as conn:
            conn.execute(text(f'DROP DATABASE IF EXISTS "{nombre}" WITH (FORCE)'))
        servidor.dispose()


# --- Con base de datos: endpoint, visor y exportación -------------------------------


@pytest.fixture
def escenario(db):
    """Un objetivo con material, dos estudiantes auditivos y una cápsula del primero."""
    objetivo = ObjetivoAprendizaje(
        codigo_objetivo="TEST-VOZ-01",
        asignatura="Bases de Datos (test voz)",
        unidad="Unidad 3",
        tema="Segunda forma normal",
        descripcion="Reconocer dependencias parciales.",
        estado="activo",
    )
    documento = DocumentoFuente(
        titulo="Apunte de prueba (voz)",
        formato="pdf",
        hash_archivo="hash-de-prueba-voz",
        estado_curacion="validado",
    )
    db.add_all([objetivo, documento])
    db.flush()
    db.add(
        Fragmento(
            id_documento=documento.id_documento,
            id_objetivo=objetivo.id_objetivo,
            numero_fragmento=1,
            tipo_fragmento="texto",
            contenido_texto=TEXTO_LARGO,
            pagina_inicio=1,
            pagina_fin=1,
            estado_validacion="validado",
        )
    )
    duenio = _estudiante_con_perfil(db, AUDITIVO)
    ajeno = _estudiante_con_perfil(db, AUDITIVO)
    capsula = MicrocapsulaGenerada(
        id_estudiante=duenio.id_estudiante,
        id_objetivo=objetivo.id_objetivo,
        titulo="Segunda forma normal",
        contenido_json={"activacion": ACTIVACION, "concepto_central": CONCEPTO},
        estado_validacion="validada",
    )
    db.add(capsula)
    db.commit()
    for estudiante in (duenio, ajeno):
        consentimiento.registrar(db, estudiante.id_estudiante)

    yield {"objetivo": objetivo, "duenio": duenio, "ajeno": ajeno, "capsula": capsula}

    db.query(MicrocapsulaGenerada).filter(
        MicrocapsulaGenerada.id_objetivo == objetivo.id_objetivo
    ).delete()
    db.commit()
    db.delete(documento)
    db.delete(objetivo)
    for est in db.query(Estudiante).filter(Estudiante.carrera == CARRERA):
        db.delete(est)
    db.commit()


def _navegador(id_estudiante: int) -> TestClient:
    cliente = TestClient(app)
    cliente.cookies.set(sesion.COOKIE_ESTUDIANTE, f"{id_estudiante}.{sesion._firma(id_estudiante)}")
    return cliente


@pytest.fixture
def sintesis_falsa(monkeypatch):
    """Anota con qué preferencia y en qué archivo se pidió cada narración."""
    pedidos: list[tuple[PreferenciaVoz, str]] = []

    def _falsa(texto, destino, language="es", *, preferencia=None):
        pedidos.append((preferencia, destino.name))
        raise audio.ErrorAudio("síntesis falsa del test")  # no deja WAV en public/

    monkeypatch.setattr(audio, "generar_audio", _falsa)
    return pedidos


def _refrescar(db, estudiante: Estudiante) -> Estudiante:
    db.expire_all()
    return db.get(Estudiante, estudiante.id_estudiante)


@necesita_bd
@pytest.mark.parametrize(
    ("voz", "genero", "modo"),
    [
        ("femenina-calidad", "femenina", "calidad"),
        ("masculina-calidad", "masculina", "calidad"),
        ("femenina-rapida", "femenina", "rapida"),
        ("masculina-rapida", "masculina", "rapida"),
    ],
)
def test_el_estudiante_guarda_su_voz(db, escenario, voz, genero, modo):
    respuesta = _navegador(escenario["duenio"].id_estudiante).post(
        "/student/preferencias/voz", data={"voz": voz}, follow_redirects=False
    )

    assert respuesta.status_code == 303
    assert respuesta.headers["location"] == "/student/profile"
    duenio = _refrescar(db, escenario["duenio"])
    assert (duenio.voz_genero, duenio.voz_modo) == (genero, modo)


@necesita_bd
def test_una_opcion_desconocida_se_rechaza(db, escenario):
    respuesta = _navegador(escenario["duenio"].id_estudiante).post(
        "/student/preferencias/voz", data={"voz": "robot-rapida"}
    )

    assert respuesta.status_code == 422
    assert _refrescar(db, escenario["duenio"]).voz_genero is None


@necesita_bd
def test_sin_sesion_no_se_guarda_nada(escenario):
    respuesta = TestClient(app).post(
        "/student/preferencias/voz", data={"voz": "masculina-rapida"}, follow_redirects=False
    )

    assert respuesta.status_code == 303
    assert respuesta.headers["location"] == "/student/vark"


@necesita_bd
def test_un_estudiante_no_puede_guardar_la_preferencia_de_otro(db, escenario):
    """El estudiante sale de la cookie: un `id_estudiante` en el formulario se ignora."""
    ajeno = escenario["ajeno"]

    _navegador(ajeno.id_estudiante).post(
        "/student/preferencias/voz",
        data={"voz": "masculina-rapida", "id_estudiante": escenario["duenio"].id_estudiante},
    )

    assert _refrescar(db, escenario["duenio"]).voz_genero is None
    assert _refrescar(db, ajeno).voz_genero == "masculina"


@necesita_bd
def test_no_se_cambia_el_audio_de_una_capsula_ajena(db, escenario):
    respuesta = _navegador(escenario["ajeno"].id_estudiante).post(
        "/student/preferencias/voz",
        data={"voz": "masculina-calidad", "contexto": "visor",
              "id_capsula": escenario["capsula"].id_capsula},
        headers={"HX-Request": "true"},
    )

    assert respuesta.status_code == 404


@necesita_bd
def test_desde_el_visor_devuelve_el_widget_que_vuelve_a_pedir_el_audio(escenario):
    id_capsula = escenario["capsula"].id_capsula

    respuesta = _navegador(escenario["duenio"].id_estudiante).post(
        "/student/preferencias/voz",
        data={"voz": "masculina-rapida", "contexto": "visor", "id_capsula": id_capsula,
              "uid": str(id_capsula)},
        headers={"HX-Request": "true"},
    )

    assert respuesta.status_code == 200
    assert f'id="audio-widget-{id_capsula}"' in respuesta.text
    assert f'hx-post="/student/viewer/{id_capsula}/generate-audio"' in respuesta.text
    assert 'hx-trigger="load"' in respuesta.text


@necesita_bd
def test_desde_el_perfil_avisa_que_quedo_guardada(escenario):
    respuesta = _navegador(escenario["duenio"].id_estudiante).post(
        "/student/preferencias/voz",
        data={"voz": "masculina-calidad", "contexto": "perfil"},
        headers={"HX-Request": "true"},
    )

    assert "Voz guardada" in respuesta.text
    assert "Alex" in respuesta.text


@necesita_bd
def test_el_visor_narra_con_la_voz_del_duenio(db, escenario, sintesis_falsa):
    duenio = escenario["duenio"]
    duenio.voz_genero, duenio.voz_modo = "masculina", "rapida"
    db.commit()
    id_capsula = escenario["capsula"].id_capsula

    _navegador(duenio.id_estudiante).post(f"/student/viewer/{id_capsula}/generate-audio")

    preferencia, archivo = sintesis_falsa[0]
    assert preferencia == PreferenciaVoz("masculina", "rapida")
    piper_masculina = audio.VozElegida("piper", "es_ES-sharvard-medium", 0)
    assert archivo == f"{audio.huella_de_audio(GUION, piper_masculina)}.wav"


@necesita_bd
def test_el_docente_oye_la_voz_del_duenio(db, escenario, sintesis_falsa, http_docente):
    duenio = escenario["duenio"]
    duenio.voz_genero, duenio.voz_modo = "masculina", "calidad"
    db.commit()

    http_docente.post(f"/student/viewer/{escenario['capsula'].id_capsula}/generate-audio")

    assert sintesis_falsa[0][0] == PreferenciaVoz("masculina", "calidad")
    alex = audio.VozElegida("kokoro", "em_alex")
    assert sintesis_falsa[0][1] == f"{audio.huella_de_audio(GUION, alex)}.wav"


@necesita_bd
@pytest.mark.parametrize(
    ("genero_sociodemografico", "voz_genero", "voz_esperada"),
    [
        ("Masculino", None, "femenina"),  # sin preferencia: Dora, no «la de su género»
        ("Femenino", "masculina", "masculina"),
        ("No Binario / otra identidad", None, "femenina"),
    ],
)
def test_la_voz_nunca_se_decide_por_el_genero_del_estudiante(
    db, escenario, sintesis_falsa, genero_sociodemografico, voz_genero, voz_esperada
):
    duenio = escenario["duenio"]
    duenio.genero = genero_sociodemografico
    duenio.voz_genero = voz_genero
    db.commit()

    _navegador(duenio.id_estudiante).post(
        f"/student/viewer/{escenario['capsula'].id_capsula}/generate-audio"
    )

    assert sintesis_falsa[0][0].genero == voz_esperada


@necesita_bd
def test_cambiar_de_voz_no_reusa_el_audio_de_la_anterior(db, escenario, sintesis_falsa):
    duenio = escenario["duenio"]
    navegador = _navegador(duenio.id_estudiante)
    ruta = f"/student/viewer/{escenario['capsula'].id_capsula}/generate-audio"

    navegador.post(ruta)
    navegador.post("/student/preferencias/voz", data={"voz": "masculina-calidad"})
    navegador.post(ruta)

    assert sintesis_falsa[0][1] != sintesis_falsa[1][1]


# --- Caché por huella (H10) -------------------------------------------------------


@pytest.fixture
def sintesis_que_escribe(monkeypatch, tmp_path):
    """Síntesis falsa que sí deja el WAV, en un directorio temporal.

    El visor escribe en `src/studify/public/audio` relativo al directorio de
    trabajo; con `chdir` a `tmp_path` el test no toca la carpeta del repo.
    """
    monkeypatch.chdir(tmp_path)
    pedidos: list[str] = []

    def _escribe(texto, destino, language="es", *, preferencia=None):
        pedidos.append(destino.name)
        destino.parent.mkdir(parents=True, exist_ok=True)
        destino.write_bytes(b"RIFF")

    monkeypatch.setattr(audio, "generar_audio", _escribe)
    return pedidos


@necesita_bd
def test_un_audio_ya_sintetizado_no_se_vuelve_a_sintetizar(escenario, sintesis_que_escribe):
    navegador = _navegador(escenario["duenio"].id_estudiante)
    ruta = f"/student/viewer/{escenario['capsula'].id_capsula}/generate-audio"

    primera = navegador.post(ruta).text
    segunda = navegador.post(ruta).text

    assert len(sintesis_que_escribe) == 1
    assert f"/public/audio/{sintesis_que_escribe[0]}" in primera
    assert f"/public/audio/{sintesis_que_escribe[0]}" in segunda


@necesita_bd
def test_la_copia_del_cache_compartido_reutiliza_el_mismo_archivo(
    db, escenario, sintesis_que_escribe
):
    """Otro estudiante con la misma cápsula (copia) y la misma voz: un solo WAV."""
    ajeno = escenario["ajeno"]
    copia = MicrocapsulaGenerada(
        id_estudiante=ajeno.id_estudiante,
        id_objetivo=escenario["objetivo"].id_objetivo,
        titulo=escenario["capsula"].titulo,
        contenido_json=dict(escenario["capsula"].contenido_json),
        estado_validacion="validada",
    )
    db.add(copia)
    db.commit()

    original = _navegador(escenario["duenio"].id_estudiante).post(
        f"/student/viewer/{escenario['capsula'].id_capsula}/generate-audio"
    )
    de_la_copia = _navegador(ajeno.id_estudiante).post(
        f"/student/viewer/{copia.id_capsula}/generate-audio"
    )

    assert len(sintesis_que_escribe) == 1
    url = f"/public/audio/{sintesis_que_escribe[0]}"
    assert url in original.text and url in de_la_copia.text


@necesita_bd
def test_el_nombre_del_archivo_no_depende_del_id_de_la_capsula(escenario, sintesis_falsa):
    """Una base recreada con ids repetidos no puede servir el audio de otra cápsula."""
    _navegador(escenario["duenio"].id_estudiante).post(
        f"/student/viewer/{escenario['capsula'].id_capsula}/generate-audio"
    )

    # La huella no recibe el id: solo guion, motor y voz.
    assert sintesis_falsa[0][1] == f"{audio.huella_de_audio(GUION, audio.resolver_voz())}.wav"


@necesita_bd
def test_el_visor_muestra_el_selector_con_dora_por_defecto(db, escenario):
    app.dependency_overrides[get_cliente_llm] = ClienteObediente
    try:
        html = _navegador(escenario["duenio"].id_estudiante).get(
            f"/student/viewer/{escenario['objetivo'].id_objetivo}"
        ).text
    finally:
        app.dependency_overrides.pop(get_cliente_llm, None)

    assert "Voz de la narración" in html
    assert 'value="femenina-calidad" checked' in html
    assert 'name="contexto" value="visor"' in html


@necesita_bd
def test_el_perfil_muestra_la_voz_guardada(db, escenario):
    duenio = escenario["duenio"]
    duenio.voz_genero, duenio.voz_modo = "femenina", "rapida"
    db.commit()

    html = _navegador(duenio.id_estudiante).get("/student/profile").text

    assert 'value="femenina-rapida" checked' in html
    assert 'id="voz-guardada" role="status"' in html


@necesita_bd
def test_mis_datos_incluye_la_preferencia_de_voz(db, escenario):
    duenio = escenario["duenio"]
    duenio.voz_genero, duenio.voz_modo = "masculina", "rapida"
    db.commit()

    datos = exportacion.datos_de(db, _refrescar(db, duenio))

    assert datos["estudiante"]["voz_genero"] == "masculina"
    assert datos["estudiante"]["voz_modo"] == "rapida"
