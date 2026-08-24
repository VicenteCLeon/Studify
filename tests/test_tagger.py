"""Etiquetado asistido por LLM de fragmentos pendientes (cap. 12, Fase 2).

Cierra el pendiente n.º 3 de AVANCE.md §6. La invariante que protegen estos
tests no es "el modelo acierta el objetivo" —eso no se puede exigir de un
LLM—, es que **nunca decide por su cuenta**: pase lo que pase en la respuesta
del modelo, `Fragmento.id_objetivo` y `estado_validacion` no se tocan. Eso
sigue siendo obra exclusiva de `knowledge.curation`, disparada por una persona.
"""

import json

import pytest
from sqlalchemy import select

from studify.db.models import DocumentoFuente, Fragmento, ObjetivoAprendizaje
from studify.knowledge import tagger
from tests.conftest import necesita_bd

pytestmark = necesita_bd

ASIGNATURA_PRUEBA = "Bases de Datos (test tagger)"
OTRA_ASIGNATURA = "Cálculo (test tagger)"


class ClienteEtiquetadorFalso:
    """Modelo falso: propone lo que se le indique, sin red ni costo."""

    def __init__(
        self, id_objetivo=None, etiqueta="Segunda forma normal", motivo="Coincide con el tema."
    ):
        self.modelo = "modelo-de-prueba"
        self.llamadas = 0
        self._id_objetivo = id_objetivo
        self._etiqueta = etiqueta
        self._motivo = motivo

    def responder(self, mensajes) -> str:
        self.llamadas += 1
        return json.dumps(
            {
                "id_objetivo": self._id_objetivo,
                "etiqueta_tematica": self._etiqueta,
                "motivo": self._motivo,
            },
            ensure_ascii=False,
        )


class ClienteQueDevuelveBasura:
    """Simula una respuesta que no es JSON recuperable."""

    modelo = "modelo-de-prueba"

    def responder(self, mensajes) -> str:
        return "esto no es JSON de ninguna forma"


@pytest.fixture
def objetivo(db):
    obj = ObjetivoAprendizaje(
        codigo_objetivo="TEST-TAG-01",
        asignatura=ASIGNATURA_PRUEBA,
        unidad="Unidad 3",
        tema="Segunda forma normal",
        descripcion="Reconocer y eliminar dependencias parciales.",
        estado="activo",
    )
    db.add(obj)
    db.commit()
    yield obj
    db.delete(obj)
    db.commit()


@pytest.fixture
def otro_objetivo(db):
    """Activo, pero de otra asignatura: no debe aparecer como candidato."""
    obj = ObjetivoAprendizaje(
        codigo_objetivo="TEST-TAG-02",
        asignatura=OTRA_ASIGNATURA,
        unidad="Unidad 1",
        tema="Límites",
        estado="activo",
    )
    db.add(obj)
    db.commit()
    yield obj
    db.delete(obj)
    db.commit()


@pytest.fixture
def documento(db):
    doc = DocumentoFuente(
        titulo="Apunte de prueba (tagger)",
        formato="pdf",
        asignatura=ASIGNATURA_PRUEBA,
        hash_archivo="hash-de-prueba-tagger",
        estado_curacion="pendiente",
    )
    db.add(doc)
    db.flush()

    for numero, texto in enumerate(
        [
            "La normalización reduce la redundancia de los datos almacenados.",
            "Una dependencia parcial depende solo de parte de la clave compuesta.",
            "La tercera forma normal elimina las dependencias transitivas.",
        ],
        start=1,
    ):
        db.add(
            Fragmento(
                id_documento=doc.id_documento,
                numero_fragmento=numero,
                tipo_fragmento="texto",
                contenido_texto=texto,
                pagina_inicio=numero,
                pagina_fin=numero,
                estado_validacion="pendiente",
            )
        )
    db.commit()
    yield doc
    db.delete(doc)
    db.commit()


def _fragmentos(db, documento) -> list[Fragmento]:
    return list(
        db.scalars(
            select(Fragmento)
            .where(Fragmento.id_documento == documento.id_documento)
            .order_by(Fragmento.numero_fragmento)
        ).all()
    )


