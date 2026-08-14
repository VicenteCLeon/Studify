"""Panel de curación del docente por HTTP (Fase 4).

Lo que estos tests protegen no es la pantalla: es la barrera del cap. 12/13.
Un fragmento que entra por la web tiene que quedar **pendiente**, y solo puede
pasar a `validado` con un objetivo de aprendizaje asignado. Si esa regla se
saltara desde la interfaz, el retriever recibiría material sin curar y todo el
argumento de trazabilidad del proyecto se cae.

Requieren Postgres (se saltan solos si no está) y las dependencias opcionales de
ingesta (`pip install -e ".[ingest]"`).
"""

from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select

from studify.db.models import DocumentoFuente, Fragmento, ObjetivoAprendizaje
from studify.main import app
from tests.conftest import necesita_bd

pytestmark = necesita_bd

ASIGNATURA_PRUEBA = "Bases de Datos (test docente)"


@pytest.fixture
def http() -> TestClient:
    return TestClient(app)


@pytest.fixture
def pdf_de_prueba(tmp_path) -> Path:
    """Un apunte real de dos secciones, no un archivo simulado."""
    pymupdf = pytest.importorskip("pymupdf")

    ruta = tmp_path / "apunte_docente.pdf"
    doc = pymupdf.open()
    for titulo, cuerpo in [
        (
            "Dependencias parciales",
            "Una dependencia parcial aparece cuando un atributo no clave "
            "depende solo de una parte de la clave primaria compuesta. " * 8,
        ),
        (
            "Segunda forma normal",
            "Una tabla esta en segunda forma normal cuando no conserva "
            "ninguna dependencia parcial respecto de su clave. " * 8,
        ),
    ]:
        pagina = doc.new_page()
        pagina.insert_text((72, 90), titulo, fontsize=18)
        pagina.insert_textbox((72, 120, 520, 700), cuerpo, fontsize=11)
    doc.save(ruta)
    doc.close()
    return ruta


@pytest.fixture
def objetivo(db):
    fila = ObjetivoAprendizaje(
        codigo_objetivo="TEST-DOC-01",
        asignatura=ASIGNATURA_PRUEBA,
        unidad="Unidad 3",
        tema="Segunda forma normal",
        estado="activo",
    )
    db.add(fila)
    db.commit()
    yield fila
    db.delete(fila)
    db.commit()


@pytest.fixture
def limpiar_documentos(db):
    creados: list[int] = []
    yield creados
    for id_doc in creados:
        doc = db.get(DocumentoFuente, id_doc)
        if doc is not None:
            db.delete(doc)
    db.commit()


def _subir(http, db, ruta: Path, limpiar_documentos) -> list[Fragmento]:
    with ruta.open("rb") as fh:
        respuesta = http.post(
            "/teacher/curation/upload",
            files={"file": (ruta.name, fh, "application/pdf")},
            data={"asignatura": ASIGNATURA_PRUEBA},
        )
    assert respuesta.status_code == 200, respuesta.text

    documento = db.scalars(
        select(DocumentoFuente).order_by(DocumentoFuente.id_documento.desc()).limit(1)
    ).one()
    limpiar_documentos.append(documento.id_documento)
    fragmentos = db.scalars(
        select(Fragmento)
        .where(Fragmento.id_documento == documento.id_documento)
        .order_by(Fragmento.numero_fragmento)
    ).all()
    return respuesta, documento, fragmentos


def test_la_ingesta_deja_todo_pendiente_de_curacion(
    http, db, pdf_de_prueba, almacen_temporal, limpiar_documentos
):
    """La invariante del cap. 12: nada entra habilitado."""
    respuesta, documento, fragmentos = _subir(
        http, db, pdf_de_prueba, limpiar_documentos
    )

    assert "quedó ingerido" in respuesta.text
    assert "pendientes de revisión" in respuesta.text
    # La bandeja se recarga sola en vez de pedir un refresco manual.
    assert respuesta.headers.get("HX-Trigger") == "fragmentos-actualizados"

    assert documento.asignatura == ASIGNATURA_PRUEBA
    assert documento.estado_curacion == "pendiente"
    assert len(fragmentos) > 0
    assert {f.estado_validacion for f in fragmentos} == {"pendiente"}
    assert all(f.pagina_inicio is not None for f in fragmentos), "falta trazabilidad"


