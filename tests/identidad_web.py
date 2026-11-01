"""Preparación de cuentas verificadas para probar las vistas sin llamar a Google.

El protocolo OAuth se prueba aparte en test_google_login. Este helper prepara
una identidad y usa el formulario y el POST reales; no desactiva ningún guardián.
"""

import re
from uuid import uuid4

from studify.db.models import Estudiante
from studify.db.session import SessionLocal
from studify.web import sesion


def enviar_vark(cliente, *, data, **kwargs):
    if not cliente.cookies.get(sesion.COOKIE_ESTUDIANTE):
        with SessionLocal() as db:
            estudiante = Estudiante(google_sub="vista-test-" + uuid4().hex, origen_registro="nuevo")
            db.add(estudiante)
            db.commit()
            cliente.cookies.set(
                sesion.COOKIE_ESTUDIANTE,
                sesion.valor_cookie(estudiante.id_estudiante, estudiante.fecha_registro),
                domain="testserver.local",
            )
    formulario = cliente.get("/student/vark?modo=actualizar")
    token = re.search(r'name="token_sesion" value="([^"]+)"', formulario.text).group(1)
    return cliente.post("/student/vark", data=data | {"token_sesion": token}, **kwargs)


def perfil_local_anterior(cliente):
    """Registro histórico sin Google, para probar su vinculación explícita."""
    from studify.api.routers.diagnostics import crear_diagnostico
    from studify.api.schemas import DiagnosticoIn, EstudianteIn, RespuestaItemIn
    from studify.web import consentimiento

    with SessionLocal() as db:
        resultado = crear_diagnostico(DiagnosticoIn(
            estudiante=EstudianteIn(),
            respuestas=[RespuestaItemIn(num_pregunta=1, alternativas=["d"])],
        ), db)
        consentimiento.registrar(db, resultado.id_estudiante)
        estudiante = db.get(Estudiante, resultado.id_estudiante)
        cliente.cookies.set(
            sesion.COOKIE_ESTUDIANTE,
            sesion.valor_cookie(estudiante.id_estudiante, estudiante.fecha_registro),
            domain="testserver.local",
        )
        return estudiante.id_estudiante
