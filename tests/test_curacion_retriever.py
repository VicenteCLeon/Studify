"""Tests de curación y recuperación determinista (Fase 2).

Se concentran en las dos invariantes que sostienen la tesis del proyecto:

1. **Ningún fragmento sin validar llega al retriever** (cap. 12/13).
2. **La recuperación es determinista**: mismos argumentos, mismo resultado, en
   el mismo orden (cap. 13). Si esto no se cumple, el sistema no es más
   auditable que una búsqueda vectorial.
"""

import pytest
from sqlalchemy import select

from studify.db.models import DocumentoFuente, Fragmento, ObjetivoAprendizaje
from studify.knowledge import curation
from studify.rag.retriever import contar_disponibles, recuperar
from tests.conftest import necesita_bd

pytestmark = necesita_bd


@pytest.fixture
def objetivo(db):
    """Un objetivo de aprendizaje desechable."""
    obj = ObjetivoAprendizaje(
        codigo_objetivo="TEST-BD-01",
        asignatura="Bases de Datos (test)",
        unidad="Unidad 3",
        tema="Normalización",
        descripcion="Aplicar las tres primeras formas normales.",
        estado="activo",
    )
    db.add(obj)
    db.commit()
    yield obj
    db.delete(obj)
    db.commit()


@pytest.fixture
def documento(db):
    """Documento con cuatro fragmentos pendientes, uno de ellos tabla."""
    doc = DocumentoFuente(
        titulo="Apunte de prueba",
        formato="pdf",
        asignatura="Bases de Datos (test)",
        hash_archivo="hash-de-prueba-curacion",
        estado_curacion="pendiente",
    )
    db.add(doc)
    db.flush()

    for numero, (tipo, texto) in enumerate(
        [
            ("texto", "La normalización reduce la redundancia de los datos almacenados."),
            ("texto", "Una dependencia funcional relaciona atributos de una misma relación."),
            ("tabla", "Forma | Exige\n1FN | Atomicidad\n2FN | Sin dependencias parciales"),
            ("texto", "La tercera forma normal elimina las dependencias transitivas."),
        ],
        start=1,
    ):
        db.add(
            Fragmento(
                id_documento=doc.id_documento,
                numero_fragmento=numero,
                tipo_fragmento=tipo,
                contenido_texto=texto,
                pagina_inicio=numero,
                pagina_fin=numero,
                etiqueta_tematica="Normalización",
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


# --- La barrera de curación ---------------------------------------------------


def test_el_retriever_ignora_los_fragmentos_pendientes(db, documento, objetivo):
    """La invariante central: sin curación no hay recuperación."""
    for f in _fragmentos(db, documento):
        f.id_objetivo = objetivo.id_objetivo
    db.commit()

    assert recuperar(db, id_objetivo=objetivo.id_objetivo) == []
    assert contar_disponibles(db, objetivo.id_objetivo) == 0


def test_validar_sin_objetivo_se_rechaza(db, documento):
    """Un fragmento validado sin objetivo quedaría inalcanzable para siempre."""
    fragmento = _fragmentos(db, documento)[0]

    with pytest.raises(curation.ErrorCuracion, match="objetivo de aprendizaje"):
        curation.validar(db, fragmento.id_fragmento)

    db.refresh(fragmento)
    assert fragmento.estado_validacion == "pendiente", "no debe quedar a medias"


def test_validar_asignando_objetivo_en_el_mismo_acto(db, documento, objetivo):
    fragmento = _fragmentos(db, documento)[0]

    curation.validar(db, fragmento.id_fragmento, id_objetivo=objetivo.id_objetivo)

    db.refresh(fragmento)
    assert fragmento.estado_validacion == "validado"
    assert fragmento.id_objetivo == objetivo.id_objetivo
    assert recuperar(db, id_objetivo=objetivo.id_objetivo)


def test_validar_promueve_el_estado_del_documento(db, documento, objetivo):
    """Si no, el panel mostraría trabajo terminado como pendiente para siempre."""
    assert documento.estado_curacion == "pendiente"
    fragmento = _fragmentos(db, documento)[0]

    curation.validar(db, fragmento.id_fragmento, id_objetivo=objetivo.id_objetivo)

    db.refresh(documento)
    assert documento.estado_curacion == "validado"


def test_descartado_no_se_recupera_pero_se_conserva(db, documento, objetivo):
    """El cap. 12 exige trazabilidad del proceso: descartar no es borrar."""
    fragmento = _fragmentos(db, documento)[0]
    curation.validar(db, fragmento.id_fragmento, id_objetivo=objetivo.id_objetivo)
    assert contar_disponibles(db, objetivo.id_objetivo) == 1

    curation.descartar(db, fragmento.id_fragmento)

    assert contar_disponibles(db, objetivo.id_objetivo) == 0
    assert db.get(Fragmento, fragmento.id_fragmento) is not None


def test_rechazar_el_documento_saca_sus_fragmentos_del_retriever(db, documento, objetivo):
    """Un apunte que resultó estar desactualizado invalida su material validado."""
    for f in _fragmentos(db, documento):
        curation.validar(db, f.id_fragmento, id_objetivo=objetivo.id_objetivo)
    assert contar_disponibles(db, objetivo.id_objetivo) == 4

    documento.estado_curacion = "rechazado"
    db.commit()

    assert recuperar(db, id_objetivo=objetivo.id_objetivo) == []


def test_no_se_puede_asignar_un_objetivo_inactivo(db, documento, objetivo):
    objetivo.estado = "en_revision"
    db.commit()
    fragmento = _fragmentos(db, documento)[0]

    with pytest.raises(curation.ErrorCuracion, match="en_revision"):
        curation.asignar_objetivo(db, fragmento.id_fragmento, objetivo.id_objetivo)


def test_editar_texto_actualiza_el_conteo_de_palabras(db, documento):
    fragmento = _fragmentos(db, documento)[0]

    curation.editar_texto(db, fragmento.id_fragmento, "Texto corregido por el curador.")

    db.refresh(fragmento)
    assert fragmento.contenido_texto == "Texto corregido por el curador."
    assert fragmento.metadatos_json["palabras"] == 5
    assert fragmento.metadatos_json["editado_por_curador"] is True


def test_editar_a_texto_vacio_se_rechaza(db, documento):
    fragmento = _fragmentos(db, documento)[0]

    with pytest.raises(curation.ErrorCuracion, match="descartar"):
        curation.editar_texto(db, fragmento.id_fragmento, "   ")


def test_resumen_cuenta_los_tres_estados(db, documento, objetivo):
    fragmentos = _fragmentos(db, documento)
    curation.validar(db, fragmentos[0].id_fragmento, id_objetivo=objetivo.id_objetivo)
    curation.descartar(db, fragmentos[1].id_fragmento)

    resumen = curation.resumen_documento(db, documento.id_documento)

    assert resumen == {"pendiente": 2, "validado": 1, "descartado": 1, "total": 4}


# --- Determinismo de la recuperación -----------------------------------------


def test_la_recuperacion_es_reproducible(db, documento, objetivo):
    """Mismos argumentos → mismos fragmentos, en el mismo orden (cap. 13)."""
    for f in _fragmentos(db, documento):
        curation.validar(db, f.id_fragmento, id_objetivo=objetivo.id_objetivo)

    corridas = [
        [r.id_fragmento for r in recuperar(db, id_objetivo=objetivo.id_objetivo)]
        for _ in range(5)
    ]

    assert all(c == corridas[0] for c in corridas)
    assert corridas[0] == sorted(corridas[0]), "el orden natural es el del documento"


def test_perfil_visual_prioriza_la_tabla(db, documento, objetivo):
    """Tabla 11.1: para un perfil visual la tabla comparativa es el recurso pedido."""
    for f in _fragmentos(db, documento):
        curation.validar(db, f.id_fragmento, id_objetivo=objetivo.id_objetivo)

    visual = recuperar(db, id_objetivo=objetivo.id_objetivo, canal_primario="V")
    lector = recuperar(db, id_objetivo=objetivo.id_objetivo, canal_primario="R")

    assert visual[0].tipo == "tabla"
    assert lector[0].tipo == "texto"
    assert {f.id_fragmento for f in visual} == {f.id_fragmento for f in lector}, (
        "el canal reordena, no filtra: nadie debe quedar fuera por su perfil"
    )


def test_el_canal_reordena_pero_no_excluye(db, documento, objetivo):
    """Si un perfil visual solo recibiera tablas, un apunte sin tablas no daría nada."""
    fragmentos = _fragmentos(db, documento)
    solo_texto = [f for f in fragmentos if f.tipo_fragmento == "texto"]
    for f in solo_texto:
        curation.validar(db, f.id_fragmento, id_objetivo=objetivo.id_objetivo)

    recuperados = recuperar(db, id_objetivo=objetivo.id_objetivo, canal_primario="V")

    assert len(recuperados) == len(solo_texto)


def test_full_text_search_filtra_dentro_del_objetivo(db, documento, objetivo):
    """El FTS es filtro secundario: acota, nunca trae material de otro objetivo."""
    for f in _fragmentos(db, documento):
        curation.validar(db, f.id_fragmento, id_objetivo=objetivo.id_objetivo)

    resultados = recuperar(db, id_objetivo=objetivo.id_objetivo, consulta="dependencia funcional")

    assert resultados, "el stemming español debe encontrar 'dependencia funcional'"
    assert all("dependencia" in r.texto.lower() or "dependencias" in r.texto.lower()
               for r in resultados)
    assert len(resultados) < 4, "debe acotar respecto de traer todo el objetivo"


def test_el_fts_no_cruza_objetivos(db, documento, objetivo):
    """Aunque el texto calce, un fragmento de otro objetivo no puede aparecer."""
    for f in _fragmentos(db, documento):
        curation.validar(db, f.id_fragmento, id_objetivo=objetivo.id_objetivo)

    otro_id = objetivo.id_objetivo + 10_000
    assert recuperar(db, id_objetivo=otro_id, consulta="normalización") == []


def test_la_cita_incluye_documento_y_pagina(db, documento, objetivo):
    """Requisito de trazabilidad del cap. 8.1."""
    fragmento = _fragmentos(db, documento)[0]
    curation.validar(db, fragmento.id_fragmento, id_objetivo=objetivo.id_objetivo)

    recuperado = recuperar(db, id_objetivo=objetivo.id_objetivo)[0]

    assert recuperado.documento == "Apunte de prueba"
    assert recuperado.cita == "Apunte de prueba, p. 1"


def test_el_limite_se_respeta(db, documento, objetivo):
    for f in _fragmentos(db, documento):
        curation.validar(db, f.id_fragmento, id_objetivo=objetivo.id_objetivo)

    assert len(recuperar(db, id_objetivo=objetivo.id_objetivo, limite=2)) == 2
