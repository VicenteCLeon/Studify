"""Exportación de los datos de la prueba de usuario, en modo solo lectura.

Genera, en una carpeta local ignorada por git (`data/exportar_prueba/<fecha-hora>/`):

    crudo/          datos identificables: NO compartir ni versionar
        intentos.csv        lo mismo que entrega /teacher/exportar/intentos.csv
        studify.dump        volcado completo de la BD (pg_dump -Fc)
        tabla_codigos.csv   id_estudiante ↔ código de participante ↔ correo
        version.json        commit, modelo, huellas del prompt y de las reglas
        SHA256SUMS.txt
    seudonimizado/  para el análisis: sin correos, nombres ni id_estudiante
        intentos.csv, participantes.csv, diagnosticos.csv, respuestas_vark.csv,
        configuraciones.csv, capsulas.csv, capsulas.jsonl, interacciones.csv,
        aceptaciones_legales.csv, version.json, [forms_*.csv], LEEME.txt
        SHA256SUMS.txt

Qué garantiza:
- La BD solo se lee: conexión con `default_transaction_read_only=on` y solo
  SELECT; el volcado es `pg_dump`, que no escribe. No se llama al LLM.
- No escribe fuera de `data/exportar_prueba/` (ni `.pyc`).
- Por pantalla solo se imprimen nombres de archivo, columnas y conteos.

**Código de participante.** `P-` + los primeros 10 hex de
HMAC-SHA256(clave, correo en minúsculas). Es estable entre corridas mientras no
cambie la clave (`data/exportar_prueba/clave_seudonimo.txt`, se crea una vez y
nunca se sobrescribe). Como depende del correo, el mismo código se puede
calcular sobre las respuestas de Google Forms (pre, post, encuesta) con
`--forms`, y el cruce se hace sin que el correo salga de `crudo/`. Si un
estudiante no tiene correo, el código se calcula sobre su id interno.

Uso:
    python scripts/exportar_prueba/exportar_prueba.py [--desde AAAA-MM-DD] [--hasta AAAA-MM-DD]
        [--forms ruta.csv [--columna-correo "Dirección de correo electrónico"]] ...
"""

from __future__ import annotations

import sys

sys.dont_write_bytecode = True

import argparse  # noqa: E402
import csv  # noqa: E402
import hashlib  # noqa: E402
import hmac  # noqa: E402
import io  # noqa: E402
import json  # noqa: E402
import re  # noqa: E402
import secrets  # noqa: E402
import shutil  # noqa: E402
import subprocess  # noqa: E402
from datetime import datetime  # noqa: E402
from decimal import Decimal  # noqa: E402
from pathlib import Path  # noqa: E402
from urllib.parse import urlsplit  # noqa: E402

RAIZ = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ / "src"))

from sqlalchemy import create_engine, text  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402

from studify.config import get_settings  # noqa: E402
from studify.rag import orchestrator  # noqa: E402
from studify.web.routers import teacher  # noqa: E402

BOM = chr(0xFEFF)  # marca UTF-8 que espera Excel, igual que el endpoint
DIR_BASE = RAIZ / "data" / "exportar_prueba"
ARCHIVO_CLAVE = DIR_BASE / "clave_seudonimo.txt"

# Archivos cuyo contenido determina el prompt y las reglas: su SHA-256 deja
# constancia de la versión en uso aunque haya cambios sin commitear.
ARCHIVOS_VERSIONADOS = (
    "src/studify/rag/prompts/maestro.py",
    "src/studify/rag/orchestrator.py",
    "src/studify/vark/rules.py",
    "src/studify/vark/hierarchy.py",
    "src/studify/vark/weighting.py",
    "src/studify/vark/scoring.py",
    "src/studify/generation/validator.py",
    "src/studify/generation/schemas.py",
    "src/studify/generation/generator.py",
)

# Columnas de Google Forms que identifican a la persona y no deben pasar al
# seudonimizado (se comparan sin mayúsculas ni tildes).
PATRON_COLUMNA_PERSONAL = re.compile(r"correo|e-?mail|nombre|apellido|rut\b|telefono|tel[eé]fono", re.I)


# --- Utilidades ----------------------------------------------------------------


def sha256_archivo(ruta: Path) -> str:
    h = hashlib.sha256()
    with ruta.open("rb") as f:
        for bloque in iter(lambda: f.read(1 << 20), b""):
            h.update(bloque)
    return h.hexdigest()


