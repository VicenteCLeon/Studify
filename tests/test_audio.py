"""Tests de la narración del visor (`media/audio.py` y `media/guion.py`).

Sin modelos ni red: los motores se sustituyen por funciones falsas en
`audio.MOTORES`, y los paquetes que no deben cargarse se bloquean en
`sys.modules` (un `None` ahí hace fallar cualquier `import`). Así se prueba la
lógica —qué voz se elige, qué pasa si el motor falla, cómo se escribe el
archivo— sin bajar los ~350 MB de Kokoro ni cargar XTTS.
"""

import sys
import types
import wave
from pathlib import Path

import pytest

from studify.config import Settings, get_settings
from studify.media import audio
from studify.media.audio import (
    ErrorAudio,
    PreferenciaVoz,
    VozElegida,
    generar_audio,
    resolver_voz,
)
from studify.media.guion import REGLAS, normalizar_guion


@pytest.fixture
def ajustes(monkeypatch, tmp_path):
    """Los ajustes reales con el motor por defecto y un directorio de modelos vacío."""
    settings = get_settings()
    monkeypatch.setattr(settings, "tts_motor", "kokoro")
    monkeypatch.setattr(settings, "tts_modelos_dir", str(tmp_path / "voces"))
    monkeypatch.setattr(audio, "_kokoro", None)
    return settings


@pytest.fixture
def motores_falsos(monkeypatch):
    """Reemplaza los motores por dobles que anotan con qué se los llamó."""
    llamadas: list[tuple[str, VozElegida, str]] = []

    def _falso(nombre):
        def _sintetizar(guion, destino, eleccion, language, ajustes):
            llamadas.append((nombre, eleccion, guion))
            with wave.open(str(destino), "wb") as wf:
                wf.setnchannels(1)
                wf.setsampwidth(2)
                wf.setframerate(24000)
                wf.writeframes(b"\x00\x00" * 2400)

        return _sintetizar

    for nombre in ("kokoro", "piper", "xtts"):
        monkeypatch.setitem(audio.MOTORES, nombre, _falso(nombre))
    return llamadas


@pytest.fixture
def piper_falso(ajustes, monkeypatch):
    """Un paquete `piper` falso y archivos de modelo vacíos: prueba el motor real
    (`_cargar_piper` y `_sintetizar_piper`) sin bajar ni cargar el modelo."""
    voces = Path(ajustes.tts_modelos_dir)
    voces.mkdir(parents=True, exist_ok=True)
    for sufijo in (".onnx", ".onnx.json"):
        (voces / f"{ajustes.tts_voz_rapida_modelo}{sufijo}").write_bytes(b"")

    registro = {"cargas": 0, "hablantes": []}

    class SynthesisConfig:
        def __init__(self, speaker_id=None):
            self.speaker_id = speaker_id

    class VozFalsa:
        def synthesize_wav(self, texto, wf, syn_config=None):
            registro["hablantes"].append(syn_config.speaker_id if syn_config else None)
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(22050)
            wf.writeframes(b"\x00\x00" * 2205)

    class PiperVoice:
        @staticmethod
        def load(modelo, config_path=None):
            registro["cargas"] += 1
            return VozFalsa()

    modulo = types.ModuleType("piper")
    modulo.PiperVoice = PiperVoice
    modulo.SynthesisConfig = SynthesisConfig
    monkeypatch.setitem(sys.modules, "piper", modulo)
    monkeypatch.setattr(audio, "_piper", {})
    return registro


# --- Motor por defecto y preferencia del estudiante ---------------------------


def test_el_motor_por_defecto_es_kokoro_con_dora(ajustes):
    """Sin preferencia guardada, el estudiante oye a Dora (femenina, calidad)."""
    assert Settings.model_fields["tts_motor"].default == "kokoro"
    assert resolver_voz(ajustes=ajustes) == VozElegida(motor="kokoro", voz="ef_dora")


@pytest.mark.parametrize(
    ("genero", "voz"),
    [("femenina", "ef_dora"), ("masculina", "em_alex")],
)
def test_la_preferencia_de_calidad_se_traduce_a_una_voz_de_kokoro(ajustes, genero, voz):
    eleccion = resolver_voz(PreferenciaVoz(genero=genero, modo="calidad"), ajustes=ajustes)

    assert eleccion == VozElegida(motor="kokoro", voz=voz)


