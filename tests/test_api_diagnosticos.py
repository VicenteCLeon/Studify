"""Tests de POST /api/diagnosticos y GET /api/diagnosticos/{id}.

Los tests de validación del contrato corren siempre (no tocan la base). Los que
persisten se saltan si Postgres no está disponible, para que `pytest` siga en
verde en una máquina recién clonada — mismo criterio que `test_health.py`.
"""

from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from studify.db.session import engine
from studify.main import app

client = TestClient(app)


def _hay_base_de_datos() -> bool:
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return True
    except Exception:
        return False


necesita_bd = pytest.mark.skipif(
    not _hay_base_de_datos(), reason="requiere Postgres levantado"
)


def respuestas_kinestesicas() -> list[dict]:
    """16 ítems marcando siempre la alternativa 'd' (canal K)."""
    return [{"num_pregunta": n, "alternativas": ["d"]} for n in range(1, 17)]


# --- Contrato de entrada (no tocan la base) ---------------------------------


def test_rechaza_sin_estudiante_ni_id():
    resp = client.post("/api/diagnosticos", json={"respuestas": respuestas_kinestesicas()})
    assert resp.status_code == 422
    assert "id_estudiante" in resp.text


def test_rechaza_estudiante_y_id_a_la_vez():
    resp = client.post(
        "/api/diagnosticos",
        json={
            "id_estudiante": 1,
            "estudiante": {"carrera": "Ingeniería en Informática"},
            "respuestas": respuestas_kinestesicas(),
        },
    )
    assert resp.status_code == 422
    assert "excluyentes" in resp.text


def test_rechaza_item_fuera_de_rango():
    resp = client.post(
        "/api/diagnosticos",
        json={
            "estudiante": {},
            "respuestas": [{"num_pregunta": 17, "alternativas": ["a"]}],
        },
    )
    assert resp.status_code == 422


def test_rechaza_alternativa_inexistente():
    resp = client.post(
        "/api/diagnosticos",
        json={
            "estudiante": {},
            "respuestas": [{"num_pregunta": 1, "alternativas": ["e"]}],
        },
    )
    assert resp.status_code == 422


def test_rechaza_item_repetido():
    """Las selecciones múltiples van juntas en 'alternativas', no en dos entradas."""
    resp = client.post(
        "/api/diagnosticos",
        json={
            "estudiante": {},
            "respuestas": [
                {"num_pregunta": 1, "alternativas": ["a"]},
                {"num_pregunta": 1, "alternativas": ["b"]},
            ],
        },
    )
    assert resp.status_code == 422
    assert "más de una vez" in resp.text


def test_rechaza_alternativas_repetidas_en_un_item():
    resp = client.post(
        "/api/diagnosticos",
        json={
            "estudiante": {},
            "respuestas": [{"num_pregunta": 1, "alternativas": ["a", "a"]}],
        },
    )
    assert resp.status_code == 422
    assert "repetidas" in resp.text


def test_rechaza_cuestionario_todo_en_blanco():
    """Sin ninguna selección el vector porcentual es 0/0 (cap. 10)."""
    resp = client.post(
        "/api/diagnosticos",
        json={
            "estudiante": {},
            "respuestas": [{"num_pregunta": n, "alternativas": []} for n in range(1, 17)],
        },
    )
    assert resp.status_code == 422
    assert "ninguna selección" in resp.text


# --- Flujo completo contra la base ------------------------------------------


