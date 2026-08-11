"""Ingesta: archivo oficial → `documento_fuente` + `fragmento` (tablas 17.6/17.7).

Orquesta las dos capas puras (`extract` y `chunker`) y las persiste. Es el único
módulo de `knowledge/` que toca la base de datos, para que la extracción y la
fragmentación —que son donde está la lógica interesante— se puedan testear sin
Postgres.

**Todo entra como "pendiente".** Ni el documento ni sus fragmentos quedan
disponibles para el retriever al ingerirse: el cap. 12 exige que cada documento
pase por «un proceso de revisión y curación» antes de incorporarse, y el cap. 13
recuerda por qué —Hashiyada et al. muestran que saltarse la curación es lo que
hace que el modelo termine recurriendo a fuentes genéricas y alucinando. La
ingesta produce material *candidato*; la curación es la que lo habilita.
"""

import shutil
from dataclasses import dataclass
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from studify.config import get_settings
from studify.db.models import DocumentoFuente, Fragmento
from studify.knowledge.chunker import fragmentar
from studify.knowledge.extract import extraer, hash_archivo

# `formato` es VARCHAR(20) y `tipo_documento` VARCHAR(40) en la tabla 17.6.
TIPOS_DOCUMENTO = ("apunte", "guia", "presentacion", "actividad", "bibliografia")


class DocumentoDuplicado(Exception):
    """El archivo ya está en la base de conocimiento (mismo SHA-256).

    Lleva el id del documento existente para que la interfaz pueda enlazarlo en
    vez de limitarse a decir "ya existe".

    **Alcance de la deduplicación.** El hash es sobre los bytes, así que detecta
    el caso habitual —el mismo archivo subido dos veces, con el nombre que
    sea— pero no una *reexportación* del mismo documento: un PDF regenerado
    lleva otro `/CreationDate` embebido y, por lo tanto, otro hash. Si el
    docente vuelve a exportar el apunte desde PowerPoint, entra como documento
    nuevo y sus fragmentos conviven con los anteriores en el retriever. Mitigar
    eso pide comparar el texto extraído, no los bytes; queda anotado como
    limitación conocida de la Fase 2.
    """

    def __init__(self, id_documento: int, titulo: str):
        self.id_documento = id_documento
        self.titulo = titulo
        super().__init__(
            f"el archivo ya fue ingerido como documento {id_documento} ('{titulo}')"
        )


class DocumentoSinTexto(Exception):
    """El archivo se leyó pero no produjo ningún fragmento recuperable.

    Pasa con PDF escaneados (imágenes sin capa de texto) y con presentaciones
    que solo tienen figuras. No es un fallo del ingestor: es material que no
    sirve para un RAG textual, y conviene decirlo explícitamente en vez de
    dejar un documento vacío en la base.
    """


@dataclass(frozen=True, slots=True)
class ResultadoIngesta:
    id_documento: int
    titulo: str
    total_fragmentos: int
    pagina_maxima: int
    palabras_totales: int


def _almacenar(ruta: Path, huella: str) -> Path:
    """Copia el archivo al almacén, nombrándolo por su hash.

    Nombrar por hash evita dos problemas de una vez: colisiones cuando dos
    docentes suben archivos llamados igual ("Clase 1.pdf"), y archivos
    huérfanos duplicados, porque el mismo contenido siempre aterriza en el
    mismo nombre.
    """
    destino_dir = Path(get_settings().documentos_dir)
    destino_dir.mkdir(parents=True, exist_ok=True)
    destino = destino_dir / f"{huella}{ruta.suffix.lower()}"
    if not destino.exists():
        shutil.copy2(ruta, destino)
    return destino


def ingerir(
    db: Session,
    ruta: Path,
    *,
    titulo: str | None = None,
    asignatura: str | None = None,
    tipo_documento: str | None = None,
    origen: str | None = None,
    version: str | None = None,
) -> ResultadoIngesta:
    """Lee un PDF/PPTX, lo fragmenta y lo deja en la base como pendiente.

    Hace `commit`: la ingesta es una unidad de trabajo completa (documento +
    todos sus fragmentos) y dejarla a medias produciría un documento sin
    material recuperable.

    Lanza `DocumentoDuplicado` si el archivo ya estaba —la comprobación es por
    contenido y no por nombre— y `DocumentoSinTexto` si no se extrajo nada.
    """
    huella = hash_archivo(ruta)

    existente = db.scalar(
        select(DocumentoFuente).where(DocumentoFuente.hash_archivo == huella)
    )
    if existente is not None:
        raise DocumentoDuplicado(existente.id_documento, existente.titulo)

    # Se extrae y fragmenta *antes* de escribir nada: si el documento no tiene
    # texto aprovechable, no se guarda ni la fila ni la copia del archivo.
    fragmentos_crudos = fragmentar(extraer(ruta))
    if not fragmentos_crudos:
        raise DocumentoSinTexto(
            f"'{ruta.name}' no produjo fragmentos recuperables. Si es un PDF "
            f"escaneado, necesita OCR antes de incorporarse."
        )

    ruta_almacenada = _almacenar(ruta, huella)

    documento = DocumentoFuente(
        titulo=(titulo or ruta.stem)[:150],
        tipo_documento=tipo_documento,
        formato=ruta.suffix.lstrip(".").lower(),
        origen=origen,
        asignatura=asignatura,
        version=version,
        ruta_archivo=str(ruta_almacenada),
        hash_archivo=huella,
        estado_curacion="pendiente",
    )
    db.add(documento)
    db.flush()

    db.add_all(
        Fragmento(
            id_documento=documento.id_documento,
            # Sin objetivo asignado: es una decisión curricular que toma una
            # persona durante la curación, no el ingestor (cap. 12).
            id_objetivo=None,
            numero_fragmento=f.numero,
            tipo_fragmento=f.tipo,
            contenido_texto=f.texto,
            pagina_inicio=f.pagina_inicio,
            pagina_fin=f.pagina_fin,
            etiqueta_tematica=f.etiqueta_tematica,
            metadatos_json={"palabras": f.palabras},
            estado_validacion="pendiente",
        )
        for f in fragmentos_crudos
    )
    db.commit()

    return ResultadoIngesta(
        id_documento=documento.id_documento,
        titulo=documento.titulo,
        total_fragmentos=len(fragmentos_crudos),
        pagina_maxima=max(f.pagina_fin for f in fragmentos_crudos),
        palabras_totales=sum(f.palabras for f in fragmentos_crudos),
    )
