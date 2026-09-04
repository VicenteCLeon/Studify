"""Script de prueba de generación adaptativa de microcápsulas RAG + VARK.

Prueba la generación de cápsulas con el LLM (DeepSeek) sobre los 4 objetivos
curados utilizando los fragmentos validados recientemente.
"""

from sqlalchemy import select

from studify.api.routers.capsules import get_cliente_llm
from studify.db.models import ObjetivoAprendizaje
from studify.db.session import SessionLocal
from studify.web.routers.teacher import _generar_capsula_pura

OBJETIVOS_CODIGOS = ["PROG-U1-01", "PROG-U1-02", "BD-U3-01", "BD-U3-02"]
CANALES_A_PROBAR = ["V", "A", "R", "K"]


def main():
    print("=== Prueba de Generacion Adaptativa de Microcapsulas (LLM + RAG + VARK) ===")

    cliente = get_cliente_llm()
    if not cliente:
        print("[ERR] No se pudo inicializar el cliente LLM. Revisa LLM_API_KEY en .env")
        return

    with SessionLocal() as db:
        for codigo in OBJETIVOS_CODIGOS:
            objetivo = db.scalar(
                select(ObjetivoAprendizaje).where(ObjetivoAprendizaje.codigo_objetivo == codigo)
            )
            if not objetivo:
                print(f"[ERR] No existe el objetivo {codigo}")
                continue

            print("\n==========================================================================")
            print(
                f"--- OBJETIVO: [{objetivo.codigo_objetivo}] {objetivo.asignatura} - {objetivo.tema}"
            )
            print("==========================================================================")

            for canal in CANALES_A_PROBAR:
                print(f"\n  > Generando capsula simulada para Canal VARK: {canal}...")
                resultado = _generar_capsula_pura(db, objetivo, canal, cliente)

                if resultado["error"]:
                    print(f"    [ERR] ERROR: {resultado['error']}")
                else:
                    capsula = resultado["capsula"]
                    print(f"    [EXITO] Titulo: '{capsula.titulo}'")
                    print(f"      - Modelo LLM: {resultado.get('modelo', 'deepseek-chat')}")
                    print(
                        f"      - Fragmentos RAG utilizados: {resultado.get('cant_fragmentos', 'N/A')}"
                    )
                    print(f"      - Concepto Central: {capsula.concepto_central[:100]}...")
                    print(f"      - Bloques VARK: {len(capsula.representacion_adaptativa)}")

                    if capsula.actividad:
                        pregunta_safe = str(capsula.actividad.pregunta).encode('ascii', 'replace').decode('ascii')
                        print(f"      - Mini-Quiz: '{pregunta_safe}'")
                        if hasattr(capsula.actividad, 'opciones') and capsula.actividad.opciones:
                            idx_corr = getattr(capsula.actividad, 'indice_correcta', 0)
                            corr_safe = str(capsula.actividad.opciones[idx_corr]).encode('ascii', 'replace').decode('ascii')
                            print(f"        Respuesta correcta: {corr_safe}")


if __name__ == "__main__":
    main()
