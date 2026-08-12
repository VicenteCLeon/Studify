"""Panel de cobertura curricular del docente (Fase 5).

La pantalla responde una sola pregunta: *¿sobre qué temas puede el sistema
generar algo hoy?* Contestarla mal tiene dos formas, y las dos son peores que no
tener el panel:

- **Falso verde:** dar por cubierto un objetivo cuyo material el retriever no
  mira. Pasa si la cobertura se cuenta solo por `estado_validacion` y se olvida
  el documento rechazado después de curar, que es justo el filtro que
  `recuperar` sí aplica.
- **Cobertura que esconde el gap real:** ocho fragmentos de texto dejan un tema
  perfecto para los perfiles A y R, y al perfil V leyendo lo mismo que ellos.
  El total por sí solo no lo dice.

Requieren Postgres (se saltan solos si no está).
"""

import pytest
from sqlalchemy import select

from studify.db.models import DocumentoFuente, Fragmento, ObjetivoAprendizaje
from studify.rag import retriever
from studify.web.routers.teacher import (
    MINIMO_RECOMENDADO,
    _cobertura_curricular,
    _fragmentos_sin_clasificar,
)
from tests.conftest import necesita_bd

pytestmark = necesita_bd

ASIGNATURA_PRUEBA = "Bases de Datos (test cobertura)"
TEXTO = (
    "Una dependencia parcial aparece cuando un atributo no clave depende solo "
    "de una parte de la clave primaria compuesta, y no de la clave completa."
)


@pytest.fixture
def escenario(db):
    """Un objetivo y un documento vacíos: cada test agrega los fragmentos que
    necesita para la situación que quiere describir."""
    objetivo = ObjetivoAprendizaje(
        codigo_objetivo="TEST-COB-01",
        asignatura=ASIGNATURA_PRUEBA,
        unidad="Unidad 3",
        tema="Segunda forma normal",
        descripcion="Reconocer dependencias parciales.",
        estado="activo",
    )
    documento = DocumentoFuente(
        titulo="Apunte de prueba (cobertura)",
        formato="pdf",
        hash_archivo="hash-de-prueba-cobertura",
        estado_curacion="validado",
    )
    db.add_all([objetivo, documento])
    db.commit()

    yield {"objetivo": objetivo, "documento": documento}

    db.query(Fragmento).filter(
        Fragmento.id_documento == documento.id_documento
    ).delete(synchronize_session=False)
    db.commit()
    db.delete(documento)
    db.delete(objetivo)
    db.commit()


def _agregar(db, escenario, *, tipo="texto", estado="validado", cuantos=1):
    numero = db.scalar(
        select(Fragmento.numero_fragmento)
        .where(Fragmento.id_documento == escenario["documento"].id_documento)
        .order_by(Fragmento.numero_fragmento.desc())
        .limit(1)
    ) or 0
    for i in range(cuantos):
        db.add(
            Fragmento(
                id_documento=escenario["documento"].id_documento,
                id_objetivo=escenario["objetivo"].id_objetivo
                if estado != "pendiente"
                else None,
                numero_fragmento=numero + i + 1,
                tipo_fragmento=tipo,
                contenido_texto=TEXTO,
                pagina_inicio=1,
                pagina_fin=1,
                estado_validacion=estado,
            )
        )
    db.commit()


def _fila(db):
    return next(
        f
        for f in _cobertura_curricular(db)
        if f["objetivo"].asignatura == ASIGNATURA_PRUEBA
    )


# --- Qué cuenta como cobertura ------------------------------------------------


def test_un_objetivo_sin_material_se_marca_como_falta(db, escenario):
    fila = _fila(db)

    assert fila["total"] == 0
    assert fila["estado"] == "sin_material"


def test_pocos_fragmentos_no_son_cobertura(db, escenario):
    """Con un fragmento la cápsula sale igual, pero fundada en una sola frase
    del apunte: el panel lo dice en vez de pintarlo verde."""
    _agregar(db, escenario, cuantos=MINIMO_RECOMENDADO - 1)

    assert _fila(db)["estado"] == "escaso"


