"""Narración del visor: un guion de texto → un WAV.

**Motores.** Detrás de la misma firma de `generar_audio` hay tres motores:

- **Kokoro** (por defecto, modo «calidad»): ONNX en CPU, voces `ef_dora` y
  `em_alex`. Sintetiza a ~0,3–0,6 × la duración del audio (PRUEBAS_VARK.md).
- **Piper** (modo «rápida»): ONNX en CPU, un solo modelo
  (`es_ES-sharvard-medium`) con dos hablantes, 0 masculino y 1 femenino.
  Sintetiza a ~0,1 × la duración del audio.
- **XTTS-v2** (solo administrativo, `TTS_MOTOR=xtts`): clona la voz de
  `referencia.wav`; en CPU tarda 1,6–4 × la duración del audio. Su cuerpo es el
  de antes, sin cambios, en `_sintetizar_xtts`.

**El estudiante elige género y modo, no una voz.** La preferencia se guarda
como `PreferenciaVoz(genero, modo)` y `resolver_voz` la traduce a (motor, voz):
así conserva su elección de género si cambia de modo o si cambia el motor.

**Sin respaldo automático entre motores.** Si el motor elegido falla, el error
sube tal cual y el visor lo muestra: un respaldo silencioso cambiaría la voz
sin que nadie lo note y escondería que falta un modelo o un paquete.

**Carga perezosa.** Cada motor importa su paquete y carga su modelo la primera
vez que se usa, y nunca antes: una instalación con solo el extra `audio` no
necesita torch ni TTS, y viceversa.

**Escritura atómica.** El WAV se escribe en un archivo temporal del mismo
directorio y se renombra al terminar. El visor sirve el archivo apenas existe,
así que un WAV a medio escribir llegaría cortado al navegador.
"""

import logging
import os
import threading
import uuid
import wave
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from studify.config import Settings, get_settings
from studify.media.guion import normalizar_guion

from .memory_manager import vram_isolated

logger = logging.getLogger(__name__)

Genero = Literal["femenina", "masculina"]
Modo = Literal["calidad", "rapida"]

# Archivos de Kokoro dentro de `tts_modelos_dir` (los baja
# `scripts/descargar_voces.py`).
KOKORO_MODELO = "kokoro-v1.0.onnx"
KOKORO_VOCES = "voices-v1.0.bin"


class ErrorAudio(RuntimeError):
    """No se pudo sintetizar el audio con el motor elegido. No hay respaldo."""


@dataclass(frozen=True, slots=True)
class PreferenciaVoz:
    """Lo que elige el estudiante. Por defecto, voz femenina en modo calidad (Dora)."""

    genero: Genero = "femenina"
    modo: Modo = "calidad"


@dataclass(frozen=True, slots=True)
class VozElegida:
    """Con qué se sintetiza: motor, voz y, en modelos de varios hablantes, cuál."""

    motor: Literal["kokoro", "piper", "xtts"]
    voz: str | None = None
    hablante: int | None = None


def resolver_voz(
    preferencia: PreferenciaVoz | None = None, *, ajustes: Settings | None = None
) -> VozElegida:
    """Traduce la preferencia del estudiante a (motor, voz).

    `TTS_MOTOR=xtts` es una decisión administrativa y gana sobre la
    preferencia: XTTS clona una sola voz de referencia, así que no hay género
    que elegir.
    """
    ajustes = ajustes or get_settings()
    preferencia = preferencia or PreferenciaVoz()

    if ajustes.tts_motor == "xtts":
        return VozElegida(motor="xtts")

    if preferencia.modo == "rapida":
        hablante = (
            ajustes.tts_hablante_rapida_femenina
            if preferencia.genero == "femenina"
            else ajustes.tts_hablante_rapida_masculina
        )
        return VozElegida(motor="piper", voz=ajustes.tts_voz_rapida_modelo, hablante=hablante)

    voz = (
        ajustes.tts_voz_calidad_femenina
        if preferencia.genero == "femenina"
        else ajustes.tts_voz_calidad_masculina
    )
    return VozElegida(motor="kokoro", voz=voz)


