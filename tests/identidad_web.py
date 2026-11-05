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


def _sesion(cliente, estudiante):
    cliente.cookies.set(
        sesion.COOKIE_ESTUDIANTE,
        sesion.valor_cookie(estudiante.id_estudiante, estudiante.fecha_registro),
        domain="testserver.local",
    )


def control_google_sin_registro(cliente):
    """Cuenta control recién creada por Google, antes de completar su registro.

    Es el estado que deja `google_login.callback` con `rol=control`: la sesión
    abierta y el formulario de `/student/control` pendiente (datos opcionales y
    aceptación). Desde el punto 2a es la única forma de entrar al grupo control.
    """
    with SessionLocal() as db:
        estudiante = Estudiante(
            rol="control", google_sub="control-test-" + uuid4().hex, origen_registro="nuevo",
        )
        db.add(estudiante)
        db.commit()
        _sesion(cliente, estudiante)
        return estudiante.id_estudiante


def control_local_anterior(cliente):
    """Registro de control local hecho antes del punto 2a, sin Google.

    Ya no se pueden crear, pero los que existen siguen entrando con su cookie y
    pueden vincular una cuenta Google.
    """
    from studify.web import consentimiento

    with SessionLocal() as db:
        estudiante = Estudiante(rol="control", origen_registro="nuevo")
        db.add(estudiante)
        db.commit()
        consentimiento.registrar(db, estudiante.id_estudiante)
        _sesion(cliente, estudiante)
        return estudiante.id_estudiante
