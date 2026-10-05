"""Genera, sobre copias del código actual, las variantes de la ronda H1+H3 y sus parches.

    python scripts/h1h3/hacer_variantes.py

No modifica `src/` ni `tests/`. Escribe:
  data/h1h3/<variante>/src/studify/...   (copia del árbol; `data/` está ignorado por git)
  data/h1h3/<variante>/tests/test_prompt_maestro.py
  scripts/h1h3/parches/brazo_A.patch, brazo_B.patch, brazo_B_topes.patch

Variantes:
  base     código actual, sin cambios (línea base de la ronda)
  prefijo  base con el texto de `actividad_aplicada` anterior al fix de la etiqueta (solo para S44)
  A        solo la instrucción nueva del glosario
  B_topes  B tal como se midió en la Etapa 1 (topes «como máximo N»), con la regla de párrafo aprobada;
           existe para comprobar que se reproducen los prompts guardados de esa etapa
  B        reparto por paso con rangos cuyo ancho sale de palabras_min/palabras_max (ver `_ancho_relativo`)

Cada reemplazo exige exactamente una ocurrencia: si el código cambió y no calza, falla en vez de
generar un parche distinto en silencio.
"""

# ruff: noqa: E501  (contiene copias literales de líneas largas del código fuente)
import difflib
import re
import shutil
import subprocess
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
SALIDA = RAIZ / "data" / "h1h3"
PARCHES = Path(__file__).resolve().parent / "parches"
COMMIT_PREFIJO = "1eac307"  # último commit antes del fix de la etiqueta «kinestésico»

ORQ = "src/studify/rag/orchestrator.py"
MAESTRO = "src/studify/rag/prompts/maestro.py"
TEST = "tests/test_prompt_maestro.py"


def leer(ruta: Path) -> tuple[str, bool]:
    datos = ruta.read_bytes().decode("utf-8")
    return datos.replace("\r\n", "\n"), "\r\n" in datos


def escribir(ruta: Path, texto: str, crlf: bool) -> None:
    ruta.parent.mkdir(parents=True, exist_ok=True)
    ruta.write_bytes((texto.replace("\n", "\r\n") if crlf else texto).encode("utf-8"))


def editar(variante: str, archivo: str, reemplazos: list[tuple[str, str]]) -> None:
    ruta = SALIDA / variante / archivo
    texto, crlf = leer(ruta)
    for viejo, nuevo in reemplazos:
        n = texto.count(viejo)
        if n != 1:
            raise SystemExit(
                f"{variante}/{archivo}: se esperaba 1 ocurrencia y hay {n}:\n{viejo[:140]!r}"
            )
        texto = texto.replace(viejo, nuevo)
    escribir(ruta, texto, crlf)


def copiar_arbol(variante: str) -> None:
    destino = SALIDA / variante
    if destino.exists():
        shutil.rmtree(destino)
    shutil.copytree(
        RAIZ / "src" / "studify",
        destino / "src" / "studify",
        ignore=shutil.ignore_patterns("__pycache__", "public"),
    )
    (destino / "tests").mkdir(parents=True)
    shutil.copy(RAIZ / TEST, destino / TEST)


# --------------------------------------------------------------------- textos
GLOSARIO_VIEJO = """    "glosario": (
        "Cierra el contenido con un bloque `glosario` cuyo cuerpo sea una lista "
        "de entradas «término: definición»."
    ),
"""
GLOSARIO_NUEVO = """    # Hasta el 03-oct-2026 decía «Cierra el contenido con un bloque `glosario`»:
    # `contenido` era el campo del contrato anterior a los siete pasos y el
    # modelo no lo ubicaba (0 glosarios en 10 cápsulas con p_R ≥ 40%, hallazgo H1
    # de PRUEBAS_VARK.md). Las entradas se acotan porque el glosario cuenta
    # dentro de la extensión.
    "glosario": (
        "El último bloque de `representacion_adaptativa` es un bloque `glosario` "
        "con 3 a 5 entradas «término: definición», de una línea cada una, con "
        "términos que aparecen en el material entregado."
    ),
"""