def test_desde_el_minimo_el_objetivo_queda_cubierto(db, escenario):
    _agregar(db, escenario, cuantos=MINIMO_RECOMENDADO)

    fila = _fila(db)
    assert fila["estado"] == "cubierto"
    assert fila["total"] == MINIMO_RECOMENDADO


def test_los_pendientes_no_cuentan_como_cobertura(db, escenario):
    _agregar(db, escenario, estado="pendiente", cuantos=5)

    assert _fila(db)["total"] == 0


def test_los_descartados_no_cuentan_como_cobertura(db, escenario):
    _agregar(db, escenario, estado="descartado", cuantos=5)

    assert _fila(db)["total"] == 0


def test_un_documento_rechazado_despues_de_curar_deja_de_contar(db, escenario):
    """El caso que el conteo por `estado_validacion` no ve: los fragmentos
    siguen validados, pero el retriever ya no los recupera."""
    _agregar(db, escenario, cuantos=MINIMO_RECOMENDADO)
    assert _fila(db)["estado"] == "cubierto"

    escenario["documento"].estado_curacion = "rechazado"
    db.commit()

    assert _fila(db)["total"] == 0
    assert _fila(db)["estado"] == "sin_material"


def test_la_cobertura_coincide_con_lo_que_recupera_el_retriever(db, escenario):
    """La pantalla y el motor tienen que contar lo mismo, o el panel miente."""
    _agregar(db, escenario, cuantos=3)
    _agregar(db, escenario, estado="pendiente", cuantos=2)

    assert _fila(db)["total"] == retriever.contar_disponibles(
        db, escenario["objetivo"].id_objetivo
    )


# --- El gap por canal ---------------------------------------------------------


def _canal(fila, letra: str) -> dict:
    return next(c for c in fila["canales"] if c["canal"] == letra)


def test_solo_texto_deja_al_perfil_visual_sin_adaptacion(db, escenario):
    """Ocho fragmentos de texto: A y R quedan servidos, V lee lo mismo que ellos
    y la diferenciación que el proyecto quiere demostrar no ocurre en ese tema."""
    _agregar(db, escenario, tipo="texto", cuantos=8)

    fila = _fila(db)
    assert fila["estado"] == "cubierto"
    assert _canal(fila, "V")["degradado"] is True
    assert _canal(fila, "A")["degradado"] is False
    assert _canal(fila, "R")["degradado"] is False
    assert _canal(fila, "K")["degradado"] is False


def test_una_tabla_cubre_el_canal_visual(db, escenario):
    _agregar(db, escenario, tipo="texto", cuantos=4)
    _agregar(db, escenario, tipo="tabla", cuantos=1)

    fila = _fila(db)
    assert _canal(fila, "V")["degradado"] is False
    assert _canal(fila, "V")["cantidad"] == 1


def test_sin_material_ningun_canal_se_marca_degradado(db, escenario):
    """Sin nada que recuperar el problema no es la adaptación: es que no hay
    material. Marcar los cuatro canales en ámbar repetiría el mismo aviso."""
    fila = _fila(db)

    assert all(canal["degradado"] is False for canal in fila["canales"])


def test_el_desglose_por_tipo_acompana_al_total(db, escenario):
    _agregar(db, escenario, tipo="texto", cuantos=3)
    _agregar(db, escenario, tipo="esquema", cuantos=1)

    assert dict(_fila(db)["tipos"]) == {"texto": 3, "esquema": 1}


# --- Falta material vs. falta curar -------------------------------------------


def test_los_pendientes_se_informan_aparte(db, escenario):
    """El objetivo se asigna al validar, así que un pendiente no pertenece a
    ningún tema todavía: por objetivo daría siempre cero y parecería que no
    queda trabajo de curación."""
    antes = _fragmentos_sin_clasificar(db)
    _agregar(db, escenario, estado="pendiente", cuantos=4)

    assert _fragmentos_sin_clasificar(db) == antes + 4
    assert _fila(db)["total"] == 0
