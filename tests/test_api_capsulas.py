"""Tests de `POST /api/capsulas` (Fase 3).

Cubren lo que el endpoint decide **antes y después** de llamar al modelo: qué
rechaza, qué recupera del caché y qué versiona. La generación en sí ya está
cubierta en `test_generador.py`; acá el LLM se sustituye por un cliente falso
con `dependency_overrides`, así que estos tests tampoco necesitan credencial ni
red — solo Postgres.

El cliente falso **cita los fragmentos que recibió en el prompt** en vez de un
id fijo: los identificadores dependen de lo que la base asigne en cada corrida,
y un id escrito a mano haría que la regla 5 rechazara la cápsula por una razón
que no tiene nada que ver con lo que el test quiere medir.
"""

import json
import re
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient

from studify.api.routers.capsules import get_cliente_llm
from studify.db.models import (
    ConfiguracionContenido,
    DiagnosticoVark,
    DocumentoFuente,
    Estudiante,
    Fragmento,
    MicrocapsulaGenerada,
    ObjetivoAprendizaje,
)
from studify.main import app
from studify.vark.rules import aplicar_reglas
from studify.vark.scoring import PerfilVark
from tests.conftest import necesita_bd

pytestmark = necesita_bd

TEXTO_LARGO = (
    "La normalización es el proceso que organiza los atributos de una base de "
    "datos relacional para reducir la redundancia y evitar anomalías al "
    "insertar, actualizar o eliminar filas. Cada forma normal agrega una "
    "condición sobre la anterior, de modo que una tabla en tercera forma "
    "normal cumple también las dos primeras. Una dependencia parcial aparece "
    "cuando un atributo no clave depende solo de una parte de la clave "
    "primaria compuesta, y no de la clave completa. Mientras exista esa "
    "dependencia, la tabla no está en segunda forma normal y el mismo valor se "
    "repetirá en muchas filas. Al separar ese atributo en su propia tabla, "
    "cualquier corrección se hace una sola vez y queda reflejada en todas las "
    "consultas que la usan. El procedimiento habitual consiste en identificar "
    "primero la clave primaria completa, revisar después cada atributo no "
    "clave y preguntarse de qué parte de la clave depende realmente. Los "
    "atributos que dependan solo de una porción se trasladan a una tabla nueva "
    "junto con esa porción, que pasa a ser su clave. En la tabla original "
    "queda una clave foránea que apunta a la nueva, de modo que la información "
    "sigue siendo recuperable con una operación de reunión y no se pierde "
    "ningún dato en el proceso."
)


class ClienteObediente:
    """Modelo falso que se porta bien: responde en español y cita lo recibido."""

    def __init__(self, modelo: str = "modelo-de-prueba") -> None:
        self.modelo = modelo
        self.llamadas = 0

    def responder(self, mensajes) -> str:
        self.llamadas += 1
        ids = [int(n) for n in re.findall(r"id_fragmento: (\d+)", mensajes[1].contenido)]
        return json.dumps(
            {
                "titulo": "Segunda forma normal y dependencias parciales",
                "objetivo_aprendizaje": "Identificar y corregir dependencias parciales.",
                "activacion": "¿Por qué a veces hay que corregir el mismo dato en muchas filas?",
                "concepto_central": TEXTO_LARGO,
                "representacion_adaptativa": [
                    {"tipo": "parrafo", "cuerpo": "Separar el atributo dependiente."}
                ],
                "ejemplo": {
                    "tipo": "ejemplo_resuelto",
                    "cuerpo": "En matrículas, el nombre del ramo depende solo de id_ramo.",
                },
                "actividad": {
                    "tipo": "quiz_mc",
                    "pregunta": "¿Cuándo una tabla incumple la segunda forma normal?",
                    "alternativas": [
                        "Cuando un atributo no clave depende de parte de la clave",
                        "Cuando la tabla tiene más de cinco columnas",
                        "Cuando la clave primaria es un número entero",
                    ],
                    "indice_correcta": 0,
                    "retroalimentacion": "Debe depender de la clave completa.",
                },
                "fuentes": [{"id_fragmento": ids[0], "documento": "x", "pagina": 1}],
            },
            ensure_ascii=False,
        )


