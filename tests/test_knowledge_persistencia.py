"""Tests de `knowledge.ingest` contra Postgres.

Verifican la parte que las funciones puras no pueden cubrir: deduplicación por
contenido, y —lo más importante— que **nada entra habilitado** a la base de
conocimiento sin pasar por curación.
"""

from pathlib import Path

import pytest
from sqlalchemy import select

from studify.db.models import DocumentoFuente, Fragmento
from studify.knowledge.ingest import (
    DocumentoDuplicado,
    DocumentoSinTexto,
    ingerir,
)
from tests.conftest import necesita_bd

pytestmark = necesita_bd


@pytest.fixture
def pdf_de_prueba(tmp_path) -> Path:
    """Un apunte de dos secciones, generado como PDF real."""
    pymupdf = pytest.importorskip("pymupdf")

    ruta = tmp_path / "unidad_normalizacion.pdf"
    doc = pymupdf.open()
    for titulo, cuerpo in [
        ("Modelo relacional", "Una tabla representa una relacion matematica entre dominios. " * 12),
        ("Claves foraneas", "La clave foranea garantiza la integridad referencial. " * 12),
    ]:
        pagina = doc.new_page()
        pagina.insert_text((72, 90), titulo, fontsize=18)
        pagina.insert_textbox((72, 120, 520, 700), cuerpo, fontsize=11)
    doc.save(ruta)
    doc.close()
    return ruta


@pytest.fixture
def limpiar_documentos(db):
    """Borra los documentos creados por el test (los fragmentos caen por CASCADE)."""
    creados: list[int] = []
    yield creados
    for id_doc in creados:
        doc = db.get(DocumentoFuente, id_doc)
        if doc is not None:
            db.delete(doc)
    db.commit()


def test_ingesta_crea_documento_y_fragmentos(
    db, pdf_de_prueba, almacen_temporal, limpiar_documentos
):
    resultado = ingerir(
        db, pdf_de_prueba, asignatura="Bases de Datos", tipo_documento="apunte"
    )
    limpiar_documentos.append(resultado.id_documento)

    assert resultado.total_fragmentos > 0
    assert resultado.pagina_maxima == 2
    assert resultado.palabras_totales > 0

    doc = db.get(DocumentoFuente, resultado.id_documento)
    assert doc.asignatura == "Bases de Datos"
    assert doc.formato == "pdf"
    assert doc.hash_archivo is not None

    fragmentos = db.scalars(
        select(Fragmento).where(Fragmento.id_documento == doc.id_documento)
    ).all()
    assert len(fragmentos) == resultado.total_fragmentos


def test_nada_entra_habilitado_sin_curacion(
    db, pdf_de_prueba, almacen_temporal, limpiar_documentos
):
    """La barrera del cap. 12/13: ingerir no es lo mismo que habilitar.

    Es la invariante central de la Fase 2. Si esto se rompe, material sin
    revisar puede llegar al prompt, que es exactamente el riesgo de alucinación
    que advierte Hashiyada et al.
    """
    resultado = ingerir(db, pdf_de_prueba)
    limpiar_documentos.append(resultado.id_documento)

    doc = db.get(DocumentoFuente, resultado.id_documento)
    assert doc.estado_curacion == "pendiente"

    fragmentos = db.scalars(
        select(Fragmento).where(Fragmento.id_documento == doc.id_documento)
    ).all()
    assert all(f.estado_validacion == "pendiente" for f in fragmentos)
    assert all(f.id_objetivo is None for f in fragmentos), (
        "asignar el objetivo de aprendizaje es una decisión curricular humana"
    )


def test_el_mismo_archivo_con_otro_nombre_se_rechaza(
    db, pdf_de_prueba, tmp_path, almacen_temporal, limpiar_documentos
):
    """La deduplicación es por contenido (SHA-256), no por nombre de archivo."""
    resultado = ingerir(db, pdf_de_prueba)
    limpiar_documentos.append(resultado.id_documento)

    copia = tmp_path / "clase_1_copia.pdf"
    copia.write_bytes(pdf_de_prueba.read_bytes())

    with pytest.raises(DocumentoDuplicado) as exc:
        ingerir(db, copia)

    assert exc.value.id_documento == resultado.id_documento


def test_documento_sin_texto_no_deja_basura_en_la_base(
    db, tmp_path, almacen_temporal
):
    """Un PDF escaneado no debe dejar un documento vacío ni una copia huérfana."""
    pymupdf = pytest.importorskip("pymupdf")

    ruta = tmp_path / "escaneado.pdf"
    doc = pymupdf.open()
    doc.new_page()  # página en blanco: sin capa de texto
    doc.save(ruta)
    doc.close()

    antes = db.scalar(select(DocumentoFuente.id_documento).order_by(
        DocumentoFuente.id_documento.desc()
    ))

    with pytest.raises(DocumentoSinTexto, match="OCR"):
        ingerir(db, ruta)
    db.rollback()

    despues = db.scalar(select(DocumentoFuente.id_documento).order_by(
        DocumentoFuente.id_documento.desc()
    ))
    assert antes == despues, "no debe crearse ninguna fila"
    assert not Path(almacen_temporal).exists() or not list(Path(almacen_temporal).iterdir())


def test_el_archivo_queda_copiado_en_el_almacen(
    db, pdf_de_prueba, almacen_temporal, limpiar_documentos
):
    """`ruta_archivo` debe seguir siendo válida aunque el docente mueva el original."""
    resultado = ingerir(db, pdf_de_prueba)
    limpiar_documentos.append(resultado.id_documento)

    doc = db.get(DocumentoFuente, resultado.id_documento)
    almacenado = Path(doc.ruta_archivo)

    assert almacenado.exists()
    assert almacenado.parent == Path(almacen_temporal)
    assert doc.hash_archivo in almacenado.name

    pdf_de_prueba.unlink()
    assert almacenado.exists(), "la copia sobrevive al borrado del original"


def test_los_fragmentos_conservan_pagina_y_etiqueta(
    db, pdf_de_prueba, almacen_temporal, limpiar_documentos
):
    """Sin página, la exactitud factual del cap. 8.1 no es verificable."""
    resultado = ingerir(db, pdf_de_prueba)
    limpiar_documentos.append(resultado.id_documento)

    fragmentos = db.scalars(
        select(Fragmento)
        .where(Fragmento.id_documento == resultado.id_documento)
        .order_by(Fragmento.numero_fragmento)
    ).all()

    for f in fragmentos:
        assert f.pagina_inicio is not None
        assert f.pagina_fin >= f.pagina_inicio
        assert f.contenido_texto.strip()
        assert f.metadatos_json["palabras"] > 0

    etiquetas = {f.etiqueta_tematica for f in fragmentos}
    assert "Modelo relacional" in etiquetas