def generar_audio(
    texto: str,
    output_path: Path,
    language: str = "es",
    *,
    preferencia: PreferenciaVoz | None = None,
) -> Path | None:
    """Sintetiza `texto` en `output_path` con la voz que corresponde a `preferencia`.

    El guion se normaliza antes (`media/guion.py`) para que los símbolos y las
    variables se lean con palabras. Levanta `ErrorAudio` si el motor falla; el
    archivo final solo aparece si la síntesis terminó bien.
    """
    ajustes = get_settings()
    eleccion = resolver_voz(preferencia, ajustes=ajustes)
    guion = normalizar_guion(texto)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    parcial = output_path.with_name(f".{output_path.stem}.{uuid.uuid4().hex}.partial.wav")
    try:
        MOTORES[eleccion.motor](guion, parcial, eleccion, language, ajustes)
        os.replace(parcial, output_path)
    except ErrorAudio:
        raise
    except Exception as exc:
        raise ErrorAudio(f"falló la síntesis con {eleccion.motor}: {exc}") from exc
    finally:
        parcial.unlink(missing_ok=True)

    logger.info("Audio %s (%s) generado en %s", eleccion.motor, eleccion.voz, output_path)
    return output_path


# --- Kokoro ---------------------------------------------------------------------

_kokoro = None
_kokoro_candado = threading.Lock()


def _cargar_kokoro(ajustes: Settings):
    """El modelo de Kokoro, cargado una vez por proceso (~0,8 s, ~400 MB)."""
    global _kokoro
    with _kokoro_candado:
        if _kokoro is not None:
            return _kokoro

        directorio = Path(ajustes.tts_modelos_dir)
        modelo, voces = directorio / KOKORO_MODELO, directorio / KOKORO_VOCES
        faltan = [str(p) for p in (modelo, voces) if not p.exists()]
        if faltan:
            raise ErrorAudio(
                f"faltan los archivos de Kokoro ({', '.join(faltan)}): ejecuta "
                f"`python scripts/descargar_voces.py`"
            )
        try:
            from kokoro_onnx import Kokoro
        except ImportError as err:
            raise ErrorAudio(
                "falta el paquete de Kokoro: instala el extra `audio` "
                "(`pip install -e .[audio]`)"
            ) from err

        _kokoro = Kokoro(str(modelo), str(voces))
        return _kokoro


def _sintetizar_kokoro(
    guion: str, destino: Path, eleccion: VozElegida, language: str, ajustes: Settings
) -> None:
    kokoro = _cargar_kokoro(ajustes)
    muestras, frecuencia = kokoro.create(
        guion, voice=eleccion.voz, speed=1.0, lang=ajustes.tts_kokoro_idioma
    )
    _escribir_wav(destino, muestras, frecuencia)


# --- Piper ----------------------------------------------------------------------

_piper: dict[str, object] = {}
_piper_candado = threading.Lock()


def _cargar_piper(modelo: str, ajustes: Settings):
    """El modelo de Piper, cargado una vez por proceso (~1,4 s, ~150 MB)."""
    with _piper_candado:
        if modelo in _piper:
            return _piper[modelo]

        directorio = Path(ajustes.tts_modelos_dir)
        onnx, config = directorio / f"{modelo}.onnx", directorio / f"{modelo}.onnx.json"
        faltan = [str(p) for p in (onnx, config) if not p.exists()]
        if faltan:
            raise ErrorAudio(
                f"faltan los archivos de Piper ({', '.join(faltan)}): ejecuta "
                f"`python scripts/descargar_voces.py`"
            )
        try:
            from piper import PiperVoice
        except ImportError as err:
            raise ErrorAudio(
                "falta el paquete de Piper: instala el extra `audio` "
                "(`pip install -e .[audio]`)"
            ) from err

        _piper[modelo] = PiperVoice.load(str(onnx), config_path=str(config))
        return _piper[modelo]


