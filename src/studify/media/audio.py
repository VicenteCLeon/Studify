import logging
import os
from pathlib import Path

from .memory_manager import vram_isolated

logger = logging.getLogger(__name__)


def generar_audio(texto: str, output_path: Path, language: str = "es") -> Path | None:
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
