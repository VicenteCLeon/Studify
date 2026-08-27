"""Panel de curación del docente por HTTP (Fase 4).

Lo que estos tests protegen no es la pantalla: es la barrera del cap. 12/13.
Un fragmento que entra por la web tiene que quedar **pendiente**, y solo puede
pasar a `validado` con un objetivo de aprendizaje asignado. Si esa regla se
saltara desde la interfaz, el retriever recibiría material sin curar y todo el
argumento de trazabilidad del proyecto se cae.

Requieren Postgres (se saltan solos si no está) y las dependencias opcionales de
ingesta (`pip install -e ".[ingest]"`).
"""

import re
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select

from studify.api.routers.capsules import get_cliente_llm
from studify.db.models import DocumentoFuente, Fragmento, ObjetivoAprendizaje
from studify.main import app
from tests.conftest import necesita_bd
from tests.test_tagger import ClienteEtiquetadorFalso, ClienteQueDevuelveBasura

pytestmark = necesita_bd

ASIGNATURA_PRUEBA = "Bases de Datos (test docente)"


@pytest.fixture
def http(http_docente) -> TestClient:
    """El panel exige sesión de docente; la fixture compartida ya la abrió.

    Que estos tests pasen por el login de verdad (y no por una cookie inyectada)
    es parte de lo que protegen: si el guardián de `/teacher/*` se rompiera o el
    login dejara de emitir una cookie válida, la suite completa del panel se
    caería en vez de seguir verde sobre una puerta que ya no cierra.
    """
    return http_docente


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


# --- Etiquetado asistido por LLM (tagger) --------------------------------------
#
# Cierra el pendiente n.º 3 de AVANCE.md §6. Lo que protegen estos tests no es
# que el modelo acierte —eso no se le puede exigir a un LLM—, es que la
# sugerencia nunca se convierte en una asignación real por sí sola: sigue
# haciendo falta el clic en «Validar», el mismo botón y el mismo endpoint que
# ya existían.


@pytest.fixture
def documento_sin_clasificar(db):
    """Documento con fragmentos pendientes y sin objetivo, sin pasar por PDF.

    Los tests de ingesta de este archivo ya cubren el camino completo desde un
    PDF real; el tagger no necesita eso —le basta con fragmentos en la base—,
    así que se arma directo para no depender de `pymupdf`.
    """
    doc = DocumentoFuente(
        titulo="Apunte sin clasificar",
        formato="pdf",
        asignatura=ASIGNATURA_PRUEBA,
        hash_archivo="hash-de-prueba-tagger-web",
        estado_curacion="pendiente",
    )
    db.add(doc)
    db.flush()
    for numero, texto in enumerate(
        [
            "La normalización reduce la redundancia de los datos almacenados.",
            "Una dependencia parcial depende solo de parte de la clave compuesta.",
        ],
        start=1,
    ):
        db.add(
            Fragmento(
                id_documento=doc.id_documento,
                numero_fragmento=numero,
                tipo_fragmento="texto",
                contenido_texto=texto,
                estado_validacion="pendiente",
            )
        )
    db.commit()
    yield doc
    db.delete(doc)
    db.commit()


@pytest.fixture
def sin_llm():
    app.dependency_overrides[get_cliente_llm] = lambda: None
    yield
    app.dependency_overrides.pop(get_cliente_llm, None)


@pytest.fixture
def llm_etiquetador():
    """Sugiere siempre el primer objetivo que se le pase por argumento."""

    def _instalar(**kwargs):
        falso = ClienteEtiquetadorFalso(**kwargs)
        app.dependency_overrides[get_cliente_llm] = lambda: falso
        return falso

    yield _instalar
    app.dependency_overrides.pop(get_cliente_llm, None)


def test_sin_llm_api_key_avisa_y_no_toca_nada(http, db, documento_sin_clasificar, sin_llm):
    respuesta = http.post(
        "/teacher/curation/tag", data={"id_documento": documento_sin_clasificar.id_documento}
    )

    assert respuesta.status_code == 200
    assert "alerta-error" in respuesta.text
    assert "LLM_API_KEY" in respuesta.text