def escribir_sumas(carpeta: Path) -> None:
    lineas = [f"{sha256_archivo(p)}  {p.name}" for p in sorted(carpeta.iterdir())
              if p.is_file() and p.name != "SHA256SUMS.txt"]
    (carpeta / "SHA256SUMS.txt").write_text("\n".join(lineas) + "\n", encoding="utf-8", newline="\n")


def escribir_csv(ruta: Path, columnas: list[str], filas: list[dict]) -> None:
    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=columnas, lineterminator="\n", extrasaction="raise")
    w.writeheader()
    for f in filas:
        w.writerow({k: _celda(v) for k, v in f.items()})
    # BOM para que Excel lea bien los acentos, igual que el endpoint.
    ruta.write_text(BOM + buf.getvalue(), encoding="utf-8", newline="\n")


def _celda(v):
    if v is None:
        return ""
    if isinstance(v, (dict, list)):
        return json.dumps(v, ensure_ascii=False, sort_keys=True)
    if isinstance(v, datetime):
        return v.isoformat()
    if isinstance(v, Decimal):
        return f"{v:.2f}"
    if isinstance(v, bool):
        return "si" if v else "no"
    return v


def clave_seudonimo() -> bytes:
    DIR_BASE.mkdir(parents=True, exist_ok=True)
    if not ARCHIVO_CLAVE.exists():
        ARCHIVO_CLAVE.write_text(
            "# Clave de los códigos de participante. No borrar ni compartir: si se pierde,\n"
            "# los códigos cambian y ya no cruzan con exportaciones anteriores.\n"
            + secrets.token_hex(32) + "\n", encoding="utf-8", newline="\n")
    lineas = [ln.strip() for ln in ARCHIVO_CLAVE.read_text(encoding="utf-8").splitlines()
              if ln.strip() and not ln.startswith("#")]
    return bytes.fromhex(lineas[0])


def codigo_participante(clave: bytes, correo: str | None, id_estudiante: int | None = None) -> str:
    base = f"correo:{correo.strip().lower()}" if correo and correo.strip() else f"id:{id_estudiante}"
    return "P-" + hmac.new(clave, base.encode("utf-8"), hashlib.sha256).hexdigest()[:10]


def _git(*args: str) -> str:
    r = subprocess.run(["git", *args], cwd=RAIZ, capture_output=True, text=True, check=False)
    return r.stdout.strip()


# --- Lectura -------------------------------------------------------------------


def motor_solo_lectura():
    return create_engine(
        get_settings().database_url,
        connect_args={"options": "-c default_transaction_read_only=on -c statement_timeout=30000 "
                                 "-c lock_timeout=3000"},
    )


def consultar(sesion: Session, sql: str) -> list[dict]:
    return [dict(f._mapping) for f in sesion.execute(text(sql))]


def intentos_del_endpoint(sesion: Session, desde: str | None, hasta: str | None) -> bytes:
    """Llama a la misma función que atiende /teacher/exportar/intentos.csv."""
    respuesta = teacher.exportar_intentos(desde=desde, hasta=hasta, db=sesion)
    return respuesta.body


def volcar_bd(destino: Path, contenedor: str) -> str:
    """pg_dump en formato custom. Primero dentro del contenedor de Docker; si no, el local."""
    url = urlsplit(get_settings().database_url.replace("postgresql+psycopg://", "postgresql://", 1))
    usuario, base = url.username or "studify", (url.path or "/studify").lstrip("/")
    if shutil.which("docker"):
        with destino.open("wb") as f:
            r = subprocess.run(["docker", "exec", contenedor, "pg_dump", "-U", usuario, "-d", base,
                                "-Fc", "--no-owner"], stdout=f, stderr=subprocess.PIPE, check=False)
        if r.returncode == 0:
            return f"docker exec {contenedor} pg_dump -Fc --no-owner"
        destino.unlink(missing_ok=True)
    if shutil.which("pg_dump"):
        url_pg = get_settings().database_url.replace("postgresql+psycopg://", "postgresql://", 1)
        with destino.open("wb") as f:
            subprocess.run(["pg_dump", "-Fc", "--no-owner", "-d", url_pg], stdout=f, check=True)
        return "pg_dump local -Fc --no-owner"
    raise SystemExit("No se pudo volcar la BD: no hay contenedor accesible ni pg_dump local.")