# --- etiquetar_fragmento: nunca decide -----------------------------------------


def test_la_sugerencia_no_asigna_el_objetivo(db, documento, objetivo):
    """La invariante central del módulo: proponer no es escribir la FK."""
    fragmento = _fragmentos(db, documento)[0]
    falso = ClienteEtiquetadorFalso(id_objetivo=objetivo.id_objetivo)

    sugerencia = tagger.etiquetar_fragmento(db, fragmento.id_fragmento, cliente=falso)

    assert sugerencia.ok
    assert sugerencia.id_objetivo == objetivo.id_objetivo
    db.refresh(fragmento)
    assert fragmento.id_objetivo is None, "seguir sin asignar es el punto del diseño"
    assert fragmento.estado_validacion == "pendiente"


def test_la_sugerencia_queda_guardada_en_metadatos(db, documento, objetivo):
    fragmento = _fragmentos(db, documento)[0]
    falso = ClienteEtiquetadorFalso(
        id_objetivo=objetivo.id_objetivo,
        etiqueta="Dependencias parciales",
        motivo="Trata justo eso.",
    )

    tagger.etiquetar_fragmento(db, fragmento.id_fragmento, cliente=falso)

    db.refresh(fragmento)
    guardado = fragmento.metadatos_json["sugerencia_llm"]
    assert guardado["id_objetivo"] == objetivo.id_objetivo
    assert guardado["codigo_objetivo"] == objetivo.codigo_objetivo
    assert guardado["etiqueta_tematica"] == "Dependencias parciales"
    assert guardado["motivo"] == "Trata justo eso."
    assert guardado["modelo"] == "modelo-de-prueba"


def test_un_id_objetivo_inventado_se_descarta_sin_tumbar_la_etiqueta(db, documento, objetivo):
    """Mismo riesgo que la regla 5 del validador de cápsulas, aplicado al catálogo."""
    fragmento = _fragmentos(db, documento)[0]
    falso = ClienteEtiquetadorFalso(id_objetivo=999_999, etiqueta="Tema fuera de catálogo")

    sugerencia = tagger.etiquetar_fragmento(db, fragmento.id_fragmento, cliente=falso)

    assert sugerencia.ok, "un id inventado no es un error del proceso, se descarta y sigue"
    assert sugerencia.id_objetivo is None
    assert sugerencia.codigo_objetivo is None
    assert sugerencia.etiqueta_tematica == "Tema fuera de catálogo"


def test_sin_candidatos_no_llama_al_modelo(db, documento):
    """Sin objetivos activos para la asignatura, ni vale la pena pagar la llamada."""
    fragmento = _fragmentos(db, documento)[0]
    falso = ClienteEtiquetadorFalso()

    sugerencia = tagger.etiquetar_fragmento(db, fragmento.id_fragmento, cliente=falso)

    assert not sugerencia.ok
    assert "objetivos" in sugerencia.error
    assert falso.llamadas == 0


def test_json_inservible_se_reporta_como_error_de_la_sugerencia(db, documento, objetivo):
    fragmento = _fragmentos(db, documento)[0]

    sugerencia = tagger.etiquetar_fragmento(
        db, fragmento.id_fragmento, cliente=ClienteQueDevuelveBasura()
    )

    assert not sugerencia.ok
    assert "JSON" in sugerencia.error
    db.refresh(fragmento)
    metadatos = fragmento.metadatos_json or {}
    assert "sugerencia_llm" not in metadatos


def test_fragmento_inexistente_lanza(db):
    with pytest.raises(tagger.ErrorEtiquetado, match="no existe"):
        tagger.etiquetar_fragmento(db, 10**9, cliente=ClienteEtiquetadorFalso())


def test_fragmento_sin_texto_lanza(db, documento, objetivo):
    fragmento = _fragmentos(db, documento)[0]
    fragmento.contenido_texto = "   "
    db.commit()

    with pytest.raises(tagger.ErrorEtiquetado, match="texto"):
        tagger.etiquetar_fragmento(db, fragmento.id_fragmento, cliente=ClienteEtiquetadorFalso())