EXT_VIEJA = """    "Extensión del contenido: aproximadamente {palabras_texto} palabras "
    "(mínimo {palabras_min}, máximo {palabras_max}). Sé conciso en cada sección para no sobrepasar el límite máximo.\\n"
"""
# Cabecera común a B_topes y B; cambian solo las tres líneas de los pasos 3 a 5.
EXT_CABECERA = """    # Reparto por paso (hallazgo H3): con solo el total, la extensión la decide
    # la cantidad de bloques y no el perfil. La línea sobre «únicamente los
    # bloques que piden las instrucciones» existe porque, al nombrar tipos de
    # bloque, el modelo los agregaba sin que nadie los pidiera (Etapa 1,
    # intento 1: `lista_pasos` y glosarios espurios).
    "Extensión de los pasos 2 a 5 (`activacion`, `concepto_central`, "
    "`representacion_adaptativa` y `ejemplo`): aproximadamente {palabras_texto} "
    "palabras (mínimo {palabras_min}, máximo {palabras_max}), repartidas así:\\n"
    "- `activacion`: como máximo {palabras_activacion} palabras.\\n"
"""
EXT_COLA = """    "En `representacion_adaptativa` incluye únicamente los bloques que piden las "
    "instrucciones estructurales de más abajo; no agregues bloques de otros tipos.\\n"
    "Sé conciso en cada sección para no sobrepasar el límite máximo.\\n"
"""
PASOS_TOPES = """    "- `concepto_central`: como máximo {palabras_concepto} palabras.\\n"
    "- `representacion_adaptativa`: como máximo {palabras_representacion} "
    "palabras en total, sumando todos sus bloques.\\n"
    "- `ejemplo`: como máximo {palabras_ejemplo} palabras.\\n"
"""
PASOS_RANGOS = """    # Rangos y no topes: con «como máximo N» en los tres pasos, y N sumando el
    # objetivo, cualquier paso corto deja el total bajo el objetivo (K pasó de
    # +21 % a −21 % en la Etapa 1). La activación sigue con tope: es una sola
    # pregunta y nunca fue el origen del sesgo.
    "- `concepto_central`: entre {concepto_min} y {concepto_max} palabras.\\n"
    "- `representacion_adaptativa`: entre {representacion_min} y "
    "{representacion_max} palabras en total, sumando todos sus bloques.\\n"
    "- `ejemplo`: entre {ejemplo_min} y {ejemplo_max} palabras.\\n"
"""

EJEMPLO_VIEJO = """    "ejemplo_resuelto": (
        "Incluye un bloque `ejemplo_resuelto` con un caso concreto desarrollado de principio a fin."
    ),
    "paso_a_paso": (
        "Incluye un bloque `lista_pasos` cuyo cuerpo sea una lista de pasos "
        "ordenados y accionables."
    ),
"""
EJEMPLO_NUEVO = """    # Se fija dónde va cada bloque práctico: sin destino, el modelo a veces
    # ponía un `ejemplo_resuelto` en la representación y otro en el `ejemplo`, y
    # la cápsula K se alargaba por duplicado (hallazgo H3).
    "ejemplo_resuelto": (
        "El `ejemplo` (paso 5) es un bloque `ejemplo_resuelto` con un caso "
        "concreto desarrollado de principio a fin."
    ),
    "paso_a_paso": (
        "Incluye en `representacion_adaptativa` un bloque `lista_pasos` de 3 a 5 "
        "pasos ordenados y accionables, de una oración cada uno."
    ),
    # No sale de `vark/rules.py`: la antepone `orchestrator.bloque_perfil` cuando
    # ninguna directiva del perfil reexpresa el concepto (perfiles «solo R»).
    # Decidirlo en código y no en el prompt evita nombrar tipos de bloque que el
    # modelo luego agrega sin que nadie los pida.
    "parrafo_reexpresion": (
        "Incluye en `representacion_adaptativa` un bloque `parrafo` que reexprese "
        "el concepto central con otras palabras."
    ),
"""

