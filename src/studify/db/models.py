"""Las 8 entidades del modelo lógico (cap. 17 del informe).

Transcripción del diccionario de datos (tablas 17.1–17.8) a SQLAlchemy 2.0.
Los tipos del informe están escritos en notación MySQL; aquí se usan sus
equivalentes en PostgreSQL:

    DATETIME       → TIMESTAMP WITH TIME ZONE
    TINYINT        → SMALLINT   (Postgres no tiene enteros de 1 byte)
    JSON           → JSONB      (indexable y con operadores nativos)
    DECIMAL(5,2)   → NUMERIC(5,2), expuesto como Decimal en Python

Principio rector del cap. 17: **el perfil de aprendizaje se almacena solo como
vector de porcentajes**, nunca como etiqueta ("visual", "bimodal", …). La
jerarquía de canales y la condición de multimodalidad se derivan en tiempo de
consulta (cap. 17.2, implementado en `studify.vark.hierarchy`), para que no
exista riesgo de inconsistencia entre el vector y su interpretación.
"""

from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Numeric,
    SmallInteger,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from studify.db.base import Base

# Todas las marcas de tiempo se guardan con zona horaria: el informe las declara
# como DATETIME (notación MySQL), pero un TIMESTAMP desnudo en Postgres deja la
# interpretación a merced del huso de la sesión, y los dos computadores del
# equipo no tienen por qué compartirlo.
TS = DateTime(timezone=True)

# --- Vocabularios controlados -------------------------------------------------
# Se validan con CHECK y no con ENUM nativo: agregar un valor a un ENUM de
# Postgres exige ALTER TYPE, mientras que un CHECK se cambia en una migración
# normal. En un prototipo que aún está afinando estados, eso importa.

ESTADOS_CURACION = ("pendiente", "validado", "rechazado")
ESTADOS_VALIDACION_FRAGMENTO = ("pendiente", "validado", "descartado")
ESTADOS_VALIDACION_CAPSULA = ("generada", "validada", "rechazada")
ESTADOS_OBJETIVO = ("activo", "inactivo", "en_revision")
CANALES_VARK = ("V", "A", "R", "K")


class Estudiante(Base):
    """Tabla 17.1 — variables sociodemográficas del cap. 9.

    Es la unidad sobre la que se ejecuta la segmentación (moda de perfiles por
    carrera, cap. 16.2), por eso `carrera` va indexada.
    """

    __tablename__ = "estudiante"

    id_estudiante: Mapped[int] = mapped_column(primary_key=True)
    rango_etario: Mapped[str | None] = mapped_column(String(20))
    # La tabla 17.1 declara VARCHAR(20), pero el propio instrumento ofrece la
    # alternativa "No Binario / otra identidad" (27 caracteres), que no cabe.
    # Se amplía a 50 para que el modelo acepte las opciones que el formulario
    # realmente entrega.
    genero: Mapped[str | None] = mapped_column(String(50))
    carrera: Mapped[str | None] = mapped_column(String(80), index=True)
    ano_ingreso: Mapped[int | None]
    fecha_registro: Mapped[datetime] = mapped_column(
        TS, server_default=func.now(), nullable=False
    )

    diagnosticos: Mapped[list["DiagnosticoVark"]] = relationship(
        back_populates="estudiante", cascade="all, delete-orphan"
    )
    capsulas: Mapped[list["MicrocapsulaGenerada"]] = relationship(
        back_populates="estudiante"
    )