@pytest.mark.parametrize(("genero", "hablante"), [("femenina", 1), ("masculina", 0)])
def test_la_preferencia_rapida_se_traduce_a_un_hablante_de_sharvard(ajustes, genero, hablante):
    """Un solo modelo de Piper; el género lo decide el hablante (`speaker_id_map`)."""
    eleccion = resolver_voz(PreferenciaVoz(genero=genero, modo="rapida"), ajustes=ajustes)

    assert eleccion == VozElegida(motor="piper", voz="es_ES-sharvard-medium", hablante=hablante)


def test_cambiar_de_modo_conserva_el_genero(ajustes):
    """La preferencia es {género, modo}: pasar de calidad a rápida no cambia el género."""
    femenina = {
        modo: resolver_voz(PreferenciaVoz(genero="femenina", modo=modo), ajustes=ajustes)
        for modo in ("calidad", "rapida")
    }
    masculina = {
        modo: resolver_voz(PreferenciaVoz(genero="masculina", modo=modo), ajustes=ajustes)
        for modo in ("calidad", "rapida")
    }

    assert (femenina["calidad"].voz, femenina["rapida"].hablante) == ("ef_dora", 1)
    assert (masculina["calidad"].voz, masculina["rapida"].hablante) == ("em_alex", 0)


def test_xtts_administrativo_gana_sobre_la_preferencia(ajustes, monkeypatch):
    monkeypatch.setattr(ajustes, "tts_motor", "xtts")

    for genero in ("femenina", "masculina"):
        eleccion = resolver_voz(PreferenciaVoz(genero=genero), ajustes=ajustes)
        assert eleccion == VozElegida(motor="xtts")


def test_generar_audio_usa_la_voz_de_la_preferencia(ajustes, motores_falsos, tmp_path):
    destino = tmp_path / "salida.wav"

    generar_audio("Hola.", destino, preferencia=PreferenciaVoz(genero="masculina"))

    assert [(m, e.voz) for m, e, _ in motores_falsos] == [("kokoro", "em_alex")]
    assert destino.exists()


# --- Piper (modo «rápida») -------------------------------------------------------


@pytest.mark.parametrize(("genero", "hablante"), [("femenina", 1), ("masculina", 0)])
def test_piper_recibe_el_hablante_explicito(piper_falso, ajustes, tmp_path, genero, hablante):
    """El `speaker_id` viaja siempre: sin él Piper usaría el 0 (masculino) para todas."""
    destino = tmp_path / "salida.wav"

    generar_audio("Hola.", destino, preferencia=PreferenciaVoz(genero=genero, modo="rapida"))

    assert piper_falso["hablantes"] == [hablante]
    with wave.open(str(destino), "rb") as wf:
        assert wf.getframerate() == 22050


def test_piper_carga_el_modelo_una_sola_vez(piper_falso, tmp_path):
    for genero in ("femenina", "masculina", "femenina"):
        generar_audio(
            "Hola.", tmp_path / f"{genero}.wav", preferencia=PreferenciaVoz(genero, "rapida")
        )

    assert piper_falso["cargas"] == 1
    assert piper_falso["hablantes"] == [1, 0, 1]


def test_piper_sin_modelos_descargados_dice_como_bajarlos(ajustes, monkeypatch, tmp_path):
    monkeypatch.setitem(sys.modules, "piper", None)
    monkeypatch.setattr(audio, "_piper", {})

    with pytest.raises(ErrorAudio, match="descargar_voces.py"):
        generar_audio("Hola.", tmp_path / "salida.wav", preferencia=PreferenciaVoz(modo="rapida"))


def test_piper_sin_su_paquete_pide_el_extra_audio(piper_falso, monkeypatch, tmp_path):
    monkeypatch.setitem(sys.modules, "piper", None)

    with pytest.raises(ErrorAudio, match=r"extra `audio`"):
        generar_audio("Hola.", tmp_path / "salida.wav", preferencia=PreferenciaVoz(modo="rapida"))


def test_si_piper_falla_no_se_cae_a_kokoro(ajustes, motores_falsos, monkeypatch, tmp_path):
    def _roto(*args):
        raise RuntimeError("onnx inválido")

    monkeypatch.setitem(audio.MOTORES, "piper", _roto)

    with pytest.raises(ErrorAudio, match="piper: onnx inválido"):
        generar_audio("Hola.", tmp_path / "salida.wav", preferencia=PreferenciaVoz(modo="rapida"))

    assert motores_falsos == []


# --- Falla visible, sin respaldo ------------------------------------------------