@necesita_bd
def test_perfil_kinestesico_puro_devuelve_configuracion_completa():
    resp = client.post(
        "/api/diagnosticos",
        json={
            "estudiante": {
                "rango_etario": "18 - 22 años",
                "genero": "No Binario / otra identidad",
                "carrera": "Ingeniería en Informática",
            },
            "respuestas": respuestas_kinestesicas(),
        },
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()

    assert body["puntajes"] == {"v": 0, "a": 0, "r": 0, "k": 16, "total": 16}
    assert Decimal(body["perfil"]["k"]) == Decimal("100.00")

    j = body["jerarquia"]
    assert j["canal_primario"] == "K"
    assert j["es_unimodal"] is True
    assert j["etiqueta"] == "K"

    # Tabla 11.1 fila 5: p_K ≥ 40% exige los tres componentes prácticos.
    config = body["configuracion"]
    assert config["componentes_practicos"] == 3
    assert config["tono_narrativo"] == "practico"
    assert {"ejemplo_resuelto", "paso_a_paso", "actividad_aplicada"} <= set(
        config["directivas"]
    )
    assert 150 <= config["palabras_texto"] <= 300
    assert config["audio_activo"] is False
    assert config["id_config"] is not None


@necesita_bd
def test_genero_largo_cabe_en_la_columna():
    """La tabla 17.1 declaraba VARCHAR(20) y esta opción tiene 27 caracteres."""
    resp = client.post(
        "/api/diagnosticos",
        json={
            "estudiante": {"genero": "No Binario / otra identidad"},
            "respuestas": respuestas_kinestesicas(),
        },
    )
    assert resp.status_code == 201, resp.text


@necesita_bd
def test_items_en_blanco_y_seleccion_multiple():
    """Ambas cosas son parte del diseño del instrumento (cap. 10)."""
    resp = client.post(
        "/api/diagnosticos",
        json={
            "estudiante": {},
            "respuestas": [
                {"num_pregunta": 1, "alternativas": ["a", "d"]},  # múltiple
                {"num_pregunta": 2, "alternativas": []},  # en blanco
                {"num_pregunta": 3, "alternativas": ["b"]},
            ],
        },
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["puntajes"]["total"] == 3
    assert body["puntajes"]["v"] == 1
    assert body["puntajes"]["a"] == 1
    assert body["puntajes"]["k"] == 1


@necesita_bd
def test_los_porcentajes_devueltos_suman_100():
    """El CHECK de la tabla lo exige; un fallo acá sería un error de redondeo."""
    resp = client.post(
        "/api/diagnosticos",
        json={
            "estudiante": {},
            # Tres canales → 33,33/33,33/33,34, el caso incómodo.
            "respuestas": [
                {"num_pregunta": 1, "alternativas": ["a"]},
                {"num_pregunta": 2, "alternativas": ["b"]},
                {"num_pregunta": 3, "alternativas": ["c"]},
            ],
        },
    )
    assert resp.status_code == 201, resp.text
    p = resp.json()["perfil"]
    total = Decimal(p["v"]) + Decimal(p["a"]) + Decimal(p["r"]) + Decimal(p["k"])
    assert total == Decimal("100")


@necesita_bd
def test_diagnostico_sobre_estudiante_existente():
    primero = client.post(
        "/api/diagnosticos",
        json={"estudiante": {"carrera": "Derecho"}, "respuestas": respuestas_kinestesicas()},
    )
    assert primero.status_code == 201
    id_estudiante = primero.json()["id_estudiante"]

    segundo = client.post(
        "/api/diagnosticos",
        json={
            "id_estudiante": id_estudiante,
            "respuestas": [{"num_pregunta": n, "alternativas": ["c"]} for n in range(1, 17)],
        },
    )
    assert segundo.status_code == 201, segundo.text
    assert segundo.json()["id_estudiante"] == id_estudiante
    assert segundo.json()["jerarquia"]["canal_primario"] == "R"


@necesita_bd
def test_estudiante_inexistente_da_404():
    resp = client.post(
        "/api/diagnosticos",
        json={"id_estudiante": 99_999_999, "respuestas": respuestas_kinestesicas()},
    )
    assert resp.status_code == 404


@necesita_bd
def test_get_devuelve_el_mismo_perfil_que_el_post():
    creado = client.post(
        "/api/diagnosticos",
        json={"estudiante": {}, "respuestas": respuestas_kinestesicas()},
    )
    assert creado.status_code == 201
    id_diagnostico = creado.json()["id_diagnostico"]

    leido = client.get(f"/api/diagnosticos/{id_diagnostico}")
    assert leido.status_code == 200
    assert leido.json()["perfil"] == creado.json()["perfil"]
    assert leido.json()["jerarquia"] == creado.json()["jerarquia"]
    assert leido.json()["configuracion"] == creado.json()["configuracion"]


@necesita_bd
def test_get_de_diagnostico_inexistente_da_404():
    assert client.get("/api/diagnosticos/99999999").status_code == 404