class DiagnosticoVark(Base):
    """Tabla 17.2 — resultado de la calificación VARK (cap. 10).

    Guarda las dos representaciones que exige el informe: los puntajes crudos
    (frecuencia absoluta de selecciones) y el vector porcentual normalizado.
    Los crudos permiten reproducir las tablas 16.2/16.3, que están expresadas
    en promedios de puntaje, no de porcentaje.

    El CHECK sobre la suma de porcentajes admite ±0.05 de tolerancia: al
    repartir 100 entre cuatro canales con 2 decimales, el redondeo puede dejar
    la suma en 99.99 o 100.01.
    """

    __tablename__ = "diagnostico_vark"
    __table_args__ = (
        CheckConstraint(
            "porcentaje_v + porcentaje_a + porcentaje_r + porcentaje_k "
            "BETWEEN 99.95 AND 100.05",
            name="ck_diagnostico_porcentajes_suman_100",
        ),
        CheckConstraint(
            "puntaje_v >= 0 AND puntaje_a >= 0 AND puntaje_r >= 0 AND puntaje_k >= 0",
            name="ck_diagnostico_puntajes_no_negativos",
        ),
    )

    id_diagnostico: Mapped[int] = mapped_column(primary_key=True)
    id_estudiante: Mapped[int] = mapped_column(
        ForeignKey("estudiante.id_estudiante", ondelete="CASCADE"), index=True
    )

    puntaje_v: Mapped[int]
    puntaje_a: Mapped[int]
    puntaje_r: Mapped[int]
    puntaje_k: Mapped[int]

    porcentaje_v: Mapped[Decimal] = mapped_column(Numeric(5, 2))
    porcentaje_a: Mapped[Decimal] = mapped_column(Numeric(5, 2))
    porcentaje_r: Mapped[Decimal] = mapped_column(Numeric(5, 2))
    porcentaje_k: Mapped[Decimal] = mapped_column(Numeric(5, 2))

    fecha_diagnostico: Mapped[datetime] = mapped_column(
        TS, server_default=func.now(), nullable=False
    )

    estudiante: Mapped["Estudiante"] = relationship(back_populates="diagnosticos")
    respuestas: Mapped[list["RespuestaVark"]] = relationship(
        back_populates="diagnostico", cascade="all, delete-orphan"
    )
    configuracion: Mapped["ConfiguracionContenido | None"] = relationship(
        back_populates="diagnostico",
        cascade="all, delete-orphan",
        uselist=False,
    )


class RespuestaVark(Base):
    """Tabla 17.3 — selección individual en cada ítem del instrumento.

    Existe para poder **recalcular** los perfiles si cambia la matriz de
    puntuación, sin volver a aplicar el cuestionario (cap. 17.1).

    Un estudiante puede marcar varias alternativas en un mismo ítem (cap. 10:
    selección múltiple habilitada), así que la unicidad es por
    (diagnóstico, pregunta, alternativa) y no por (diagnóstico, pregunta).
    """

    __tablename__ = "respuesta_vark"
    __table_args__ = (
        UniqueConstraint(
            "id_diagnostico",
            "num_pregunta",
            "alternativa",
            name="uq_respuesta_diagnostico_pregunta_alternativa",
        ),
        CheckConstraint(
            "num_pregunta BETWEEN 1 AND 16", name="ck_respuesta_num_pregunta_1_16"
        ),
        CheckConstraint(
            "canal_mapeado IN ('V', 'A', 'R', 'K')", name="ck_respuesta_canal_vark"
        ),
    )

    id_respuesta: Mapped[int] = mapped_column(primary_key=True)
    id_diagnostico: Mapped[int] = mapped_column(
        ForeignKey("diagnostico_vark.id_diagnostico", ondelete="CASCADE"), index=True
    )
    num_pregunta: Mapped[int] = mapped_column(SmallInteger)
    alternativa: Mapped[str] = mapped_column(String(1))
    canal_mapeado: Mapped[str] = mapped_column(String(1))

    diagnostico: Mapped["DiagnosticoVark"] = relationship(back_populates="respuestas")