ORQ_CONST_VIEJA = "MARGEN_PALABRAS_OBJETIVO = 30\n"
ORQ_CONST_COMUN = """MARGEN_PALABRAS_OBJETIVO = 30

# Reparto del objetivo entre los pasos 2–5 (hallazgo H3 de PRUEBAS_VARK.md). Las
# fracciones salen de lo que el modelo ya escribía en la batería del 03-oct: el
# concepto central ronda el 35 % y el ejemplo el 20 %; la representación
# adaptativa se lleva el resto, que es donde viven los bloques de cada perfil.
PALABRAS_ACTIVACION = 20
FRACCION_CONCEPTO = 0.30
FRACCION_EJEMPLO = 0.20

# Directivas de `vark/rules.py` que ya piden un bloque que reexpresa el concepto
# central en otro formato. Si el perfil no trae ninguna, el código antepone
# `parrafo_reexpresion`: sin eso, un perfil «solo R» quedaría con la
# representación reducida al glosario. `tests/test_prompt_maestro.py` comprueba
# que cada nombre exista en las directivas reales.
DIRECTIVAS_REEXPRESIVAS = frozenset(
    {
        "analogias_cotidianas",
        "paso_a_paso",
        "incluir_mapa_conceptual",
        "tabla_comparativa",
        "recurso_visual_complementario",
    }
)
"""
ANCLA_REPARTO = """def _redondear_palabras(palabras: int) -> int:
    return round(palabras / TRAMO_PALABRAS) * TRAMO_PALABRAS
"""
REPARTO_TOPES = '''

def reparto_palabras(palabras_objetivo: int) -> dict[str, int]:
    """Cuántas palabras le tocan a cada paso; suman `palabras_objetivo`."""
    concepto = _redondear_palabras(round(palabras_objetivo * FRACCION_CONCEPTO))
    ejemplo = _redondear_palabras(round(palabras_objetivo * FRACCION_EJEMPLO))
    return {
        "palabras_activacion": PALABRAS_ACTIVACION,
        "palabras_concepto": concepto,
        "palabras_representacion": palabras_objetivo - PALABRAS_ACTIVACION - concepto - ejemplo,
        "palabras_ejemplo": ejemplo,
    }
'''
REPARTO_RANGOS = '''

def _ancho_relativo(palabras_objetivo: int, palabras_min: int, palabras_max: int) -> float:
    """Semiancho relativo, común a los tres rangos, que respeta los límites del perfil.

    Los centros suman el objetivo. Se toma el mayor ancho tal que, juntos, los
    extremos altos (más el tope de la activación) no pasen de `palabras_max` y los
    bajos (la activación aporta 0, porque solo tiene tope) no bajen de
    `palabras_min`. Con objetivos bajo ~187 palabras el ancho cae bajo ±10 %: no se
    ensancha para compensar, queda como sale de la regla.
    """
    repartible = palabras_objetivo - PALABRAS_ACTIVACION
    por_arriba = (palabras_max - PALABRAS_ACTIVACION) / repartible - 1
    por_abajo = 1 - palabras_min / repartible
    return max(0.0, min(por_arriba, por_abajo))


def reparto_palabras(
    palabras_objetivo: int, *, palabras_min: int, palabras_max: int
) -> dict[str, int]:
    """Palabras por paso: `palabras_activacion` es un tope y el resto, rangos.

    Los centros son el 30 % (concepto) y el 20 % (ejemplo) del objetivo; la
    representación adaptativa se lleva lo que queda. Los extremos se redondean
    hacia adentro, así que la suma de los límites nunca sale del perfil.
    """
    ancho = _ancho_relativo(palabras_objetivo, palabras_min, palabras_max)
    concepto = palabras_objetivo * FRACCION_CONCEPTO
    ejemplo = palabras_objetivo * FRACCION_EJEMPLO
    centros = {
        "concepto": concepto,
        "representacion": palabras_objetivo - PALABRAS_ACTIVACION - concepto - ejemplo,
        "ejemplo": ejemplo,
    }
    reparto = {"palabras_activacion": PALABRAS_ACTIVACION}
    for nombre, centro in centros.items():
        reparto[f"{nombre}_min"] = math.ceil(centro * (1 - ancho) - 1e-9)
        reparto[f"{nombre}_max"] = math.floor(centro * (1 + ancho) + 1e-9)
    return reparto
'''
INSTR_VIEJA = """    instrucciones = []
    for directiva in config.directivas:
"""
INSTR_NUEVA = """    directivas = config.directivas
    if not DIRECTIVAS_REEXPRESIVAS & set(directivas):
        directivas = ("parrafo_reexpresion", *directivas)

    instrucciones = []
    for directiva in directivas:
"""
KW_VIEJO = "        palabras_texto=palabras_objetivo,\n"
KW_TOPES = (
    "        palabras_texto=palabras_objetivo,\n        **reparto_palabras(palabras_objetivo),\n"
)
KW_RANGOS = (
    "        palabras_texto=palabras_objetivo,\n"
    "        **reparto_palabras(\n"
    "            palabras_objetivo,\n"
    "            palabras_min=ajustes.capsula_min_palabras,\n"
    "            palabras_max=ajustes.capsula_max_palabras,\n"
    "        ),\n"
)
IMPORT_VIEJO = "import hashlib\n"
IMPORT_NUEVO = "import hashlib\nimport math\n"