def test_tag_no_asigna_objetivo_solo_lo_propone(
    http, db, objetivo, documento_sin_clasificar, llm_etiquetador
):
    """La invariante central, ahora verificada por HTTP: sigue sin decidir."""
    llm_etiquetador(id_objetivo=objetivo.id_objetivo)

    respuesta = http.post(
        "/teacher/curation/tag", data={"id_documento": documento_sin_clasificar.id_documento}
    )

    assert respuesta.status_code == 200
    assert respuesta.headers.get("HX-Trigger") == "fragmentos-actualizados"

    fragmentos = db.scalars(
        select(Fragmento)
        .where(Fragmento.id_documento == documento_sin_clasificar.id_documento)
    ).all()
    assert all(f.id_objetivo is None for f in fragmentos), "propone, no decide"
    assert all(f.estado_validacion == "pendiente" for f in fragmentos)


def test_tag_preselecciona_el_objetivo_sugerido_en_la_bandeja(
    http, db, objetivo, documento_sin_clasificar, llm_etiquetador
):
    llm_etiquetador(id_objetivo=objetivo.id_objetivo, etiqueta="Segunda forma normal")

    http.post(
        "/teacher/curation/tag", data={"id_documento": documento_sin_clasificar.id_documento}
    )
    bandeja = http.get(
        f"/teacher/curation/fragmentos?id_documento={documento_sin_clasificar.id_documento}"
    ).text

    # Preseleccionado en el <select>, no como valor fijo: sigue siendo un
    # `<option>` normal que el curador puede cambiar antes de validar.
    opcion = re.search(
        rf'<option value="{objetivo.id_objetivo}"[^>]*?(selected)?>', bandeja
    )
    assert opcion is not None and opcion.group(1) == "selected"
    assert "badge-primary" in bandeja
    assert "Segunda forma normal" in bandeja


def test_tag_resume_cuantos_fragmentos_sugirio(
    http, objetivo, documento_sin_clasificar, llm_etiquetador
):
    llm_etiquetador(id_objetivo=objetivo.id_objetivo)

    respuesta = http.post(
        "/teacher/curation/tag", data={"id_documento": documento_sin_clasificar.id_documento}
    )

    assert "2 de 2 fragmentos con objetivo sugerido" in respuesta.text


def test_tag_sin_candidatos_lo_dice_sin_romper(http, documento_sin_clasificar, llm_etiquetador):
    """Sin objetivos en el catálogo de esa asignatura, no hay nada que sugerir."""
    llm_etiquetador()

    respuesta = http.post(
        "/teacher/curation/tag", data={"id_documento": documento_sin_clasificar.id_documento}
    )

    assert respuesta.status_code == 200
    # "sin un objetivo claro" es el texto del caso "ok pero sin match"; acá el
    # motivo es otro (sin candidatos), así que corresponde "fallaron".
    assert "sin un objetivo claro" not in respuesta.text
    assert "fallaron" in respuesta.text


def test_tag_json_inservible_no_tumba_el_lote(http, db, documento_sin_clasificar):
    """Dos fragmentos, el modelo devuelve basura para ambos: se reporta, no revienta."""
    app.dependency_overrides[get_cliente_llm] = lambda: ClienteQueDevuelveBasura()
    try:
        respuesta = http.post(
            "/teacher/curation/tag", data={"id_documento": documento_sin_clasificar.id_documento}
        )
    finally:
        app.dependency_overrides.pop(get_cliente_llm, None)

    assert respuesta.status_code == 200
    assert "fallaron" in respuesta.text


def test_tag_sin_fragmentos_pendientes_lo_dice(http, objetivo, llm_etiquetador):
    llm_etiquetador(id_objetivo=objetivo.id_objetivo)

    respuesta = http.post("/teacher/curation/tag", data={"id_documento": 10**9})

    assert "No hay fragmentos pendientes" in respuesta.text
