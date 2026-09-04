"""Script de curación automática de fragmentos de prueba.

Relaciona cada documento ingerido con su Objetivo de Aprendizaje correspondiente
y aprueba (valida) todos sus fragmentos para dejarlos disponibles en el RAG.
"""

from sqlalchemy import select

from studify.db.models import DocumentoFuente, Fragmento, ObjetivoAprendizaje
from studify.db.session import SessionLocal
from studify.knowledge.curation import resumen_documento, validar

MAPEO_DOC_OBJETIVO = {
    "Variables y Tipos de Datos Primitivos": "PROG-U1-01",
    "Estructuras de Control Condicionales e Iterativas": "PROG-U1-02",
    "Guía de Normalización: Primera Forma Normal (1FN)": "BD-U3-01",
    "Teoría de Dependencias Funcionales y Cierre de Atributos": "BD-U3-02",
}


def main():
    print("=== Curación y Validación de Fragmentos de Prueba ===")

    with SessionLocal() as db:
        # 1. Cargar catálogo de objetivos existentes por su clave natural (codigo_objetivo)
        objetivos = {
            obj.codigo_objetivo: obj for obj in db.scalars(select(ObjetivoAprendizaje)).all()
        }

        print("\nObjetivos disponibles en la BD:")
        for cod, obj in objetivos.items():
            print(f"  - [{cod}] ID: {obj.id_objetivo} -> {obj.asignatura}: {obj.tema}")

        # 2. Buscar los documentos cargados
        documentos = db.scalars(select(DocumentoFuente)).all()
        print(f"\nDocumentos en la BD: {len(documentos)}")

        validados_totales = 0

        for doc in documentos:
            codigo_obj_esperado = MAPEO_DOC_OBJETIVO.get(doc.titulo)
            if not codigo_obj_esperado:
                print(f"\n[OMITIDO] Documento sin mapeo directo: '{doc.titulo}'")
                continue

            objetivo_dest = objetivos.get(codigo_obj_esperado)
            if not objetivo_dest:
                print(
                    f"\n[ERR] No se encontró el objetivo '{codigo_obj_esperado}' para '{doc.titulo}'"
                )
                continue

            print(f"\nProcesando Documento ID {doc.id_documento}: '{doc.titulo}'")
            print(
                f"  -> Asignando a Objetivo ID {objetivo_dest.id_objetivo} [{objetivo_dest.codigo_objetivo}]"
            )

            fragmentos_pendientes = db.scalars(
                select(Fragmento).where(
                    Fragmento.id_documento == doc.id_documento,
                    Fragmento.estado_validacion == "pendiente",
                )
            ).all()

            validos_doc = 0
            for frag in fragmentos_pendientes:
                try:
                    validar(db, frag.id_fragmento, id_objetivo=objetivo_dest.id_objetivo)
                    validos_doc += 1
                except Exception as e:
                    print(f"    [ERR] Error al validar fragmento {frag.id_fragmento}: {e}")

            validados_totales += validos_doc
            resumen = resumen_documento(db, doc.id_documento)
            print(f"  [OK] Validados {validos_doc} fragmentos nuevos. Resumen Doc: {resumen}")

        print(f"\n=== Proceso completado. Total fragmentos validados: {validados_totales} ===")


if __name__ == "__main__":
    main()