class ConfiguracionContenido(Base):
    """Tabla 17.4 — salida de las reglas de decisión del cap. 11.2.

    Traduce el vector porcentual en parámetros concretos de generación. Los
    `peso_*` son los C_* continuos de las fórmulas; los enteros
    (`recursos_visuales`, `palabras_texto`, `componentes_practicos`) son los
    cortes aplicados sobre ellos (ver `studify.vark.rules`).

    Relación 1:1 con el diagnóstico: una configuración es función pura del
    vector, de modo que un mismo diagnóstico no puede tener dos.
    """

    __tablename__ = "configuracion_contenido"
    __table_args__ = (
        CheckConstraint(
            "palabras_texto BETWEEN 150 AND 300", name="ck_config_palabras_150_300"
        ),
        CheckConstraint(
            "recursos_visuales >= 0 AND componentes_practicos >= 0",
            name="ck_config_cantidades_no_negativas",
        ),
    )

    id_config: Mapped[int] = mapped_column(primary_key=True)
    id_diagnostico: Mapped[int] = mapped_column(
        ForeignKey("diagnostico_vark.id_diagnostico", ondelete="CASCADE"),
        unique=True,
    )

    peso_texto: Mapped[Decimal] = mapped_column(Numeric(5, 2))
    peso_visual: Mapped[Decimal] = mapped_column(Numeric(5, 2))
    peso_narrativo: Mapped[Decimal] = mapped_column(Numeric(5, 2))
    peso_practico: Mapped[Decimal] = mapped_column(Numeric(5, 2))

    recursos_visuales: Mapped[int] = mapped_column(SmallInteger)
    palabras_texto: Mapped[int] = mapped_column(SmallInteger)
    componentes_practicos: Mapped[int] = mapped_column(SmallInteger)

    # Fuera de alcance del prototipo: no hay TTS en el stack del cap. 14.
    # Se conserva el campo para no desviarse del modelo del informe; queda
    # declarado como trabajo futuro (decisión 2 de PLAN_DESARROLLO.md §6).
    audio_activo: Mapped[bool] = mapped_column(default=False)

    tono_narrativo: Mapped[str] = mapped_column(String(20))
    canales_activos: Mapped[str] = mapped_column(String(10))

    diagnostico: Mapped["DiagnosticoVark"] = relationship(
        back_populates="configuracion"
    )
    capsulas: Mapped[list["MicrocapsulaGenerada"]] = relationship(
        back_populates="configuracion"
    )


class ObjetivoAprendizaje(Base):
    """Tabla 17.5 — catálogo curricular.

    Se carga manualmente: es información curricular institucional, no se
    infiere desde los documentos (Fase 2 del plan).
    """

    __tablename__ = "objetivo_aprendizaje"
    __table_args__ = (
        CheckConstraint(
            "estado IN ('activo', 'inactivo', 'en_revision')",
            name="ck_objetivo_estado",
        ),
        Index("ix_objetivo_asignatura_unidad", "asignatura", "unidad"),
    )

    id_objetivo: Mapped[int] = mapped_column(primary_key=True)
    codigo_objetivo: Mapped[str] = mapped_column(String(30), unique=True)
    asignatura: Mapped[str] = mapped_column(String(100))
    unidad: Mapped[str] = mapped_column(String(100))
    tema: Mapped[str] = mapped_column(String(150))
    descripcion: Mapped[str | None] = mapped_column(Text)
    nivel_taxonomico: Mapped[str | None] = mapped_column(String(50))
    estado: Mapped[str] = mapped_column(String(20), default="activo")

    fragmentos: Mapped[list["Fragmento"]] = relationship(back_populates="objetivo")
    capsulas: Mapped[list["MicrocapsulaGenerada"]] = relationship(
        back_populates="objetivo"
    )


