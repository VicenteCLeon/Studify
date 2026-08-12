"""Batería de evaluación técnica (Bake-off de modelos) para la Fase 5.

Este script automatiza la generación de microcápsulas variando el modelo de lenguaje
y el perfil VARK, midiendo el porcentaje de JSON válido, latencia y uso de reintentos.
Exporta los resultados a un CSV para su análisis posterior y evaluación humana ciega.
"""

import argparse
import csv
import logging
import os
import sys
import time
from decimal import Decimal
from pathlib import Path

# Permite ejecutar el script sin instalar el paquete
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from studify.db.session import SessionLocal
from studify.db.models import ObjetivoAprendizaje
from studify.rag.retriever import recuperar
from studify.rag.orchestrator import construir
from studify.vark.scoring import PerfilVark
from studify.vark.rules import aplicar_reglas
from studify.vark.hierarchy import derivar
from studify.generation.generator import ClienteOpenAILike, generar, ErrorGeneracion
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

# Definimos 4 perfiles VARK puros (100% de dominancia en cada canal)
PERFILES = {
    "V": PerfilVark(v=Decimal("100"), a=Decimal("0"), r=Decimal("0"), k=Decimal("0")),
    "A": PerfilVark(v=Decimal("0"), a=Decimal("100"), r=Decimal("0"), k=Decimal("0")),
    "R": PerfilVark(v=Decimal("0"), a=Decimal("0"), r=Decimal("100"), k=Decimal("0")),
    "K": PerfilVark(v=Decimal("0"), a=Decimal("0"), r=Decimal("0"), k=Decimal("100")),
}

# Modelos a evaluar con sus respectivas URLs.
# El script buscará la key en variables de entorno específicas primero,
# y si no, caerá en la global LLM_API_KEY.
MODELOS = [
    {
        "nombre": "deepseek-chat",
        "base_url": "https://api.deepseek.com/v1",
        "env_key": "DEEPSEEK_API_KEY",
    },
    {
        "nombre": "qwen-plus",
        "base_url": "https://dashscope-intl.aliyuncs.com/compatible-mode/v1",
        "env_key": "QWEN_API_KEY",
    },
    {
        "nombre": "glm-4-plus",
        "base_url": "https://open.bigmodel.cn/api/paas/v4",
        "env_key": "GLM_API_KEY",
    },
]

def main():
    parser = argparse.ArgumentParser(description="Ejecuta el bake-off de modelos.")
    parser.add_argument("--dry-run", action="store_true", help="Muestra la matriz de pruebas sin ejecutar a los LLM")
    parser.add_argument("--out", type=Path, default=Path("data/resultados_evaluacion.csv"), help="Archivo CSV de salida")
    args = parser.parse_args()

    # 1. Obtener objetivo con fragmentos
    with SessionLocal() as db:
        # Buscamos el primer objetivo que tenga fragmentos validados asociados
        # Para ser rápidos en SQLite/Postgres, podemos simplemente listar y probar recuperar
        objetivos = db.query(ObjetivoAprendizaje).all()
        objetivo_seleccionado = None
        fragmentos_seleccionados = []
        
        for obj in objetivos:
            frags = recuperar(db, id_objetivo=obj.id_objetivo)
            if frags:
                objetivo_seleccionado = obj
                fragmentos_seleccionados = frags
                break
        
        if not objetivo_seleccionado:
            logger.error("No se encontró ningún Objetivo de Aprendizaje con fragmentos validados. Entra a /teacher/curation y valida al menos uno.")
            sys.exit(1)

        logger.info(f"Objetivo seleccionado: {objetivo_seleccionado.codigo_objetivo} con {len(fragmentos_seleccionados)} fragmentos validados.")

    if args.dry_run:
        logger.info("=== DRY RUN: Matriz de Pruebas ===")
        for modelo_info in MODELOS:
            for nombre_perfil in PERFILES:
                logger.info(f"Modelo: {modelo_info['nombre']:<15} | Perfil: {nombre_perfil}")
        sys.exit(0)

    # 2. Ejecutar la batería
    resultados_csv = []
    
    for modelo_info in MODELOS:
        modelo = modelo_info["nombre"]
        base_url = modelo_info["base_url"]
        api_key = os.environ.get(modelo_info["env_key"]) or os.environ.get("LLM_API_KEY")
        
        if not api_key:
            logger.warning(f"Saltando {modelo} porque no se encontró {modelo_info['env_key']} ni LLM_API_KEY")
            continue

        try:
            cliente = ClienteOpenAILike(modelo=modelo, base_url=base_url, api_key=api_key)
        except Exception as e:
            logger.warning(f"Error instanciando cliente para {modelo}: {e}")
            continue

        for nombre_perfil, perfil_vark in PERFILES.items():
            logger.info(f"Generando con {modelo} para perfil {nombre_perfil}...")
            
            configuracion = aplicar_reglas(perfil_vark)
            jerarquia = derivar(perfil_vark)
            
            # El RAG real prioriza por el canal primario del estudiante
            with SessionLocal() as db:
                frags = recuperar(db, id_objetivo=objetivo_seleccionado.id_objetivo, canal_primario=jerarquia.canal_primario)
            
            prompt_maestro = construir(
                objetivo=objetivo_seleccionado,
                fragmentos=frags,
                config=configuracion,
                modelo=modelo,
            )

            # Ejecutar con medición de tiempo
            inicio = time.perf_counter()
            try:
                res_validacion = generar(prompt_maestro, cliente=cliente)
                fin = time.perf_counter()
                latencia = round(fin - inicio, 2)
                
                # Extraer métricas si el resultado fue exitoso
                valido_primera = res_validacion.valida_al_primer_intento
                reintentos = res_validacion.intentos - 1
                palabras = res_validacion.metricas.get("palabras_contenido", 0)
                error_msg = ""
            except Exception as e:
                fin = time.perf_counter()
                latencia = round(fin - inicio, 2)
                valido_primera = False
                reintentos = 0
                palabras = 0
                error_msg = str(e)
            
            resultados_csv.append({
                "modelo": modelo,
                "perfil": nombre_perfil,
                "id_objetivo": objetivo_seleccionado.id_objetivo,
                "latencia_seg": latencia,
                "intentos_usados": reintentos,
                "valido_primer_intento": "Si" if valido_primera else "No",
                "palabras_contenido": palabras,
                "errores": error_msg,
                "rubrica_fidelidad": "",
                "rubrica_calidad_espanol": "",
            })

    # 3. Guardar resultados
    if resultados_csv:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        campos = list(resultados_csv[0].keys())
        with args.out.open("w", encoding="utf-8-sig", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=campos)
            writer.writeheader()
            writer.writerows(resultados_csv)
        logger.info(f"Batería completada. {len(resultados_csv)} resultados guardados en {args.out}")
    else:
        logger.warning("No se generó ningún resultado. Revisa las API Keys.")

if __name__ == "__main__":
    main()
