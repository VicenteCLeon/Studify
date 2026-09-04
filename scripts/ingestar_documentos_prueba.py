"""Ingiere automáticamente los 4 PDFs de prueba en la base de datos de Studify.

Asigna los tipos de documento y asignaturas correspondientes, dejándolos en
estado 'pendiente' de curación en el Panel Docente.
"""

from pathlib import Path

from studify.db.session import SessionLocal
from studify.knowledge.ingest import DocumentoDuplicado, ingerir

DIR_PDF = Path("data/documentos_prueba_pdf")

DOCUMENTOS_CONFIG = [
    {
        "archivo": "PROG_U1_01_Variables_y_Tipos_de_Datos.pdf",
        "titulo": "Variables y Tipos de Datos Primitivos",
        "asignatura": "Introducción a la Programación",
        "tipo_documento": "apunte",
        "origen": "Material Docente Institucional",
        "version": "1.0",
    },
    {
        "archivo": "PROG_U1_02_Estructuras_de_Control.pdf",
        "titulo": "Estructuras de Control Condicionales e Iterativas",
        "asignatura": "Introducción a la Programación",
        "tipo_documento": "apunte",
        "origen": "Material Docente Institucional",
        "version": "1.0",
    },
    {
        "archivo": "BD_U3_01_Primera_Forma_Normal.pdf",
        "titulo": "Guía de Normalización: Primera Forma Normal (1FN)",
        "asignatura": "Bases de Datos",
        "tipo_documento": "guia",
        "origen": "Material Docente Institucional",
        "version": "1.0",
    },
    {
        "archivo": "BD_U3_02_Dependencias_Funcionales.pdf",
        "titulo": "Teoría de Dependencias Funcionales y Cierre de Atributos",
        "asignatura": "Bases de Datos",
        "tipo_documento": "apunte",
        "origen": "Material Docente Institucional",
        "version": "1.0",
    },
]


def main():
    print("Iniciando ingesta de documentos de prueba...")
    with SessionLocal() as db:
        for doc_cfg in DOCUMENTOS_CONFIG:
            ruta_pdf = DIR_PDF / doc_cfg["archivo"]
            if not ruta_pdf.exists():
                print(f"[ERR] No existe {ruta_pdf}")
                continue

            try:
                res = ingerir(
                    db,
                    ruta_pdf,
                    titulo=doc_cfg["titulo"],
                    asignatura=doc_cfg["asignatura"],
                    tipo_documento=doc_cfg["tipo_documento"],
                    origen=doc_cfg["origen"],
                    version=doc_cfg["version"],
                )
                print(
                    f"[OK] Ingerido '{res.titulo}' (ID Doc: {res.id_documento}, Fragmentos: {res.total_fragmentos}, Palabras: {res.palabras_totales})"
                )
            except DocumentoDuplicado as dup:
                print(f"[OMITIDO] {dup}")
            except Exception as e:
                print(f"[ERR] Error al ingerir {doc_cfg['archivo']}: {e}")


if __name__ == "__main__":
    main()