def info_version(sesion: Session, desde: str | None, hasta: str | None, metodo_volcado: str) -> dict:
    ajustes = get_settings()
    estado = _git("status", "--porcelain")
    return {
        "exportado_en": datetime.now().astimezone().isoformat(timespec="seconds"),
        "filtro_intentos": {"desde": desde, "hasta": hasta},
        "codigo": {
            "commit": _git("rev-parse", "HEAD"),
            "rama": _git("rev-parse", "--abbrev-ref", "HEAD"),
            "cambios_sin_commitear": bool(estado),
            "archivos_con_cambios": [ln[3:] for ln in estado.splitlines()],
        },
        "modelo": {
            "configurado": ajustes.llm_model,
            "temperatura": ajustes.llm_temperature,
            "reintentos_de_reparacion": ajustes.llm_max_repair_attempts,
            "en_capsulas_guardadas": {f["modelo_llm"] or "no registrado": f["n"] for f in consultar(
                sesion, "SELECT modelo_llm, count(*) AS n FROM microcapsula_generada "
                        "GROUP BY 1 ORDER BY 1")},
        },
        "prompt": {
            "huella_plantillas_experimental": orchestrator._huella_plantillas(),
            "huella_plantillas_control": orchestrator._huella_plantillas_neutras(),
            "palabras_min": ajustes.capsula_min_palabras,
            "palabras_max_prompt": ajustes.capsula_max_palabras,
            "palabras_max_aceptadas_validador": ajustes.capsula_max_palabras_aceptadas,
        },
        "reglas_y_validacion_sha256": {p: sha256_archivo(RAIZ / p) for p in ARCHIVOS_VERSIONADOS},
        "bd": {
            "migracion_alembic": consultar(sesion, "SELECT version_num FROM alembic_version")[0]["version_num"],
            "volcado": metodo_volcado,
        },
    }


# --- Seudonimización -----------------------------------------------------------


