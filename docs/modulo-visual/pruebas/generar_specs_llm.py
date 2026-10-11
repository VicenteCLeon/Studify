"""Paso LLM del módulo Visual: DeepSeek genera la especificación del esquema.

Es la prueba que le faltaba a `analisis-modulo-visual.md`: las especificaciones
de `specs/` se redactaron a mano. Este script le pide a DeepSeek una
especificación por objetivo, la valida, la repara si hace falta y la dibuja con
el mismo render determinístico de `generar_pruebas.py`.

- **Cliente:** el del proyecto (`ClienteOpenAILike`, vía `ClienteMedido`): misma
  temperatura, mismo modo JSON y mismo `max_tokens`.
- **Prompt:** el de `studify.rag.prompts.visual`. Con `--prompt informe` usa el
  texto del §3.2 del informe, que es el de la primera tanda (sin la regla de los
  títulos de sección). El esquema JSON se lee siempre del §3.1.
- **Salida:** `specs_llm/<destino>/` y `resultados/llm/<destino>/`, con el prompt
  enviado en `prompts_usados/`. La primera tanda está en la raíz de `specs_llm/`
  y el script no la pisa: una tanda nueva pide `--destino`.
- **Material:** los fragmentos validados de la base, con `retriever.recuperar`.
- **Validación:** el esquema JSON del §3.1 y, después, las reglas por código.
  Si falla, hasta `LLM_MAX_REPAIR_ATTEMPTS` reparaciones, como `generator.py`.

Uso (desde la raíz del repo, con Postgres levantado):

    python docs/modulo-visual/pruebas/generar_specs_llm.py --plan
    python docs/modulo-visual/pruebas/generar_specs_llm.py --destino v2
    python docs/modulo-visual/pruebas/generar_specs_llm.py --destino v2 --solo BD-U3-01

Sin `--plan` hace llamadas de pago a DeepSeek. `deepseek_medido.py` lleva la
cuenta y se detiene antes de pasar el tope autorizado.
"""

import argparse
import csv
import json
import logging
import os
import re
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

AQUI = Path(__file__).resolve().parent
RAIZ = AQUI.parents[2]
# `Settings` busca el `.env` en el directorio de trabajo.
os.chdir(RAIZ)
sys.path.insert(0, str(AQUI))

import generar_pruebas as base  # noqa: E402
from deepseek_medido import TOPES_USD, ClienteMedido, TopeSuperado, gastado  # noqa: E402
from sqlalchemy import select  # noqa: E402

from studify.config import get_settings  # noqa: E402
from studify.db.models import ObjetivoAprendizaje  # noqa: E402
from studify.db.session import SessionLocal  # noqa: E402
from studify.generation.generator import Mensaje  # noqa: E402
from studify.generation.validator import ErrorFormatoJSON, extraer_json  # noqa: E402
from studify.rag import prompts, retriever  # noqa: E402
from studify.rag.prompts import visual  # noqa: E402

INFORME = AQUI.parent / "analisis-modulo-visual.md"
OBJETIVOS_CSV = RAIZ / "data" / "objetivos.csv"
SPECS_LLM = AQUI / "specs_llm"
SVG_LLM = AQUI / "resultados" / "llm"
REGISTRO = SPECS_LLM / "registro.json"

CORRIDAS = 3


# --- Prompt y esquema ----------------------------------------------------------------


def _bloques(seccion: str, lenguaje: str) -> list[str]:
    """Los bloques de código de una sección `### N.M` del informe, en orden."""
    texto = INFORME.read_text(encoding="utf-8")
    inicio = texto.index(f"### {seccion} ")
    fin = texto.index("\n### ", inicio + 1)
    return re.findall(rf"```{lenguaje}\n(.*?)\n```", texto[inicio:fin], flags=re.DOTALL)


def cargar_contrato(prompt: str = "modulo") -> tuple[dict, str, str, str]:
    """(esquema, texto del esquema, prompt de sistema, plantilla de usuario).

    `modulo` es el prompt vigente, el de `rag/prompts/visual.py`. `informe` es
    el texto del §3.2, con el que se generó la primera tanda.
    """
    (esquema_texto,) = _bloques("3.1", "json")
    if prompt == "informe":
        sistema, usuario = _bloques("3.2", "text")
        usuario = usuario.replace("{fragmentos, cada uno con su id_fragmento}", "{fragmentos}")
    else:
        sistema, usuario = visual.SISTEMA, visual.USUARIO.template
    return json.loads(esquema_texto), esquema_texto, sistema, usuario