class DocumentoFuente(Base):
    """Tabla 17.6 — documento institucional incorporado a la base de conocimiento.

    `hash_archivo` es único: evita cargar dos veces el mismo PDF, que es el
    error más fácil de cometer durante la curación de la Fase 2.
    """

    __tablename__ = "documento_fuente"
    __table_args__ = (
        CheckConstraint(
            "estado_curacion IN ('pendiente', 'validado', 'rechazado')",
            name="ck_documento_estado_curacion",
        ),
    )

    id_documento: Mapped[int] = mapped_column(primary_key=True)
    titulo: Mapped[str] = mapped_column(String(150))
    tipo_documento: Mapped[str | None] = mapped_column(String(40))
    formato: Mapped[str | None] = mapped_column(String(20))
    origen: Mapped[str | None] = mapped_column(String(100))
    asignatura: Mapped[str | None] = mapped_column(String(100), index=True)
    version: Mapped[str | None] = mapped_column(String(20))
    ruta_archivo: Mapped[str | None] = mapped_column(String(255))
    hash_archivo: Mapped[str | None] = mapped_column(String(128), unique=True)
    estado_curacion: Mapped[str] = mapped_column(String(30), default="pendiente")
    fecha_carga: Mapped[datetime] = mapped_column(
        TS, server_default=func.now(), nullable=False
    )

    fragmentos: Mapped[list["Fragmento"]] = relationship(
        back_populates="documento", cascade="all, delete-orphan"
    )


class Fragmento(Base):
    """Tabla 17.7 — unidad recuperable del RAG estructurado.

    Sin embeddings, por diseño (cap. 12/13): la recuperación es SQL sobre
    `id_objetivo` + `estado_validacion`, con full-text search en español como
    filtro secundario. De ahí el índice GIN sobre `to_tsvector('spanish', …)`.

    `estado_validacion` es la barrera de seguridad del proyecto: ningún
    fragmento sin validar puede entrar al prompt, porque es exactamente el
    riesgo de alucinación que advierte Hashiyada et al. (cap. 13).
    """

    __tablename__ = "fragmento"
    __table_args__ = (
        CheckConstraint(
            "estado_validacion IN ('pendiente', 'validado', 'descartado')",
            name="ck_fragmento_estado_validacion",
        ),
        CheckConstraint(
            "pagina_fin IS NULL OR pagina_inicio IS NULL OR pagina_fin >= pagina_inicio",
            name="ck_fragmento_paginas_coherentes",
        ),
        UniqueConstraint(
            "id_documento", "numero_fragmento", name="uq_fragmento_documento_numero"
        ),
        # Índice del retriever: filtra por objetivo y estado en una sola pasada.
        Index("ix_fragmento_objetivo_estado", "id_objetivo", "estado_validacion"),
    )

    id_fragmento: Mapped[int] = mapped_column(primary_key=True)
    id_documento: Mapped[int] = mapped_column(
        ForeignKey("documento_fuente.id_documento", ondelete="CASCADE"), index=True
    )
    id_objetivo: Mapped[int | None] = mapped_column(
        ForeignKey("objetivo_aprendizaje.id_objetivo", ondelete="SET NULL")
    )
    numero_fragmento: Mapped[int]
    tipo_fragmento: Mapped[str] = mapped_column(String(30), default="texto")
    contenido_texto: Mapped[str | None] = mapped_column(Text)
    ruta_recurso: Mapped[str | None] = mapped_column(String(255))
    pagina_inicio: Mapped[int | None]
    pagina_fin: Mapped[int | None]
    etiqueta_tematica: Mapped[str | None] = mapped_column(String(100))
    metadatos_json: Mapped[dict | None] = mapped_column(JSONB)
    estado_validacion: Mapped[str] = mapped_column(String(30), default="pendiente")

    documento: Mapped["DocumentoFuente"] = relationship(back_populates="fragmentos")
    objetivo: Mapped["ObjetivoAprendizaje | None"] = relationship(
        back_populates="fragmentos"
    )