def exportar_seudonimizado(sesion: Session, clave: bytes, intentos_csv: bytes, destino: Path,
                           crudo: Path) -> dict[str, list[str]]:
    est = consultar(sesion, "SELECT * FROM estudiante ORDER BY id_estudiante")
    codigo = {e["id_estudiante"]: codigo_participante(clave, e["google_email"], e["id_estudiante"]) for e in est}

    # Tabla de correspondencia: solo en crudo/.
    escribir_csv(crudo / "tabla_codigos.csv", ["id_estudiante", "codigo_participante", "rol", "google_email"],
                 [{"id_estudiante": e["id_estudiante"], "codigo_participante": codigo[e["id_estudiante"]],
                   "rol": e["rol"], "google_email": e["google_email"]} for e in est])

    tablas: dict[str, tuple[list[str], list[dict]]] = {}

    filas = list(csv.DictReader(io.StringIO(intentos_csv.decode("utf-8").lstrip(BOM))))
    cols = ["codigo_participante"] + [c for c in (filas[0].keys() if filas else teacher.COLUMNAS_INTENTOS)
                                      if c != "id_estudiante"]
    tablas["intentos.csv"] = (cols, [{"codigo_participante": codigo[int(f.pop("id_estudiante"))], **f}
                                     for f in filas])

    tablas["participantes.csv"] = (
        ["codigo_participante", "rol", "rango_etario", "genero", "carrera", "ano_ingreso", "fecha_registro",
         "origen_registro", "voz_genero", "voz_modo", "entra_con_google"],
        [{"codigo_participante": codigo[e["id_estudiante"]], "rol": e["rol"], "rango_etario": e["rango_etario"],
          "genero": e["genero"], "carrera": e["carrera"], "ano_ingreso": e["ano_ingreso"],
          "fecha_registro": e["fecha_registro"], "origen_registro": e["origen_registro"],
          "voz_genero": e["voz_genero"], "voz_modo": e["voz_modo"],
          "entra_con_google": e["google_sub"] is not None} for e in est])

    diag = consultar(sesion, "SELECT * FROM diagnostico_vark ORDER BY id_diagnostico")
    tablas["diagnosticos.csv"] = (
        ["codigo_participante", "id_diagnostico", "porcentaje_v", "porcentaje_a", "porcentaje_r",
         "porcentaje_k", "fecha_diagnostico"],
        [{"codigo_participante": codigo[d["id_estudiante"]], **{k: d[k] for k in (
            "id_diagnostico", "porcentaje_v", "porcentaje_a", "porcentaje_r", "porcentaje_k",
            "fecha_diagnostico")}} for d in diag])

    resp = consultar(sesion, "SELECT id_diagnostico, num_pregunta, alternativa, canal_mapeado "
                             "FROM respuesta_vark ORDER BY id_diagnostico, num_pregunta, alternativa")
    tablas["respuestas_vark.csv"] = (["id_diagnostico", "num_pregunta", "alternativa", "canal_mapeado"], resp)

    conf = consultar(sesion, "SELECT * FROM configuracion_contenido ORDER BY id_config")
    tablas["configuraciones.csv"] = (list(conf[0].keys()) if conf else ["id_config"], conf)

    caps = consultar(sesion, """
        SELECT m.id_capsula, m.id_estudiante, o.codigo_objetivo, m.id_config, m.id_fragmento_fuente,
               m.titulo, m.estado_validacion, m.fecha_generacion, m.huella_generacion, m.modelo_llm,
               m.contenido_json, m.mini_quiz_json
        FROM microcapsula_generada m JOIN objetivo_aprendizaje o USING (id_objetivo)
        ORDER BY m.id_capsula""")
    cols_caps = ["id_capsula", "codigo_participante", "codigo_objetivo", "id_config", "id_fragmento_fuente",
                 "titulo", "estado_validacion", "fecha_generacion", "huella_generacion", "modelo_llm"]
    tablas["capsulas.csv"] = (cols_caps, [{"codigo_participante": codigo[c["id_estudiante"]],
                                           **{k: c[k] for k in cols_caps if k != "codigo_participante"}}
                                          for c in caps])
    # El contenido generado no tiene datos personales; va aparte, una cápsula por línea.
    (destino / "capsulas.jsonl").write_text("".join(
        json.dumps({"id_capsula": c["id_capsula"], "contenido_json": c["contenido_json"],
                    "mini_quiz_json": c["mini_quiz_json"]}, ensure_ascii=False, sort_keys=True) + "\n"
        for c in caps), encoding="utf-8", newline="\n")

    inter = consultar(sesion, """
        SELECT i.*, m.id_estudiante FROM interaccion_quiz i
        JOIN microcapsula_generada m USING (id_capsula) ORDER BY i.id_interaccion""")
    cols_int = ["id_interaccion", "id_capsula", "codigo_participante", "numero_intento",
                "alternativa_seleccionada", "es_correcta", "aciertos", "total_preguntas", "detalle_json",
                "fecha_respuesta"]
    tablas["interacciones.csv"] = (cols_int, [{"codigo_participante": codigo[i["id_estudiante"]],
                                               **{k: i[k] for k in cols_int if k != "codigo_participante"}}
                                              for i in inter])

    acep = consultar(sesion, "SELECT * FROM aceptacion_legal ORDER BY id_aceptacion")
    tablas["aceptaciones_legales.csv"] = (
        ["codigo_participante", "documento", "version", "aceptado_en"],
        [{"codigo_participante": codigo[a["id_estudiante"]], "documento": a["documento"],
          "version": a["version"], "aceptado_en": a["aceptado_en"]} for a in acep])

    for nombre, (columnas, filas_t) in tablas.items():
        escribir_csv(destino / nombre, columnas, filas_t)
    return {n: c for n, (c, _) in tablas.items()} | {"capsulas.jsonl": ["id_capsula", "contenido_json",
                                                                         "mini_quiz_json"]}


def seudonimizar_forms(ruta: Path, columna_correo: str | None, clave: bytes, codigos_bd: set[str],
                       destino: Path) -> tuple[str, list[str], int, int, list[str]]:
    texto = ruta.read_text(encoding="utf-8-sig")
    lector = csv.DictReader(io.StringIO(texto))
    columnas = lector.fieldnames or []
    col = columna_correo or next((c for c in columnas if re.search(r"correo|e-?mail", c, re.I)), None)
    if col is None or col not in columnas:
        raise SystemExit(f"{ruta.name}: no encuentro la columna de correo; indícala con --columna-correo.")
    descartadas = [c for c in columnas if PATRON_COLUMNA_PERSONAL.search(c)]
    quedan = [c for c in columnas if c not in descartadas]
    filas, cruzan = [], 0
    for f in lector:
        cod = codigo_participante(clave, f[col])
        cruzan += cod in codigos_bd
        filas.append({"codigo_participante": cod, **{c: f[c] for c in quedan}})
    nombre = f"forms_{re.sub(r'[^A-Za-z0-9_-]+', '_', ruta.stem)}.csv"
    escribir_csv(destino / nombre, ["codigo_participante", *quedan], filas)
    return nombre, ["codigo_participante", *quedan], len(filas), cruzan, descartadas