def test_el_mismo_archivo_con_otro_nombre_se_rechaza(
    http, db, pdf_de_prueba, almacen_temporal, limpiar_documentos, tmp_path
):
    """La deduplicación es por contenido (SHA-256), no por nombre."""
    _subir(http, db, pdf_de_prueba, limpiar_documentos)

    copia = tmp_path / "otro_nombre.pdf"
    copia.write_bytes(pdf_de_prueba.read_bytes())
    with copia.open("rb") as fh:
        respuesta = http.post(
            "/teacher/curation/upload",
            files={"file": (copia.name, fh, "application/pdf")},
        )

    assert respuesta.status_code == 200
    assert "alerta-error" in respuesta.text
    assert "no lo duplica" in respuesta.text


def test_un_formato_no_soportado_se_explica(http):
    respuesta = http.post(
        "/teacher/curation/upload",
        files={"file": ("apuntes.txt", b"texto plano", "text/plain")},
    )
    assert respuesta.status_code == 200
    assert "alerta-error" in respuesta.text
    assert ".pdf" in respuesta.text


def test_no_se_puede_validar_sin_objetivo_asignado(
    http, db, pdf_de_prueba, almacen_temporal, limpiar_documentos
):
    """El fallo silencioso que la Fase 2 bloqueó, ahora también desde la UI.

    Un fragmento validado con `id_objetivo = NULL` queda inalcanzable para
    siempre: aprobado, sin error visible y sin llegar nunca a una cápsula.
    """
    _, _, fragmentos = _subir(http, db, pdf_de_prueba, limpiar_documentos)
    objetivo_del_fragmento = fragmentos[0]

    respuesta = http.post(
        f"/teacher/curation/{objetivo_del_fragmento.id_fragmento}/approve",
        data={"id_objetivo": ""},
    )

    assert respuesta.status_code == 200
    assert "alerta-error" in respuesta.text
    assert "objetivo de aprendizaje" in respuesta.text

    db.refresh(objetivo_del_fragmento)
    assert objetivo_del_fragmento.estado_validacion == "pendiente"


def test_validar_con_objetivo_habilita_el_fragmento(
    http, db, objetivo, pdf_de_prueba, almacen_temporal, limpiar_documentos
):
    _, documento, fragmentos = _subir(http, db, pdf_de_prueba, limpiar_documentos)
    fragmento = fragmentos[0]

    respuesta = http.post(
        f"/teacher/curation/{fragmento.id_fragmento}/approve",
        data={"id_objetivo": str(objetivo.id_objetivo)},
    )

    assert respuesta.status_code == 200
    assert "badge-success" in respuesta.text
    assert "alerta-error" not in respuesta.text

    db.refresh(fragmento)
    db.refresh(documento)
    assert fragmento.estado_validacion == "validado"
    assert fragmento.id_objetivo == objetivo.id_objetivo
    # Validar un fragmento promueve el documento: si no, el panel mostraría
    # trabajo terminado como si estuviera por hacer.
    assert documento.estado_curacion == "validado"


def test_descartar_no_borra_el_fragmento(
    http, db, pdf_de_prueba, almacen_temporal, limpiar_documentos
):
    """El cap. 12 exige trazabilidad del proceso: qué se descartó también cuenta."""
    _, _, fragmentos = _subir(http, db, pdf_de_prueba, limpiar_documentos)
    fragmento = fragmentos[0]

    respuesta = http.post(f"/teacher/curation/{fragmento.id_fragmento}/reject")

    assert "badge-danger" in respuesta.text
    db.refresh(fragmento)
    assert fragmento.estado_validacion == "descartado"
    assert db.get(Fragmento, fragmento.id_fragmento) is not None


def test_la_bandeja_muestra_los_fragmentos_reales(
    http, db, objetivo, pdf_de_prueba, almacen_temporal, limpiar_documentos
):
    _, documento, fragmentos = _subir(http, db, pdf_de_prueba, limpiar_documentos)

    html = http.get(f"/teacher/curation?id_documento={documento.id_documento}").text

    assert "apunte_docente" in html
    assert f'id="fragment-{fragmentos[0].id_fragmento}"' in html
    # El selector de objetivo va en la misma fila que el botón de validar.
    assert "TEST-DOC-01" in html
    assert 'name="id_objetivo"' in html

    # Tras validar, el fragmento sale de la bandeja de pendientes.
    http.post(
        f"/teacher/curation/{fragmentos[0].id_fragmento}/approve",
        data={"id_objetivo": str(objetivo.id_objetivo)},
    )
    bandeja = http.get(
        f"/teacher/curation/fragmentos?id_documento={documento.id_documento}"
    ).text
    assert f'id="fragment-{fragmentos[0].id_fragmento}"' not in bandeja


