"""Capa 1 de la batería VARK: decisión perfil → canales y evaluación, sin red.

`scripts/probar_perfiles_vark.py` corre el pipeline real contra DeepSeek y
XTTS. Estos tests cubren lo que no necesita ninguno de los dos: que la batería
construya los perfiles pedidos, que cada perfil se traduzca en los canales y
cantidades que fija la tabla 11.1, y que la evaluación de una cápsula —con un
LLM y un TTS falsos— marque como falla lo que tiene que marcar. Corren sin
`LLM_API_KEY`, sin base de datos y sin GPU.
"""

import importlib.util
import json
import sys
import wave
from decimal import Decimal
from pathlib import Path

import pytest
from material import EXPLICACION, FRAGMENTOS, OBJETIVO, PARRAFO, capsula_valida

from studify.vark.rules import aplicar_reglas

_RUTA = Path(__file__).resolve().parent.parent / "scripts" / "probar_perfiles_vark.py"
_spec = importlib.util.spec_from_file_location("probar_perfiles_vark", _RUTA)
bateria = importlib.util.module_from_spec(_spec)
sys.modules["probar_perfiles_vark"] = bateria
_spec.loader.exec_module(bateria)

BATERIA = bateria.construir_bateria("ABC", 8, 42)


# --- Construcción de la batería ----------------------------------------------


def test_todos_los_perfiles_suman_100_y_dejan_visual_en_cero():
    assert all(p.v == 0 and p.a + p.r + p.k == 100 for p in BATERIA)
    assert len({p.slug for p in BATERIA}) == len(BATERIA)


def test_fases_tienen_los_perfiles_pedidos():
    nombres_b = {p.nombre for p in bateria.fase_b()}
    assert [p.nombre for p in bateria.fase_a()] == ["A100-R0-K0", "A0-R100-K0", "A0-R0-K100"]
    assert len(nombres_b) == 3 + 6 + 6 + 1 + 3
    assert {"A50-R50-K0", "A50-R0-K50", "A0-R50-K50", "A34-R33-K33"} <= nombres_b
    assert {"A90-R5-K5", "A5-R90-K5", "A5-R5-K90"} <= nombres_b
    assert {"A70-R20-K10", "A10-R20-K70", "A30-R60-K10", "A10-R30-K60"} <= nombres_b


def test_fase_c_es_reproducible_con_la_misma_semilla():
    misma = [p.pcts for p in bateria.fase_c(8, 42)]
    assert misma == [p.pcts for p in bateria.fase_c(8, 42)]
    assert misma != [p.pcts for p in bateria.fase_c(8, 7)]
    assert len(bateria.fase_c(12, 42)) == 12


@pytest.mark.parametrize(
    "proporciones",
    [(1 / 3, 1 / 3, 1 / 3), (0.333, 0.333, 0.334), (0.995, 0.004, 0.001), (0.5, 0.5, 0.0)],
)
def test_redondeo_suma_exactamente_100(proporciones):
    enteros = bateria.redondear_a_100(proporciones)
    assert sum(enteros) == 100
    assert all(abs(e - p * 100) < 1 for e, p in zip(enteros, proporciones, strict=True))


# --- Decisión: perfil → canales, cantidades y directivas ---------------------


@pytest.mark.parametrize("perfil", BATERIA, ids=lambda p: p.slug)
def test_decision_del_motor_para_cada_perfil_de_la_bateria(perfil):
    config = aplicar_reglas(perfil.vark())
    d = set(config.directivas)
    a, r, k = perfil.a, perfil.r, perfil.k

    assert config.pesos.total == Decimal(100)
    assert config.recursos_visuales == 0  # V = 0: nunca se pide imagen
    assert config.audio_activo == (a >= 25)
    assert config.componentes_practicos == (3 if k >= 40 else 2 if k >= 25 else 1 if k else 0)

    primario = max("ARK", key=lambda c: (perfil.pcts[c], -"ARK".index(c)))
    assert config.jerarquia.canal_primario == primario
    if max(a, r, k) >= 40:
        assert config.tono_narrativo == {"A": "oral", "R": "formal", "K": "practico"}[primario]

    if r >= 40:
        assert {"encabezados_jerarquicos", "definiciones_exactas", "glosario"} <= d
    if r == 0:
        assert not d & {"encabezados_jerarquicos", "glosario"}
    if a >= 40:
        assert {"tono_oral", "analogias_cotidianas", "preguntas_reflexivas"} <= d
    if a == 0:
        assert not d & {"tono_oral", "analogias_cotidianas", "preguntas_reflexivas"}
    if k >= 40:
        assert {"ejemplo_resuelto", "paso_a_paso", "actividad_aplicada"} <= d
    if k == 0:
        assert not d & {"paso_a_paso", "actividad_aplicada"}
    assert not d & {"incluir_mapa_conceptual", "tabla_comparativa", "recurso_visual_complementario"}