LEEME = """Datos seudonimizados de la prueba de usuario de Studify.

- codigo_participante reemplaza a id_estudiante, nombre y correo. Es estable entre exportaciones mientras
  no cambie data/exportar_prueba/clave_seudonimo.txt; la correspondencia está solo en ../crudo/tabla_codigos.csv.
- Seudonimizado no es anónimo: carrera, rango_etario, genero y fecha_registro combinados pueden identificar a
  alguien en una cohorte pequeña. genero es un dato sensible. Compartir solo con el equipo y la profesora guía.
- version.json dice con qué código, modelo, prompt y reglas se generaron los datos.
- SHA256SUMS.txt permite verificar que ningún archivo cambió: sha256sum -c SHA256SUMS.txt
"""


# --- Principal -----------------------------------------------------------------


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--desde", help="primer día de intentos (AAAA-MM-DD, hora de Chile)")
    ap.add_argument("--hasta", help="último día de intentos (AAAA-MM-DD, hora de Chile)")
    ap.add_argument("--contenedor", default="studify-db", help="contenedor de Postgres para pg_dump")
    ap.add_argument("--forms", action="append", default=[], type=Path,
                    help="CSV exportado de Google Forms a seudonimizar con el mismo código (repetible)")
    ap.add_argument("--columna-correo", help="nombre exacto de la columna de correo en los CSV de Forms")
    args = ap.parse_args()
    sys.stdout.reconfigure(encoding="utf-8")

    clave = clave_seudonimo()
    salida = DIR_BASE / datetime.now().strftime("%Y%m%d-%H%M%S")
    crudo, seud = salida / "crudo", salida / "seudonimizado"
    crudo.mkdir(parents=True)
    seud.mkdir()

    motor = motor_solo_lectura()
    try:
        with Session(motor) as sesion:
            intentos = intentos_del_endpoint(sesion, args.desde, args.hasta)
            (crudo / "intentos.csv").write_bytes(intentos)
            metodo = volcar_bd(crudo / "studify.dump", args.contenedor)
            version = info_version(sesion, args.desde, args.hasta, metodo)
            columnas = exportar_seudonimizado(sesion, clave, intentos, seud, crudo)
            codigos_bd = {f["codigo_participante"] for f in csv.DictReader(io.StringIO(
                (crudo / "tabla_codigos.csv").read_text(encoding="utf-8-sig")))}
            sesion.rollback()
    finally:
        motor.dispose()

    for destino in (crudo, seud):
        (destino / "version.json").write_text(json.dumps(version, ensure_ascii=False, indent=2) + "\n",
                                              encoding="utf-8", newline="\n")
    forms = [seudonimizar_forms(r, args.columna_correo, clave, codigos_bd, seud) for r in args.forms]
    (seud / "LEEME.txt").write_text(LEEME, encoding="utf-8", newline="\n")
    escribir_sumas(crudo)
    escribir_sumas(seud)

    # Solo nombres, tamaños, columnas y conteos: nada de datos personales.
    print(f"Exportación en {salida.relative_to(RAIZ)}")
    for carpeta in (crudo, seud):
        print(f"\n{carpeta.name}/")
        for p in sorted(carpeta.iterdir()):
            print(f"  {p.name:<28} {p.stat().st_size:>10,} B")
    print("\nColumnas del seudonimizado:")
    for nombre, cols in columnas.items():
        print(f"  {nombre}: {', '.join(cols)}")
    for nombre, cols, n, cruzan, descartadas in forms:
        print(f"  {nombre}: {', '.join(cols)}  ({n} filas, {cruzan} cruzan con la BD; "
              f"columnas personales descartadas: {len(descartadas)})")
    print(f"\ncommit {version['codigo']['commit'][:12]} (cambios sin commitear: "
          f"{version['codigo']['cambios_sin_commitear']}), modelo {version['modelo']['configurado']}, "
          f"huella prompt {version['prompt']['huella_plantillas_experimental'][:12]}")


if __name__ == "__main__":
    main()