# --- Alta de objetivos desde el panel ----------------------------------------
#
# Antes el catálogo solo se cargaba con `scripts/cargar_objetivos.py`, y sin al
# menos un objetivo el docente no puede validar nada: agregar un tema obligaba a
# abrir una terminal. El script sigue siendo la vía para sembrar un plan de
# estudios completo; el formulario cubre el caso de agregar uno.


@pytest.fixture
def limpiar_objetivos(db):
    codigos: list[str] = []
    yield codigos
    for codigo in codigos:
        fila = db.scalar(
            select(ObjetivoAprendizaje).where(
                ObjetivoAprendizaje.codigo_objetivo == codigo
            )
        )
        if fila is not None:
            db.delete(fila)
    db.commit()


def test_se_crea_un_objetivo_desde_el_panel(http, db, limpiar_objetivos):
    limpiar_objetivos.append("TEST-WEB-01")

    respuesta = http.post(
        "/teacher/curation/objetivos",
        data={
            "codigo_objetivo": "TEST-WEB-01",
            "asignatura": ASIGNATURA_PRUEBA,
            "unidad": "Unidad 4",
            "tema": "Tercera forma normal",
            "descripcion": "Eliminar dependencias transitivas.",
            "nivel_taxonomico": "aplicar",
        },
    )

    assert respuesta.status_code == 200
    fila = db.scalar(
        select(ObjetivoAprendizaje).where(
            ObjetivoAprendizaje.codigo_objetivo == "TEST-WEB-01"
        )
    )
    assert fila is not None
    assert fila.tema == "Tercera forma normal"
    assert fila.estado == "activo"


def test_el_objetivo_recien_creado_queda_disponible_para_validar(
    http, db, limpiar_objetivos
):
    """Es el punto del cambio: sirve para curar sin pasar por la consola."""
    limpiar_objetivos.append("TEST-WEB-02")
    http.post(
        "/teacher/curation/objetivos",
        data={
            "codigo_objetivo": "TEST-WEB-02",
            "asignatura": ASIGNATURA_PRUEBA,
            "unidad": "Unidad 4",
            "tema": "Dependencias transitivas",
            "descripcion": "",
            "nivel_taxonomico": "",
        },
    )

    # El selector de la bandeja lo tiene que ofrecer sin reiniciar nada.
    assert "TEST-WEB-02" in http.get("/teacher/curation").text


def test_un_codigo_repetido_se_rechaza_con_el_motivo(http, db, limpiar_objetivos):
    """`codigo_objetivo` es la clave natural del catálogo."""
    limpiar_objetivos.append("TEST-WEB-03")
    datos = {
        "codigo_objetivo": "TEST-WEB-03",
        "asignatura": ASIGNATURA_PRUEBA,
        "unidad": "Unidad 4",
        "tema": "Un tema",
        "descripcion": "",
        "nivel_taxonomico": "",
    }
    http.post("/teacher/curation/objetivos", data=datos)

    repetido = http.post("/teacher/curation/objetivos", data={**datos, "tema": "Otro"})

    assert "ya existe un objetivo" in repetido.text
    assert (
        db.scalar(
            select(func.count())
            .select_from(ObjetivoAprendizaje)
            .where(ObjetivoAprendizaje.codigo_objetivo == "TEST-WEB-03")
        )
        == 1
    )


def test_un_campo_demasiado_largo_se_explica_en_espanol(http):
    """La pantalla es del docente; los mensajes de Pydantic vienen en inglés."""
    respuesta = http.post(
        "/teacher/curation/objetivos",
        data={
            "codigo_objetivo": "X" * 31,  # el máximo de la tabla 17.5 es 30
            "asignatura": ASIGNATURA_PRUEBA,
            "unidad": "U",
            "tema": "T",
            "descripcion": "",
            "nivel_taxonomico": "",
        },
    )

    assert "supera el máximo de 30 caracteres" in respuesta.text
    assert "String should have at most" not in respuesta.text