def test_si_kokoro_falla_no_se_cae_a_otro_motor(ajustes, motores_falsos, monkeypatch, tmp_path):
    def _roto(*args):
        raise RuntimeError("modelo corrupto")

    monkeypatch.setitem(audio.MOTORES, "kokoro", _roto)
    destino = tmp_path / "salida.wav"

    with pytest.raises(ErrorAudio, match="kokoro: modelo corrupto"):
        generar_audio("Hola.", destino)

    assert motores_falsos == []  # XTTS no se llamó
    assert list(tmp_path.iterdir()) == []  # ni WAV final ni temporal


def test_sin_modelos_descargados_el_error_dice_como_bajarlos(ajustes, tmp_path, monkeypatch):
    """El motor real, sin archivos: falla antes de importar nada y explica qué hacer."""
    monkeypatch.setitem(sys.modules, "kokoro_onnx", None)

    with pytest.raises(ErrorAudio, match="descargar_voces.py"):
        generar_audio("Hola.", tmp_path / "salida.wav")


def test_kokoro_sin_su_paquete_pide_el_extra_audio(ajustes, monkeypatch):
    voces = Path(ajustes.tts_modelos_dir)
    voces.mkdir()
    for nombre in (audio.KOKORO_MODELO, audio.KOKORO_VOCES):
        (voces / nombre).write_bytes(b"")
    monkeypatch.setitem(sys.modules, "kokoro_onnx", None)

    with pytest.raises(ErrorAudio, match=r"extra `audio`"):
        generar_audio("Hola.", voces / "salida.wav")


def test_el_motor_por_defecto_no_importa_xtts_ni_torch(
    ajustes, motores_falsos, monkeypatch, tmp_path
):
    """Una instalación con solo el extra `audio` no tiene TTS ni torch."""
    monkeypatch.setitem(sys.modules, "TTS", None)
    monkeypatch.setitem(sys.modules, "TTS.api", None)
    monkeypatch.setitem(sys.modules, "torch", None)

    generar_audio("Hola.", tmp_path / "salida.wav")

    assert motores_falsos[0][0] == "kokoro"


def test_el_visor_muestra_el_error_en_vez_de_un_audio(http_docente, monkeypatch):
    """Sin respaldo, la falla llega a la pantalla: la cápsula se sigue leyendo."""

    def _roto(*args, **kwargs):
        raise ErrorAudio("faltan los archivos de Kokoro")

    monkeypatch.setattr(audio, "generar_audio", _roto)

    respuesta = http_docente.post(
        "/student/viewer/0/generate-audio",
        data={"texto_override": "texto único para este test de falla visible"},
    )

    assert respuesta.status_code == 200
    assert "No se pudo generar el audio" in respuesta.text
    assert "faltan los archivos de Kokoro" in respuesta.text
    assert "<audio" not in respuesta.text


# --- Escritura atómica ------------------------------------------------------------


def test_el_wav_final_solo_aparece_cuando_la_sintesis_termina(ajustes, monkeypatch, tmp_path):
    destino = tmp_path / "salida.wav"
    vistos: list[bool] = []

    def _lento(guion, parcial, eleccion, language, ajustes):
        parcial.write_bytes(b"RIFF")
        # Mientras el motor escribe, el visor no debe ver el archivo final.
        vistos.append(destino.exists())
        assert parcial.parent == destino.parent

    monkeypatch.setitem(audio.MOTORES, "kokoro", _lento)

    generar_audio("Hola.", destino)

    assert vistos == [False]
    assert destino.read_bytes() == b"RIFF"
    assert [p.name for p in tmp_path.iterdir()] == ["salida.wav"]


def test_el_motor_recibe_el_guion_normalizado(ajustes, motores_falsos, tmp_path):
    generar_audio("Se escribe X → Y.", tmp_path / "salida.wav")

    assert motores_falsos[0][2] == "Se escribe equis determina ye."


# --- Clave del caché de audio (H10) -------------------------------------------------

DORA = VozElegida(motor="kokoro", voz="ef_dora")


def test_la_huella_es_un_nombre_de_archivo_estable(ajustes):
    huella = audio.huella_de_audio("Se escribe X → Y.", DORA, ajustes)

    assert len(huella) == 32 and all(c in "0123456789abcdef" for c in huella)
    assert huella == audio.huella_de_audio("Se escribe X → Y.", DORA, ajustes)


