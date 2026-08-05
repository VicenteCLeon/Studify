"""Smoke test de la Semana 0: la app levanta y /health responde.

No requiere Postgres corriendo: /health reporta la base como inalcanzable
en vez de fallar, para poder distinguir "la app no arranca" de "falta la BD".
"""

from fastapi.testclient import TestClient

from studify.main import app

client = TestClient(app)


def test_health_responde():
    resp = client.get("/health")
    assert resp.status_code == 200

    body = resp.json()
    assert body["status"] in {"ok", "degraded"}
    assert "database" in body
    assert "llm" in body


def test_openapi_se_genera():
    resp = client.get("/openapi.json")
    assert resp.status_code == 200
    assert resp.json()["info"]["title"] == "Studify"