def _sintetizar_piper(
    guion: str, destino: Path, eleccion: VozElegida, language: str, ajustes: Settings
) -> None:
    voz = _cargar_piper(eleccion.voz, ajustes)
    from piper import SynthesisConfig

    # El hablante va siempre explícito: sin él Piper usaría el 0 por defecto,
    # y la estudiante que eligió voz femenina oiría la masculina.
    with wave.open(str(destino), "wb") as wf:
        voz.synthesize_wav(guion, wf, syn_config=SynthesisConfig(speaker_id=eleccion.hablante))


def _escribir_wav(destino: Path, muestras, frecuencia: int) -> None:
    """Muestras en coma flotante (−1…1) → WAV PCM de 16 bits mono."""
    import numpy as np

    pcm = (np.clip(muestras, -1.0, 1.0) * 32767).astype("<i2")
    with wave.open(str(destino), "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(frecuencia)
        wf.writeframes(pcm.tobytes())


# --- XTTS-v2 (administrativo) ---------------------------------------------------


def _xtts(guion: str, destino: Path, eleccion: VozElegida, language: str, ajustes: Settings):
    _sintetizar_xtts(guion, destino, language)


def _sintetizar_xtts(texto: str, output_path: Path, language: str = "es") -> Path | None:
    """
    Genera audio usando exclusivamente el modelo neuronal XTTS-v2 de Coqui TTS
    con clonación de voz basada en un archivo de referencia (speaker_wav).
    Aplica aislación de VRAM estricta.
    """
    output_path.parent.mkdir(parents=True, exist_ok=True)

    try:
        import torch
        from TTS.api import TTS

        # --- PARCHE PARA PYTORCH 2.6+ ---
        # Desactivamos el bloqueo estricto de seguridad para permitir la carga de XTTS (una sola vez)
        if not getattr(torch, "_xtts_patched", False):
            _original_load = torch.load

            def _patched_load(*args, **kwargs):
                kwargs["weights_only"] = False
                return _original_load(*args, **kwargs)

            torch.load = _patched_load
            torch._xtts_patched = True
        # ---------------------------------

    except ImportError as err:
        logger.error(f"Error al importar dependencias de XTTS-v2 (TTS/torch): {err}")
        raise RuntimeError(
            "No se puede generar audio: se requiere el paquete TTS de Coqui instalado."
        ) from err

    # XTTS necesita un audio de referencia para clonar la voz.
    # Buscamos 'referencia.wav' en tests/ o data/
    ref_path = Path("tests/referencia.wav")
    if not ref_path.exists():
        ref_path = Path("data/referencia.wav")
        if not ref_path.exists():
            raise FileNotFoundError(
                "No se encontró el archivo 'referencia.wav' para clonación de voz en XTTS-v2. "
                "Debe existir en tests/referencia.wav o data/referencia.wav"
            )

    with vram_isolated():
        logger.info("Cargando XTTS-v2 en memoria...")
        os.environ["COQUI_TOS_AGREED"] = "1"
        device = "cuda" if torch.cuda.is_available() else "cpu"
        tts = TTS("tts_models/multilingual/multi-dataset/xtts_v2").to(device)

        logger.info(f"Sintetizando audio con XTTS-v2 ({device})...")
        tts.tts_to_file(
            text=texto,
            speaker_wav=str(ref_path),
            language=language,
            file_path=str(output_path),
        )
        logger.info(f"Audio XTTS-v2 generado exitosamente en {output_path}")

        del tts

    return output_path


Motor = Callable[[str, Path, VozElegida, str, Settings], None]

MOTORES: dict[str, Motor] = {
    "kokoro": _sintetizar_kokoro,
    "piper": _sintetizar_piper,
    "xtts": _xtts,
}