@pytest.fixture
def cliente_falso():
    """Sustituye el LLM y devuelve el doble para poder contar sus llamadas."""
    falso = ClienteObediente()
    app.dependency_overrides[get_cliente_llm] = lambda: falso
    yield falso
    app.dependency_overrides.pop(get_cliente_llm, None)


@pytest.fixture
def http():
    return TestClient(app)


def _estudiante_con_perfil(db, perfil: PerfilVark) -> Estudiante:
    """Estudiante con diagnóstico y configuración, como los deja la Fase 1."""
    estudiante = Estudiante(carrera="Ingeniería Informática (test capsulas)")
    db.add(estudiante)
    db.flush()

    diagnostico = DiagnosticoVark(
        id_estudiante=estudiante.id_estudiante,
        puntaje_v=int(perfil.v / 10),
        puntaje_a=int(perfil.a / 10),
        puntaje_r=int(perfil.r / 10),
        puntaje_k=int(perfil.k / 10),
        porcentaje_v=perfil.v,
        porcentaje_a=perfil.a,
        porcentaje_r=perfil.r,
        porcentaje_k=perfil.k,
    )
    db.add(diagnostico)
    db.flush()

    config = aplicar_reglas(perfil)
    db.add(
        ConfiguracionContenido(
            id_diagnostico=diagnostico.id_diagnostico,
            peso_texto=config.pesos.texto,
            peso_visual=config.pesos.visual,
            peso_narrativo=config.pesos.narrativo,
            peso_practico=config.pesos.practico,
            recursos_visuales=config.recursos_visuales,
            palabras_texto=config.palabras_texto,
            componentes_practicos=config.componentes_practicos,
            audio_activo=config.audio_activo,
            tono_narrativo=config.tono_narrativo,
            canales_activos=config.canales_activos,
        )
    )
    db.commit()
    return estudiante


@pytest.fixture
def escenario(db):
    """Un objetivo con material validado y un estudiante con perfil K."""
    objetivo = ObjetivoAprendizaje(
        codigo_objetivo="TEST-CAP-01",
        asignatura="Bases de Datos (test capsulas)",
        unidad="Unidad 3",
        tema="Segunda forma normal",
        descripcion="Reconocer dependencias parciales.",
        estado="activo",
    )
    db.add(objetivo)
    db.flush()

    documento = DocumentoFuente(
        titulo="Apunte de prueba (capsulas)",
        formato="pdf",
        hash_archivo="hash-de-prueba-capsulas",
        estado_curacion="validado",
    )
    db.add(documento)
    db.flush()

    db.add(
        Fragmento(
            id_documento=documento.id_documento,
            id_objetivo=objetivo.id_objetivo,
            numero_fragmento=1,
            tipo_fragmento="texto",
            contenido_texto=TEXTO_LARGO,
            pagina_inicio=12,
            pagina_fin=12,
            estado_validacion="validado",
        )
    )

    estudiante = _estudiante_con_perfil(
        db, PerfilVark(v=Decimal(0), a=Decimal(0), r=Decimal(0), k=Decimal(100))
    )
    db.commit()

    yield {"objetivo": objetivo, "documento": documento, "estudiante": estudiante}

    # Las cápsulas tienen FK RESTRICT contra el objetivo: se borran primero.
    db.query(MicrocapsulaGenerada).filter(
        MicrocapsulaGenerada.id_objetivo == objetivo.id_objetivo
    ).delete()
    db.commit()
    db.delete(documento)
    db.delete(objetivo)
    for est in db.query(Estudiante).filter(
        Estudiante.carrera == "Ingeniería Informática (test capsulas)"
    ):
        db.delete(est)
    db.commit()


def _pedir(http, escenario, **params):
    return http.post(
        "/api/capsulas",
        json={
            "id_estudiante": escenario["estudiante"].id_estudiante,
            "id_objetivo": escenario["objetivo"].id_objetivo,
        },
        params=params,
    )


# --- Lo que el endpoint rechaza ----------------------------------------------