def armar_usuario(plantilla: str, objetivo, fragmentos, esquema_texto: str) -> str:
    """Rellena la plantilla. Los fragmentos van con el formato de las cápsulas."""
    material = "\n".join(
        prompts.FRAGMENTO.format(
            id_fragmento=f.id_fragmento, cita=f.cita, tipo=f.tipo, texto=f.texto.strip()
        )
        for f in fragmentos
    )
    relleno = {
        "{asignatura}": objetivo.asignatura,
        "{unidad}": objetivo.unidad,
        "{tema}": objetivo.tema,
        "{fragmentos}": material,
        "{esquema_json}": esquema_texto,
    }
    for marca, valor in relleno.items():
        if marca not in plantilla:
            raise SystemExit(f"la plantilla ya no tiene el marcador {marca}")
        plantilla = plantilla.replace(marca, valor)
    return plantilla


# --- Validación --------------------------------------------------------------------

_TIPOS_JSON = {"object": dict, "array": list, "string": str, "integer": int}


def validar_esquema(valor, esquema: dict, ruta: str = "") -> list[str]:
    """JSON Schema, solo con las palabras clave que usa el §3.1.

    El venv del proyecto no trae `jsonschema` y agregar una dependencia para
    una prueba no se justifica: el esquema usa nueve palabras clave.
    """
    donde = ruta or "la raíz"
    if "const" in esquema and valor != esquema["const"]:
        return [f"`{donde}` debe ser {esquema['const']!r} y llegó {valor!r}"]
    if "enum" in esquema and valor not in esquema["enum"]:
        return [f"`{donde}` debe ser uno de {esquema['enum']} y llegó {valor!r}"]
    tipo = esquema.get("type")
    if tipo and (not isinstance(valor, _TIPOS_JSON[tipo]) or isinstance(valor, bool)):
        return [f"`{donde}` debe ser de tipo {tipo} y llegó {type(valor).__name__}"]

    errores: list[str] = []
    if isinstance(valor, str) and "pattern" in esquema and not re.search(esquema["pattern"], valor):
        errores.append(f"`{donde}` no cumple el patrón {esquema['pattern']} (llegó {valor!r})")
    if isinstance(valor, dict):
        for clave in esquema.get("required", []):
            if clave not in valor:
                errores.append(f"falta el campo obligatorio `{ruta + '.' if ruta else ''}{clave}`")
        for clave, sub in esquema.get("properties", {}).items():
            if clave in valor:
                errores += validar_esquema(valor[clave], sub, f"{ruta}.{clave}" if ruta else clave)
    if isinstance(valor, list):
        if len(valor) < esquema.get("minItems", 0):
            errores.append(f"`{donde}` tiene {len(valor)} elementos; mínimo {esquema['minItems']}")
        if len(valor) > esquema.get("maxItems", len(valor)):
            errores.append(f"`{donde}` tiene {len(valor)} elementos; máximo {esquema['maxItems']}")
        if "items" in esquema:
            for i, item in enumerate(valor):
                errores += validar_esquema(item, esquema["items"], f"{ruta}[{i}]")
    return errores


def _tiene_ciclo(ids: list[str], aristas: list[tuple[str, str]]) -> bool:
    entrantes = dict.fromkeys(ids, 0)
    for _, b in aristas:
        entrantes[b] += 1
    cola = [i for i in ids if entrantes[i] == 0]
    vistos = 0
    while cola:
        actual = cola.pop()
        vistos += 1
        for a, b in aristas:
            if a == actual:
                entrantes[b] -= 1
                if entrantes[b] == 0:
                    cola.append(b)
    return vistos != len(ids)