def test_la_huella_usa_el_guion_ya_normalizado(ajustes):
    """Dos textos que se narran igual comparten audio."""
    assert audio.huella_de_audio("Se escribe X → Y.", DORA, ajustes) == audio.huella_de_audio(
        "Se escribe X -> Y.", DORA, ajustes
    )


def test_cambiar_una_regla_de_normalizacion_invalida_el_cache(ajustes, monkeypatch):
    antes = audio.huella_de_audio("Se escribe X → Y.", DORA, ajustes)

    monkeypatch.setattr(audio, "normalizar_guion", lambda texto: texto)

    assert audio.huella_de_audio("Se escribe X → Y.", DORA, ajustes) != antes


@pytest.mark.parametrize(
    "otra",
    [
        VozElegida(motor="kokoro", voz="em_alex"),
        VozElegida(motor="piper", voz="es_ES-sharvard-medium", hablante=1),
        VozElegida(motor="xtts"),
    ],
)
def test_otra_voz_u_otro_motor_da_otro_archivo(ajustes, otra):
    assert audio.huella_de_audio("Hola.", otra, ajustes) != audio.huella_de_audio(
        "Hola.", DORA, ajustes
    )


def test_los_dos_hablantes_de_sharvard_no_comparten_archivo(ajustes):
    femenina = VozElegida(motor="piper", voz="es_ES-sharvard-medium", hablante=1)
    masculina = VozElegida(motor="piper", voz="es_ES-sharvard-medium", hablante=0)

    assert audio.huella_de_audio("Hola.", femenina, ajustes) != audio.huella_de_audio(
        "Hola.", masculina, ajustes
    )


def test_el_acento_de_kokoro_entra_en_la_clave_y_no_afecta_a_piper(ajustes, monkeypatch):
    piper = VozElegida(motor="piper", voz="es_ES-sharvard-medium", hablante=1)
    kokoro_419 = audio.huella_de_audio("Hola.", DORA, ajustes)
    piper_419 = audio.huella_de_audio("Hola.", piper, ajustes)

    monkeypatch.setattr(ajustes, "tts_kokoro_idioma", "es")

    assert audio.huella_de_audio("Hola.", DORA, ajustes) != kokoro_419
    assert audio.huella_de_audio("Hola.", piper, ajustes) == piper_419


# --- Normalización del guion -------------------------------------------------------


@pytest.mark.parametrize(
    ("entrada", "esperado"),
    [
        ("Se denota X → Y.", "Se denota equis determina ye."),
        ("si X → Y y Y → Z", "si equis determina ye y ye determina zeta"),
        ("X ⇒ Y, X ↔ Y, X ≠ Y", "equis implica ye, equis si y solo si ye, equis distinto de ye"),
        ("X -> Y y X => Y", "equis determina ye y equis implica ye"),
        ("(Y ⊆ X)", "(ye es subconjunto de equis)"),
        ("$X \\rightarrow Y$", "equis determina ye"),
        ("($t_1[X] = t_2[X]$)", "(te uno de equis igual a te dos de equis)"),
        ("el cierre (X)+ = X", "el cierre equis más igual a equis"),
        ("las dependencias F", "las dependencias efe"),
        ("Una DF.", "Una dependencia funcional."),
        ("Las DF y las DFs.", "Las dependencias funcionales y las dependencias funcionales."),
        ("Una Dependencia Funcional (DF) es", "Una Dependencia Funcional es"),
        (
            "la 3FN o la FNBC de la BD",
            "la tercera forma normal o la forma normal de Boyce-Codd de la base de datos",
        ),
        ("el RUT de una persona", "el rut de una persona"),
    ],
)
def test_normalizacion(entrada, esperado):
    assert normalizar_guion(entrada) == esperado


@pytest.mark.parametrize(
    "frase",
    ["A veces conviene repasar.", "Y luego se normaliza.", "O bien se separa la tabla."],
)
def test_una_vocal_mayuscula_que_es_palabra_no_se_lee_como_letra(frase):
    assert normalizar_guion(frase) == frase


def test_un_texto_sin_simbolos_no_cambia():
    texto = "La normalización reduce la redundancia de los datos, paso a paso."
    assert normalizar_guion(texto) == texto


def test_las_reglas_tienen_nombre_y_descripcion():
    """`REGLAS` es la lista que se documenta: cada una dice qué hace."""
    nombres = [r.nombre for r in REGLAS]
    assert len(nombres) == len(set(nombres))
    assert all(r.descripcion for r in REGLAS)