def test_estudiante_inexistente_da_404(http, escenario, cliente_falso):
    respuesta = http.post(
        "/api/capsulas",
        json={"id_estudiante": 10**9, "id_objetivo": escenario["objetivo"].id_objetivo},
    )

    assert respuesta.status_code == 404
    assert cliente_falso.llamadas == 0


def test_objetivo_inexistente_da_404(http, escenario, cliente_falso):
    respuesta = http.post(
        "/api/capsulas",
        json={
            "id_estudiante": escenario["estudiante"].id_estudiante,
            "id_objetivo": 10**9,
        },
    )

    assert respuesta.status_code == 404


def test_estudiante_sin_diagnostico_da_422(http, db, escenario, cliente_falso):
    """Sin perfil no hay nada que adaptar; generar sería inventar un perfil."""
    huerfano = Estudiante(carrera="Ingeniería Informática (test capsulas)")
    db.add(huerfano)
    db.commit()

    respuesta = http.post(
        "/api/capsulas",
        json={
            "id_estudiante": huerfano.id_estudiante,
            "id_objetivo": escenario["objetivo"].id_objetivo,
        },
    )

    assert respuesta.status_code == 422
    assert "cuestionario" in respuesta.json()["detail"]
    assert cliente_falso.llamadas == 0


def test_objetivo_sin_material_validado_da_422(http, db, escenario, cliente_falso):
    """La barrera del cap. 12: sin curación no se genera nada."""
    vacio = ObjetivoAprendizaje(
        codigo_objetivo="TEST-CAP-VACIO",
        asignatura="Bases de Datos (test capsulas)",
        unidad="Unidad 4",
        tema="Sin material",
        estado="activo",
    )
    db.add(vacio)
    db.commit()

    respuesta = http.post(
        "/api/capsulas",
        json={
            "id_estudiante": escenario["estudiante"].id_estudiante,
            "id_objetivo": vacio.id_objetivo,
        },
    )

    db.delete(vacio)
    db.commit()

    assert respuesta.status_code == 422
    assert "sin material" in respuesta.json()["detail"]
    assert cliente_falso.llamadas == 0


# --- Generación ---------------------------------------------------------------


def test_genera_una_capsula_completa(http, escenario, cliente_falso):
    respuesta = _pedir(http, escenario)

    assert respuesta.status_code == 201, respuesta.text
    cuerpo = respuesta.json()
    assert cuerpo["origen"] == "generada"
    assert cuerpo["intentos"] == 1
    assert cuerpo["modelo_llm"] == "modelo-de-prueba"
    assert cuerpo["actividad"]["tipo"] == "quiz_mc"
    assert cuerpo["fuentes"], "la cápsula tiene que citar el material que la fundamentó"
    assert cliente_falso.llamadas == 1


def test_la_actividad_se_guarda_en_mini_quiz_json(http, db, escenario, cliente_falso):
    """La tabla 17.8 declara las dos columnas JSONB; se usan las dos."""
    id_capsula = _pedir(http, escenario).json()["id_capsula"]

    fila = db.get(MicrocapsulaGenerada, id_capsula)
    db.refresh(fila)

    assert fila.mini_quiz_json["tipo"] == "quiz_mc"
    assert "actividad" not in fila.contenido_json
    assert fila.contenido_json["titulo"].startswith("Segunda forma normal")


def test_la_capsula_queda_trazable_hasta_el_fragmento(http, db, escenario, cliente_falso):
    """La FK a `fragmento` es la trazabilidad nativa del cap. 13."""
    id_capsula = _pedir(http, escenario).json()["id_capsula"]

    fila = db.get(MicrocapsulaGenerada, id_capsula)
    assert fila.id_fragmento_fuente is not None
    assert fila.fragmento_fuente.id_objetivo == escenario["objetivo"].id_objetivo


# --- Caché y regeneración -----------------------------------------------------


def test_la_segunda_peticion_sale_del_cache_sin_llamar_al_modelo(
    http, escenario, cliente_falso
):
    primera = _pedir(http, escenario).json()
    segunda = _pedir(http, escenario).json()

    assert segunda["origen"] == "cache"
    assert segunda["id_capsula"] == primera["id_capsula"]
    assert cliente_falso.llamadas == 1