def validar_reglas(spec: dict, ids_entregados: set[int]) -> tuple[list[str], list[str]]:
    """Las reglas que el esquema no puede expresar: (errores, advertencias).

    Los errores rechazan la especificación y van al bucle de reparación. Las
    advertencias no: describen algo que el render actual resuelve mal o que
    conviene mirar, y quedan en el registro.
    """
    errores = base.validar(spec)
    advertencias: list[str] = []
    tipo = spec["tipo_de_diagrama"]
    nodos = spec["nodos"]
    ids = [n["id"] for n in nodos]
    etiqueta = {n["id"]: n["etiqueta"] for n in nodos}
    aristas = [
        (r["desde"], r["hacia"])
        for r in spec["relaciones"]
        if r["desde"] in ids and r["hacia"] in ids
    ]

    principales = [n["id"] for n in nodos if n.get("rol") == "principal"]
    if len(principales) != 1:
        errores.append(
            f"debe haber exactamente un nodo con rol `principal` y hay {len(principales)}"
        )

    if tipo == "jerarquia":
        padres: dict[str, list[str]] = {i: [] for i in ids}
        for a, b in aristas:
            padres[b].append(a)
        for i, p in padres.items():
            if len(p) > 1:
                errores.append(
                    f"en una jerarquía cada nodo tiene un solo padre: «{etiqueta[i]}» ({i}) "
                    f"tiene {len(p)}"
                )
        if _tiene_ciclo(ids, aristas):
            errores.append("una jerarquía no puede tener ciclos entre sus relaciones")
        raices = [i for i, p in padres.items() if not p]
        if len(raices) > 1:
            advertencias.append(f"la jerarquía tiene {len(raices)} raíces: {raices}")

    if tipo == "ciclo":
        salientes = {i: [b for a, b in aristas if a == i] for i in ids}
        entrantes = {i: [a for a, b in aristas if b == i] for i in ids}
        cerrado = all(len(salientes[i]) == 1 and len(entrantes[i]) == 1 for i in ids)
        if cerrado:
            actual, recorridos = ids[0], [ids[0]]
            while (actual := salientes[actual][0]) != ids[0] and len(recorridos) <= len(ids):
                recorridos.append(actual)
            cerrado = len(recorridos) == len(ids)
            if cerrado and recorridos != ids:
                advertencias.append("el ciclo no sigue el orden de `nodos`: las flechas se cruzan")
        if not cerrado:
            errores.append(
                "un ciclo debe cerrarse: cada nodo con exactamente una relación de salida y "
                "una de entrada, y la última etapa vuelve a la primera"
            )

    if tipo in ("flujo", "linea_de_tiempo"):
        consecutivas = set(zip(ids, ids[1:], strict=False))
        for a, b in aristas:
            if (a, b) not in consecutivas:
                advertencias.append(
                    f"relación {a} → {b} entre pasos no consecutivos: el render no la dibuja"
                )
        for a, b in consecutivas:
            if (a, b) not in aristas:
                advertencias.append(f"falta la relación {a} → {b} entre pasos consecutivos")

    fuentes = spec.get("fuentes")
    if not fuentes:
        advertencias.append("no declara `fuentes`: no se puede trazar al material")
    else:
        ajenas = sorted(set(fuentes) - ids_entregados)
        if ajenas:
            errores.append(
                f"`fuentes` cita fragmentos que no se entregaron: {ajenas}. Los únicos "
                f"id_fragmento válidos son {sorted(ids_entregados)}"
            )
    return errores, advertencias


def validar(crudo: str, esquema: dict, ids_entregados: set[int]):
    """(especificación o None, errores, advertencias)."""
    try:
        spec = extraer_json(crudo)
    except ErrorFormatoJSON as exc:
        return None, [str(exc)], []
    errores = validar_esquema(spec, esquema)
    if errores:
        # Con la forma rota, las reglas por código no tienen de dónde agarrarse.
        return spec, errores, []
    errores, advertencias = validar_reglas(spec, ids_entregados)
    return spec, errores, advertencias


def mensaje_de_reparacion(errores: list[str]) -> str:
    """El mismo texto que `ResultadoValidacion.mensaje_para_reparacion`."""
    listado = "\n".join(f"{i}. {e}" for i, e in enumerate(errores, start=1))
    return (
        "La respuesta anterior fue rechazada por estos motivos:\n"
        f"{listado}\n\n"
        "Corrige exclusivamente esos puntos y vuelve a entregar el objeto "
        "JSON completo, en español y sin texto adicional fuera del JSON. "
        "La respuesta nueva tiene que ser distinta de la anterior: si "
        "envías el mismo contenido otra vez, el motivo de rechazo se "
        "repite."
    )


# --- Generación --------------------------------------------------------------------