class MicrocapsulaGenerada(Base):
    """Tabla 17.8 — el artefacto que produce el sistema.

    La FK a `fragmento` es lo que hace nativa la trazabilidad exigida en el
    cap. 13: cada cápsula queda vinculada al documento oficial exacto que la
    fundamentó. `contenido_json` sigue el contrato definido en
    PLAN_DESARROLLO.md §3 y validado por `generation/validator.py` (Fase 3).
    """

    __tablename__ = "microcapsula_generada"
    __table_args__ = (
        CheckConstraint(
            "estado_validacion IN ('generada', 'validada', 'rechazada')",
            name="ck_capsula_estado_validacion",
        ),
        Index("ix_capsula_estudiante_objetivo", "id_estudiante", "id_objetivo"),
    )

    id_capsula: Mapped[int] = mapped_column(primary_key=True)
    id_estudiante: Mapped[int] = mapped_column(
        ForeignKey("estudiante.id_estudiante", ondelete="CASCADE"), index=True
    )
    id_objetivo: Mapped[int] = mapped_column(
        ForeignKey("objetivo_aprendizaje.id_objetivo", ondelete="RESTRICT")
    )
    id_config: Mapped[int | None] = mapped_column(
        ForeignKey("configuracion_contenido.id_config", ondelete="SET NULL")
    )
    # El fragmento *principal*; el detalle completo de fuentes citadas va en
    # contenido_json["fuentes"], que el validador contrasta contra los
    # fragmentos realmente inyectados en el prompt.
    id_fragmento_fuente: Mapped[int | None] = mapped_column(
        ForeignKey("fragmento.id_fragmento", ondelete="SET NULL")
    )

    titulo: Mapped[str] = mapped_column(String(150))
    contenido_json: Mapped[dict] = mapped_column(JSONB)
    mini_quiz_json: Mapped[dict | None] = mapped_column(JSONB)
    estado_validacion: Mapped[str] = mapped_column(String(30), default="generada")
    fecha_generacion: Mapped[datetime] = mapped_column(
        TS, server_default=func.now(), nullable=False
    )

    # --- Añadidos en la Fase 3, no están en la tabla 17.8 del informe --------
    #
    # `huella_generacion` es la clave de caché que calcula
    # `rag/orchestrator.huella()`: resume todo lo que determina la cápsula
    # (objetivo, tramo del perfil, fragmentos disponibles y modelo). Va como
    # columna y no dentro de `contenido_json` porque es lo que se consulta en
    # cada petición, y un `->>` sobre JSONB no aprovecha índice.
    #
    # `modelo_llm` hace legible una cápsula guardada: el bake-off de la Fase 3
    # deja en la misma tabla las cápsulas de los tres modelos candidatos, y sin
    # esta columna no hay forma de saber cuál produjo cada una.
    huella_generacion: Mapped[str | None] = mapped_column(String(64), index=True)
    modelo_llm: Mapped[str | None] = mapped_column(String(60))

    estudiante: Mapped["Estudiante"] = relationship(back_populates="capsulas")
    objetivo: Mapped["ObjetivoAprendizaje"] = relationship(back_populates="capsulas")
    configuracion: Mapped["ConfiguracionContenido | None"] = relationship(
        back_populates="capsulas"
    )
    fragmento_fuente: Mapped["Fragmento | None"] = relationship()


# Índice GIN para el full-text search en español que el retriever usa como
# filtro secundario (Fase 2).
#
# La expresión va como SQL textual y no como `func.to_tsvector(...)` por dos
# razones: Postgres solo admite expresiones IMMUTABLE en un índice —la variante
# de un argumento depende de `default_text_search_config`, que es de sesión—, y
# el literal tipado REGCONFIG que sí lo haría inmutable no lo sabe renderizar
# el autogenerate de Alembic (CompileError: "no literal value renderer").
#
# Las consultas del retriever deben usar exactamente esta misma expresión para
# que el planner elija el índice.
Index(
    "ix_fragmento_contenido_fts",
    text("to_tsvector('spanish', contenido_texto)"),
    postgresql_using="gin",
)