def test_regenerar_crea_una_version_nueva_y_conserva_la_anterior(
    http, escenario, cliente_falso
):
    """La decisión de la Fase 3: se versiona, no se sobrescribe."""
    primera = _pedir(http, escenario).json()
    segunda = _pedir(http, escenario, regenerar="true").json()

    assert segunda["origen"] == "generada"
    assert segunda["id_capsula"] != primera["id_capsula"]
    assert cliente_falso.llamadas == 2

    historial = http.get(
        "/api/capsulas", params={"id_objetivo": escenario["objetivo"].id_objetivo}
    ).json()
    assert {c["id_capsula"] for c in historial} >= {
        primera["id_capsula"],
        segunda["id_capsula"],
    }


def test_otro_estudiante_del_mismo_tramo_no_vuelve_a_pagar_la_generacion(
    http, db, escenario, cliente_falso
):
    """El caché compartido: se copia la cápsula, no se llama de nuevo al modelo.

    Se copia en una fila propia y no se comparte la del otro estudiante porque
    la tabla 17.8 vincula cada cápsula a un estudiante, y el A/B de la Fase 5
    necesita saber qué vio cada uno.
    """
    primera = _pedir(http, escenario).json()

    gemelo = _estudiante_con_perfil(
        db, PerfilVark(v=Decimal(0), a=Decimal(0), r=Decimal(0), k=Decimal(100))
    )
    respuesta = http.post(
        "/api/capsulas",
        json={
            "id_estudiante": gemelo.id_estudiante,
            "id_objetivo": escenario["objetivo"].id_objetivo,
        },
    )
    cuerpo = respuesta.json()

    assert respuesta.status_code == 201, respuesta.text
    assert cuerpo["origen"] == "cache_compartido"
    assert cuerpo["id_capsula"] != primera["id_capsula"]
    assert cuerpo["id_estudiante"] == gemelo.id_estudiante
    assert cuerpo["titulo"] == primera["titulo"]
    assert cliente_falso.llamadas == 1


def test_un_perfil_distinto_no_reutiliza_el_cache(http, db, escenario, cliente_falso):
    """Si compartiera caché, la adaptación VARK no existiría."""
    _pedir(http, escenario)

    visual = _estudiante_con_perfil(
        db, PerfilVark(v=Decimal(100), a=Decimal(0), r=Decimal(0), k=Decimal(0))
    )
    cuerpo = http.post(
        "/api/capsulas",
        json={
            "id_estudiante": visual.id_estudiante,
            "id_objetivo": escenario["objetivo"].id_objetivo,
        },
    ).json()

    assert cuerpo["origen"] == "generada"
    assert cliente_falso.llamadas == 2


def test_obtener_una_capsula_por_id(http, escenario, cliente_falso):
    id_capsula = _pedir(http, escenario).json()["id_capsula"]

    respuesta = http.get(f"/api/capsulas/{id_capsula}")

    assert respuesta.status_code == 200
    assert respuesta.json()["id_capsula"] == id_capsula


def test_capsula_inexistente_da_404(http):
    assert http.get("/api/capsulas/999999999").status_code == 404


# --- Sin credencial -----------------------------------------------------------


def test_sin_api_key_no_se_genera_pero_el_cache_sigue_sirviendo(
    http, escenario, cliente_falso
):
    """El 503 tiene que bloquear la generación, no la lectura de lo ya generado.

    Es exactamente el estado actual del proyecto (`LLM_API_KEY` vacío), así que
    conviene que la demo pueda seguir mostrando cápsulas ya generadas.
    """
    primera = _pedir(http, escenario).json()

    app.dependency_overrides[get_cliente_llm] = lambda: None

    cacheada = _pedir(http, escenario)
    assert cacheada.status_code == 201
    assert cacheada.json()["id_capsula"] == primera["id_capsula"]

    forzada = _pedir(http, escenario, regenerar="true")
    assert forzada.status_code == 503
    assert "LLM_API_KEY" in forzada.json()["detail"]