# --- Pipeline con LLM y TTS falsos -------------------------------------------


class ClienteFalso:
    def __init__(self, *respuestas):
        self.respuestas = list(respuestas)
        self.modelo = "modelo-de-prueba"

    def responder(self, mensajes):
        respuesta = self.respuestas.pop(0)
        if isinstance(respuesta, Exception):
            raise respuesta
        return respuesta


def tts_falso(texto: str, ruta: Path, *, palabras_por_segundo: float = 2.5) -> Path:
    """WAV de silencio con la duración que tendría el guion narrado."""
    segundos = max(1.0, len(texto.split()) / palabras_por_segundo)
    with wave.open(str(ruta), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(24000)
        w.writeframes(b"\x00\x00" * int(24000 * segundos))
    return ruta


def capsula_k() -> dict:
    datos = capsula_valida()
    datos["representacion_adaptativa"] = [
        {"tipo": "parrafo", "encabezado": "Dependencia parcial", "cuerpo": EXPLICACION},
        {
            "tipo": "lista_pasos",
            "encabezado": "Cómo corregirla",
            "cuerpo": [
                "Identifica la clave primaria compuesta de la tabla.",
                "Revisa de qué parte de la clave depende cada atributo.",
                "Separa el atributo que depende de una parte en su propia tabla.",
            ],
        },
    ]
    datos["actividad"] = {
        "tipo": "flashcards_y_quiz",
        "tarjetas": [
            {"anverso": "Dependencia parcial", "reverso": "Depende de parte de la clave"},
            {"anverso": "Clave compuesta", "reverso": "Clave formada por varios atributos"},
            {"anverso": "Normalización", "reverso": "Proceso que reduce la redundancia"},
        ],
        "preguntas": [
            {
                "enunciado": f"Pregunta {i}: ¿qué indica una dependencia parcial?",
                "alternativas": [
                    "Un atributo no clave depende de parte de la clave compuesta",
                    "La tabla tiene demasiadas columnas",
                    "La clave primaria es numérica",
                ],
                "indice_correcta": 0,
                "explicacion": "Así se define en el material.",
            }
            for i in range(1, 4)
        ],
    }
    return datos


def capsula_a() -> dict:
    datos = capsula_valida()
    datos["representacion_adaptativa"] = [
        {
            "tipo": "analogia",
            "encabezado": "Como tus contactos",
            "cuerpo": (
                "Piensa en tu lista de contactos: si guardas el nombre de tu amigo "
                "junto a cada mensaje, tienes que corregirlo en todos cuando cambia. "
                "¿No sería mejor guardarlo una sola vez? Eso busca la normalización."
            ),
        },
        {"tipo": "parrafo", "encabezado": "Dependencia parcial", "cuerpo": EXPLICACION},
    ]
    datos["ejemplo"] = {"tipo": "parrafo", "encabezado": "Caso", "cuerpo": PARRAFO[:200]}
    return datos


def capsula_r() -> dict:
    datos = capsula_valida()
    datos["representacion_adaptativa"] = [
        {"tipo": "parrafo", "encabezado": "Dependencia parcial", "cuerpo": EXPLICACION},
        {
            "tipo": "glosario",
            "encabezado": "Glosario",
            "cuerpo": [
                "Dependencia parcial: atributo no clave que depende de parte de la clave.",
                "Segunda forma normal: todo atributo no clave depende de la clave completa.",
            ],
        },
    ]
    datos["ejemplo"] = {"tipo": "parrafo", "encabezado": "Caso", "cuerpo": PARRAFO[:200]}
    return datos


def correr(tmp_path, perfil, *respuestas, sintetizar=tts_falso):
    return bateria.ejecutar_perfil(
        perfil,
        objetivo=OBJETIVO,
        obtener_fragmentos=lambda _config: FRAGMENTOS,
        cliente=ClienteFalso(*respuestas),
        sintetizar=sintetizar,
        dir_corrida=tmp_path,
        modelo="modelo-de-prueba",
    )


def json_de(datos: dict) -> str:
    return json.dumps(datos, ensure_ascii=False)


K_PURO = bateria.Perfil("A", "K100", a=0, r=0, k=100)
A_PURO = bateria.Perfil("A", "A100", a=100, r=0, k=0)
R_PURO = bateria.Perfil("A", "R100", a=0, r=100, k=0)


def test_k_puro_pasa_con_flashcards_quiz_y_pasos(tmp_path):
    r = correr(tmp_path, K_PURO, json_de(capsula_k()))

    assert r["veredicto"] == "pasa", r["criterios"]
    assert r["criterios"]["ejercicios"]["estado"] == "pasa"
    assert r["criterios"]["audio"]["estado"] == "n/a"
    assert r["puntajes"]["K"] == 1.0
    assert (tmp_path / "A_K100" / "capsula.json").exists()


def test_a_puro_sintetiza_el_guion_del_visor_y_lo_valida(tmp_path):
    r = correr(tmp_path, A_PURO, json_de(capsula_a()))

    assert r["veredicto"] == "pasa", r["criterios"]
    assert r["criterios"]["audio"]["estado"] == "pasa"
    assert r["audio"]["guion"].startswith(capsula_a()["activacion"])
    assert Path(r["artefactos"]["audio"]).stat().st_size > 0
    # La ruta de POST /api/capsulas narraría JSON: queda registrado como evidencia.
    assert r["guion_ruta_api_es_json"] is True
    assert r["puntajes"]["A"] == 1.0


def test_r_puro_exige_glosario_y_encabezados(tmp_path):
    r = correr(tmp_path, R_PURO, json_de(capsula_r()))
    assert r["veredicto"] == "pasa", r["criterios"]

    sin_glosario = capsula_r()
    sin_glosario["representacion_adaptativa"].pop()
    r = correr(tmp_path, R_PURO, json_de(sin_glosario))
    assert r["criterios"]["texto"]["estado"] == "falla"
    assert "glosario" in r["criterios"]["texto"]["detalle"]


def test_cita_inventada_se_repara_y_cuenta_el_reintento(tmp_path):
    inventada = capsula_k()
    inventada["fuentes"] = [{"id_fragmento": 999, "documento": "x", "pagina": 1}]

    r = correr(tmp_path, K_PURO, json_de(inventada), json_de(capsula_k()))

    assert r["intentos"] == 2
    assert r["operativo"]["llamadas"] == 2
    assert r["criterios"]["trazabilidad"]["estado"] == "pasa"
    assert "999" in r["errores_por_intento"][0][0]


def test_contrato_agotado_queda_registrado_sin_romper_la_bateria(tmp_path):
    r = correr(tmp_path, K_PURO, "no es json", "tampoco", "{")

    assert r["veredicto"] == "falla"
    assert r["criterios"]["contrato"]["estado"] == "falla"
    assert len(r["errores_por_intento"]) == 3
    assert (tmp_path / "A_K100" / "respuestas_crudas.json").exists()


def test_timeout_del_llm_queda_como_error_operativo(tmp_path):
    class APITimeoutError(Exception):
        pass

    r = correr(tmp_path, K_PURO, APITimeoutError("se agotó el tiempo"))

    assert r["veredicto"] == "error"
    assert r["error"]["timeout"] is True


def test_proporcion_falla_si_el_dominante_no_deja_marcas(tmp_path):
    # Un K puro que recibe la cápsula genérica: quiz_mc y sin lista de pasos.
    r = correr(tmp_path, K_PURO, json_de(capsula_valida()))

    assert r["criterios"]["proporcion"]["estado"] == "falla"
    assert r["criterios"]["ejercicios"]["estado"] == "falla"
    assert r["veredicto"] == "falla"


def test_dos_canales_sobre_40_son_codominantes():
    # C06 de la corrida del 03-oct: A41/K46 reciben ambos sus directivas y las
    # cumplen por completo; exigir que K le gane a A sería castigar al motor
    # por hacer exactamente lo que se le pidió.
    perfil = bateria.Perfil("C", "A41-R13-K46", a=41, r=13, k=46)
    marcas = {"A": {}, "R": {}, "K": {}, "V": {}}

    ok, _ = bateria.evaluar_proporcion(perfil, {"A": 1.0, "R": 0.67, "K": 1.0, "V": 0}, marcas)
    mal, _ = bateria.evaluar_proporcion(perfil, {"A": 0.5, "R": 0.67, "K": 1.0, "V": 0}, marcas)

    assert ok["estado"] == "pasa"
    assert mal["estado"] == "falla"


def test_audio_truncado_falla_por_duracion(tmp_path):
    def tts_truncado(texto, ruta):
        return tts_falso("una dos", ruta)  # 1 s para un guion de decenas de palabras

    r = correr(tmp_path, A_PURO, json_de(capsula_a()), sintetizar=tts_truncado)

    assert r["criterios"]["audio"]["estado"] == "falla"
    assert "duración" in r["criterios"]["audio"]["detalle"]


def test_fallo_del_tts_no_tumba_la_bateria(tmp_path):
    def tts_roto(texto, ruta):
        raise RuntimeError("sin modelo")

    r = correr(tmp_path, A_PURO, json_de(capsula_a()), sintetizar=tts_roto)

    assert r["criterios"]["audio"]["estado"] == "falla"
    assert "sin modelo" in r["criterios"]["audio"]["detalle"]


def test_canal_al_cero_con_marcadores_genera_advertencia(tmp_path):
    # A puro con un `ejemplo_resuelto` (marcador K) en el ejemplo.
    datos = capsula_a()
    datos["ejemplo"] = capsula_valida()["ejemplo"]

    r = correr(tmp_path, A_PURO, json_de(datos))

    assert any("canal K al 0%" in a for a in r["advertencias"])


# --- Heurísticas de texto ----------------------------------------------------


def test_cifras_ajenas_a_los_fragmentos_se_detectan():
    fragmentos = "El RUT 19.876.543-2 identifica a Carlos. Paso 1, paso 2."
    assert bateria.numeros_ajenos("El RUT 19.876.543-2 y el paso 3", fragmentos) == []
    assert bateria.numeros_ajenos("Desde 1970 se usa en el 85% de los casos", fragmentos) == [
        "1970",
        "85",
    ]


def test_cobertura_tolera_flexion_pero_no_temas_ajenos():
    vocabulario = bateria.raices("Una dependencia funcional determina atributos")
    assert bateria.cobertura("Los atributos que se determinan", vocabulario) == 1.0
    assert bateria.cobertura("Fotosíntesis clorofila", vocabulario) == 0.0
    assert bateria.cobertura("de la y", vocabulario) is None


def test_informe_reemplaza_solo_el_bloque_generado(tmp_path):
    r = correr(tmp_path, K_PURO, json_de(capsula_k()))
    resumen = {
        "corrida": "prueba", "fecha": "hoy", "directorio": str(tmp_path),
        "objetivo": {"codigo": "BD-U3-01", "tema": "t", "id": 42, "fragmentos": 2},
        "modelo": "m", "semilla": 42, "n_aleatorias": 8, "fases": "A",
        "comando": "c", "resultados": [r],
    }
    doc = tmp_path / "PRUEBAS.md"
    marcas = f"{bateria.MARCA_INICIO}\nviejo\n{bateria.MARCA_FIN}"
    doc.write_text(f"# Título\n\nanálisis escrito\n\n{marcas}\n\nfin\n", "utf-8")

    bateria.escribir_informe(resumen, doc)

    texto = doc.read_text("utf-8")
    assert "análisis escrito" in texto and texto.rstrip().endswith("fin")
    assert "viejo" not in texto
    assert "| K100 (0/0/100) | ✅ 1 |" in texto
    assert "[cápsula](A_K100/capsula.json)" in texto