def test_un_objetivo_de_otra_asignatura_no_es_candidato_aunque_este_activo(
    db, documento, objetivo, otro_objetivo
):
    """`documento.asignatura` acota el catálogo: un objetivo activo de otro ramo
    no debe poder proponerse, aunque el modelo lo "elija" por su cuenta —se
    trata igual que un id inventado, porque para este documento lo es."""
    fragmento = _fragmentos(db, documento)[0]
    falso = ClienteEtiquetadorFalso(id_objetivo=otro_objetivo.id_objetivo)

    sugerencia = tagger.etiquetar_fragmento(db, fragmento.id_fragmento, cliente=falso)

    assert sugerencia.ok
    assert sugerencia.id_objetivo is None


# --- etiquetar_pendientes: el lote -----------------------------------------------


def test_etiquetar_pendientes_cubre_solo_lo_no_asignado(db, documento, objetivo):
    fragmentos = _fragmentos(db, documento)
    fragmentos[0].id_objetivo = objetivo.id_objetivo  # ya clasificado a mano
    db.commit()
    falso = ClienteEtiquetadorFalso(id_objetivo=objetivo.id_objetivo)

    resultados = tagger.etiquetar_pendientes(db, cliente=falso, id_documento=documento.id_documento)

    assert falso.llamadas == 2, "el ya asignado no debe volver a consultarse"
    assert {r.id_fragmento for r in resultados} == {f.id_fragmento for f in fragmentos[1:]}


def test_etiquetar_pendientes_sigue_tras_un_fallo(db, documento, objetivo):
    """Un fragmento sin texto no debe abortar el resto del lote."""
    fragmentos = _fragmentos(db, documento)
    fragmentos[1].contenido_texto = "   "
    db.commit()
    falso = ClienteEtiquetadorFalso(id_objetivo=objetivo.id_objetivo)

    resultados = tagger.etiquetar_pendientes(db, cliente=falso, id_documento=documento.id_documento)

    assert len(resultados) == 3
    fallidos = [r for r in resultados if not r.ok]
    exitosos = [r for r in resultados if r.ok]
    assert len(fallidos) == 1
    assert len(exitosos) == 2
    assert fallidos[0].id_fragmento == fragmentos[1].id_fragmento


def test_etiquetar_pendientes_respeta_el_limite(db, documento, objetivo):
    falso = ClienteEtiquetadorFalso(id_objetivo=objetivo.id_objetivo)

    resultados = tagger.etiquetar_pendientes(
        db, cliente=falso, id_documento=documento.id_documento, limite=1
    )

    assert len(resultados) == 1
    assert falso.llamadas == 1


def test_etiquetar_pendientes_filtra_por_documento(db, documento, objetivo):
    otro_doc = DocumentoFuente(
        titulo="Otro apunte",
        formato="pdf",
        asignatura=ASIGNATURA_PRUEBA,
        hash_archivo="hash-de-prueba-tagger-otro",
        estado_curacion="pendiente",
    )
    db.add(otro_doc)
    db.flush()
    db.add(
        Fragmento(
            id_documento=otro_doc.id_documento,
            numero_fragmento=1,
            tipo_fragmento="texto",
            contenido_texto="Fragmento de un documento distinto.",
            estado_validacion="pendiente",
        )
    )
    db.commit()
    falso = ClienteEtiquetadorFalso(id_objetivo=objetivo.id_objetivo)

    try:
        resultados = tagger.etiquetar_pendientes(
            db, cliente=falso, id_documento=documento.id_documento, limite=20
        )
        ids_documento = {f.id_fragmento for f in _fragmentos(db, documento)}
        assert {r.id_fragmento for r in resultados} == ids_documento
    finally:
        db.query(Fragmento).filter(Fragmento.id_documento == otro_doc.id_documento).delete()
        db.delete(otro_doc)
        db.commit()