def generar_spec(
    cliente: ClienteMedido,
    sistema: str,
    usuario: str,
    esquema: dict,
    ids_entregados: set[int],
    reintentos: int,
) -> dict:
    """Pide la especificación y la repara, con el mismo bucle que `generator.generar`."""
    mensajes = [Mensaje("system", sistema), Mensaje("user", usuario)]
    intentos: list[dict] = []
    anterior: str | None = None
    inicio = time.perf_counter()
    primera = len(cliente.llamadas)
    spec, advertencias, valida = None, [], False

    for intento in range(1, reintentos + 2):
        crudo = cliente.responder(mensajes)
        spec, errores, advertencias = validar(crudo, esquema, ids_entregados)
        intentos.append({"intento": intento, "errores": errores, "crudo": crudo})
        if not errores:
            valida = True
            break
        if intento <= reintentos:
            if crudo == anterior:
                # Hallazgo H2: ante una respuesta repetida, se parte de cero.
                mensajes = [
                    Mensaje("system", sistema),
                    Mensaje("user", f"{usuario}\n\n{mensaje_de_reparacion(errores)}"),
                ]
            else:
                mensajes.append(Mensaje("assistant", crudo))
                mensajes.append(Mensaje("user", mensaje_de_reparacion(errores)))
            anterior = crudo

    llamadas = cliente.llamadas[primera:]
    return {
        "valida": valida,
        "spec": spec if valida else None,
        "intentos": len(intentos),
        "reparaciones": len(intentos) - 1,
        "detalle_intentos": intentos,
        "advertencias": advertencias if valida else [],
        "segundos": round(time.perf_counter() - inicio, 2),
        "tokens_entrada": sum(f["tokens_entrada"] for f in llamadas),
        "tokens_entrada_cache": sum(f["tokens_entrada_cache"] for f in llamadas),
        "tokens_salida": sum(f["tokens_salida"] for f in llamadas),
        "tokens_razonamiento": sum(f["tokens_razonamiento"] for f in llamadas),
        "costo_usd": sum(f["costo_usd"] for f in llamadas),
        "costo_usd_punta": sum(f["costo_usd_punta"] for f in llamadas),
        "tarifa": llamadas[-1]["tarifa"],
        "modelo_respondido": llamadas[-1]["modelo_respondido"],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plan", action="store_true", help="muestra qué haría, sin llamar")
    parser.add_argument("--solo", action="append", help="código de objetivo (repetible)")
    parser.add_argument("--corridas", type=int, default=CORRIDAS)
    parser.add_argument("--modelo", help="por defecto, el de LLM_MODEL")
    parser.add_argument(
        "--thinking",
        choices=["enabled", "disabled", ""],
        help="razonamiento del modelo; por defecto, el de LLM_THINKING",
    )
    parser.add_argument(
        "--prompt",
        choices=["modulo", "informe"],
        default="modulo",
        help="rag/prompts/visual.py (vigente) o el texto del §3.2 (primera tanda)",
    )
    parser.add_argument("--destino", default="", help="subcarpeta de specs_llm/ para esta tanda")
    parser.add_argument("--tarea", default="validacion", help="a qué tope se carga el gasto")
    args = parser.parse_args()
    # En `dev` el motor de SQLAlchemy imprime cada consulta.
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)

    carpeta, carpeta_svg = SPECS_LLM / args.destino, SVG_LLM / args.destino
    registro_ruta = carpeta / "registro.json"
    if not args.plan and not args.destino and REGISTRO.exists():
        raise SystemExit(
            "specs_llm/ ya tiene la primera tanda: usa --destino <nombre> para no pisarla"
        )

    ajustes = get_settings()
    esquema, esquema_texto, sistema, plantilla = cargar_contrato(args.prompt)
    with OBJETIVOS_CSV.open(encoding="utf-8-sig", newline="") as fh:
        codigos = [fila["codigo_objetivo"] for fila in csv.DictReader(fh)]
    if args.solo:
        codigos = [c for c in codigos if c in args.solo]

    material: dict[str, tuple] = {}
    with SessionLocal() as db:
        for codigo in codigos:
            objetivo = db.scalar(
                select(ObjetivoAprendizaje).where(ObjetivoAprendizaje.codigo_objetivo == codigo)
            )
            if objetivo is None:
                raise SystemExit(f"el objetivo {codigo} no está en la base")
            # Sin `canal_primario`: el esquema es por lección, no por perfil, así
            # que los fragmentos van en el orden del documento.
            fragmentos = retriever.recuperar(db, id_objetivo=objetivo.id_objetivo)
            if not fragmentos:
                raise SystemExit(f"el objetivo {codigo} no tiene fragmentos validados")
            material[codigo] = (objetivo, fragmentos)

    usuarios = {
        codigo: armar_usuario(plantilla, objetivo, fragmentos, esquema_texto)
        for codigo, (objetivo, fragmentos) in material.items()
    }

    modelo = args.modelo or ajustes.llm_model
    thinking = ajustes.llm_thinking if args.thinking is None else args.thinking
    print(
        f"modelo: {modelo} · temperatura: {ajustes.llm_temperature} · modo JSON: "
        f"{ajustes.llm_json_mode} · max_tokens: {ajustes.llm_max_tokens} · thinking: "
        f"{thinking or 'no se envía'}"
    )
    for codigo, (_, fragmentos) in material.items():
        print(
            f"  {codigo}: {len(fragmentos)} fragmentos validados, "
            f"{len(usuarios[codigo])} caracteres de prompt × {args.corridas} corridas"
        )
    print(
        f"gastado en «{args.tarea}»: US${gastado(tarea=args.tarea):.4f} de "
        f"US${TOPES_USD[args.tarea]:.2f}"
    )
    if args.plan:
        return 0

    carpeta.mkdir(parents=True, exist_ok=True)
    (carpeta / "prompts_usados").mkdir(exist_ok=True)
    (carpeta / "material").mkdir(exist_ok=True)
    carpeta_svg.mkdir(parents=True, exist_ok=True)
    (carpeta / "prompts_usados" / "sistema.txt").write_text(sistema, encoding="utf-8")

    for codigo, (objetivo, fragmentos) in material.items():
        (carpeta / "prompts_usados" / f"usuario_{codigo}.txt").write_text(
            usuarios[codigo], encoding="utf-8"
        )
        (carpeta / "material" / f"{codigo}.json").write_text(
            json.dumps(
                {
                    "codigo_objetivo": codigo,
                    "asignatura": objetivo.asignatura,
                    "unidad": objetivo.unidad,
                    "tema": objetivo.tema,
                    "origen": "base de datos: fragmentos validados (retriever.recuperar)",
                    "fragmentos": [
                        {
                            "id_fragmento": f.id_fragmento,
                            "documento": f.documento,
                            "cita": f.cita,
                            "tipo": f.tipo,
                            "texto": f.texto,
                        }
                        for f in fragmentos
                    ],
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )

    registro = (
        json.loads(registro_ruta.read_text(encoding="utf-8")) if registro_ruta.exists() else []
    )
    cliente = ClienteMedido(modelo=args.modelo, thinking=args.thinking, tarea=args.tarea)
    for codigo, (_, fragmentos) in material.items():
        ids_entregados = {f.id_fragmento for f in fragmentos}
        for corrida in range(1, args.corridas + 1):
            nombre = f"{codigo}_c{corrida}"
            cliente.etiqueta = f"spec:{nombre}"
            try:
                resultado = generar_spec(
                    cliente,
                    sistema,
                    usuarios[codigo],
                    esquema,
                    ids_entregados,
                    ajustes.llm_max_repair_attempts,
                )
            except TopeSuperado as exc:
                print(f"DETENIDO en {nombre}: {exc}")
                registro_ruta.write_text(
                    json.dumps(registro, ensure_ascii=False, indent=2), encoding="utf-8"
                )
                return 2

            fila = {
                "nombre": nombre,
                "codigo_objetivo": codigo,
                "corrida": corrida,
                "modelo_pedido": cliente.modelo,
                "thinking": cliente.thinking,
                "temperatura": ajustes.llm_temperature,
                "generado_utc": datetime.now(UTC).isoformat(timespec="seconds"),
                "fragmentos_entregados": sorted(ids_entregados),
                **{k: v for k, v in resultado.items() if k != "spec"},
            }
            registro = [f for f in registro if f["nombre"] != nombre] + [fila]

            estado = "falló"
            if resultado["valida"]:
                spec = resultado["spec"]
                spec["origen"] = {
                    "codigo_objetivo": codigo,
                    "generado_por": cliente.modelo,
                    "corrida": corrida,
                    "intentos": resultado["intentos"],
                    "prompt": args.prompt,
                    "nota": "Generada por el LLM; sin editar a mano.",
                }
                (carpeta / f"{nombre}.json").write_text(
                    json.dumps(spec, ensure_ascii=False, indent=2), encoding="utf-8"
                )
                svg = base.renderizar_svg(spec)
                (carpeta_svg / f"{nombre}.svg").write_text(svg, encoding="utf-8")
                estado = (
                    "a la primera"
                    if resultado["reparaciones"] == 0
                    else f"con {resultado['reparaciones']} reparación(es)"
                )
                estado += f" · {spec['tipo_de_diagrama']} · {len(spec['nodos'])} nodos"
            print(
                f"  {nombre}: {estado} · {resultado['tokens_entrada']}+"
                f"{resultado['tokens_salida']} tokens · {resultado['segundos']} s · "
                f"US${resultado['costo_usd']:.5f}"
            )
            for intento in resultado["detalle_intentos"]:
                for error in intento["errores"]:
                    print(f"      intento {intento['intento']}: {error}")
            for aviso in resultado["advertencias"]:
                print(f"      aviso: {aviso}")

    registro_ruta.write_text(json.dumps(registro, ensure_ascii=False, indent=2), encoding="utf-8")
    print(
        f"gastado en «{args.tarea}»: US${gastado(tarea=args.tarea):.4f} de "
        f"US${TOPES_USD[args.tarea]:.2f} · en total: US${gastado():.4f}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