TESTS_ANCLA = "# --- La diferenciación entre perfiles ----------------------------------------\n"
TESTS_NUEVOS = '''# --- Párrafo de reexpresión y reparto por paso -------------------------------


def test_las_directivas_reexpresivas_existen_en_rules():
    """Si `rules.py` renombra una directiva, el conjunto dejaría de reconocerla en silencio."""
    inexistentes = orchestrator.DIRECTIVAS_REEXPRESIVAS - _todas_las_directivas_posibles()

    assert not inexistentes, f"directivas que ya no existen en vark/rules.py: {sorted(inexistentes)}"


def test_el_parrafo_de_reexpresion_solo_va_si_ninguna_directiva_reexpresa():
    parrafo = prompts.INSTRUCCION_POR_DIRECTIVA["parrafo_reexpresion"]

    solo_r = orchestrator.bloque_perfil(aplicar_reglas(perfil(0, 0, 100, 0)), palabras_objetivo=270)
    assert parrafo in solo_r

    for v, a, r, k in product(range(0, 101, 10), repeat=4):
        if v + a + r + k != 100:
            continue
        config = aplicar_reglas(perfil(v, a, r, k))
        texto = orchestrator.bloque_perfil(config, palabras_objetivo=200)
        hay_reexpresiva = bool(orchestrator.DIRECTIVAS_REEXPRESIVAS & set(config.directivas))
        assert (parrafo in texto) is (not hay_reexpresiva), (v, a, r, k)


def test_el_reparto_cabe_en_los_limites_del_perfil():
    """Con los rangos en sus extremos, la suma no sale de [palabras_min, palabras_max]."""
    for objetivo in range(170, 301, 10):
        reparto = orchestrator.reparto_palabras(objetivo, palabras_min=150, palabras_max=300)
        pasos = ("concepto", "representacion", "ejemplo")
        altos = reparto["palabras_activacion"] + sum(reparto[f"{p}_max"] for p in pasos)
        bajos = sum(reparto[f"{p}_min"] for p in pasos)

        assert altos <= 300, objetivo
        assert bajos >= 150, objetivo
        assert all(reparto[f"{p}_min"] <= reparto[f"{p}_max"] for p in pasos), objetivo


def test_el_reparto_centra_los_rangos_en_el_30_y_el_20_por_ciento():
    reparto = orchestrator.reparto_palabras(270, palabras_min=150, palabras_max=300)

    assert reparto["concepto_min"] <= 0.30 * 270 <= reparto["concepto_max"]
    assert reparto["ejemplo_min"] <= 0.20 * 270 <= reparto["ejemplo_max"]


'''


# Instrucciones que nombran bloques o fijan su destino: las comparten B_topes y B.
def aplicar_comun_b(variante: str, *, rangos: bool) -> None:
    editar(
        variante,
        MAESTRO,
        [
            (EXT_VIEJA, EXT_CABECERA + (PASOS_RANGOS if rangos else PASOS_TOPES) + EXT_COLA),
            (EJEMPLO_VIEJO, EJEMPLO_NUEVO),
        ],
    )
    editar(
        variante,
        ORQ,
        [
            (ORQ_CONST_VIEJA, ORQ_CONST_COMUN),
            (ANCLA_REPARTO, ANCLA_REPARTO + (REPARTO_RANGOS if rangos else REPARTO_TOPES)),
            (INSTR_VIEJA, INSTR_NUEVA),
            (KW_VIEJO, KW_RANGOS if rangos else KW_TOPES),
            *([(IMPORT_VIEJO, IMPORT_NUEVO)] if rangos else []),
        ],
    )
    if rangos:
        editar(variante, TEST, [(TESTS_ANCLA, TESTS_NUEVOS + TESTS_ANCLA)])


def _lineas(texto: str) -> list[str]:
    return re.findall(r"[^\n]*\n|[^\n]+", texto)


def escribir_parche(variante: str, nombre: str) -> None:
    lineas: list[str] = []
    for archivo in (ORQ, MAESTRO, TEST):
        viejo = (SALIDA / "base" / archivo).read_bytes().decode("utf-8")
        nuevo = (SALIDA / variante / archivo).read_bytes().decode("utf-8")
        if viejo == nuevo:
            continue
        lineas += difflib.unified_diff(
            _lineas(viejo),
            _lineas(nuevo),
            fromfile=f"a/{archivo}",
            tofile=f"b/{archivo}",
            n=3,
        )
    PARCHES.mkdir(exist_ok=True)
    (PARCHES / nombre).write_bytes("".join(lineas).encode("utf-8"))


def main() -> None:
    for variante in ("base", "prefijo", "A", "B_topes", "B"):
        copiar_arbol(variante)

    previo = subprocess.run(
        ["git", "show", f"{COMMIT_PREFIJO}:{MAESTRO}"], cwd=RAIZ, capture_output=True, check=True
    ).stdout.decode("utf-8")
    _, crlf = leer(SALIDA / "base" / MAESTRO)
    escribir(SALIDA / "prefijo" / MAESTRO, previo.replace("\r\n", "\n"), crlf)

    for variante in ("A", "B_topes", "B"):
        editar(variante, MAESTRO, [(GLOSARIO_VIEJO, GLOSARIO_NUEVO)])
    aplicar_comun_b("B_topes", rangos=False)
    aplicar_comun_b("B", rangos=True)

    escribir_parche("A", "brazo_A.patch")
    escribir_parche("B_topes", "brazo_B_topes.patch")
    escribir_parche("B", "brazo_B.patch")
    print(f"variantes en {SALIDA}\nparches en {PARCHES}")


if __name__ == "__main__":
    main()
