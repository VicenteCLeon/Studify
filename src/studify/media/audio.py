import logging
import os
from pathlib import Path

from .memory_manager import vram_isolated

logger = logging.getLogger(__name__)


def generar_audio(texto: str, output_path: Path, language: str = "es") -> Path | None:
    """
    Genera audio usando XTTS-v2 de Coqui TTS y lo guarda.
    Aplica aislación de VRAM estricta.
    """
    try:
        import torch
        from TTS.api import TTS

        # --- PARCHE PARA PYTORCH 2.6+ ---
        # Desactivamos el bloqueo estricto de seguridad para permitir la carga de XTTS
        _original_load = torch.load

        def _patched_load(*args, **kwargs):
            kwargs["weights_only"] = False
            return _original_load(*args, **kwargs)

        torch.load = _patched_load
        # ---------------------------------

    except ImportError:
        logger.warning("Faltan dependencias de audio (TTS, torch). Ignorando.")
        return None

    with vram_isolated():
        logger.info("Cargando XTTS-v2 en memoria...")
        try:
            # XTTS-v2 requiere confirmación de licencia (CPML)
            os.environ["COQUI_TOS_AGREED"] = "1"
            device = "cuda" if torch.cuda.is_available() else "cpu"
            tts = TTS("tts_models/multilingual/multi-dataset/xtts_v2").to(device)
        except Exception as e:
            logger.error(f"Error cargando XTTS-v2: {e}")
            return None

        logger.info("Generando audio...")
        # XTTS necesita un audio de referencia para clonar la voz.
        # Buscamos un archivo 'referencia.wav' en la carpeta data o en tests como fallback
        ref_path = Path("data/referencia.wav")
        if not ref_path.exists():
            ref_path = Path("tests/referencia.wav")
            if not ref_path.exists():
                logger.error("No se encontró referencia.wav en data/ ni tests/. XTTS lo necesita.")
                return None

        tts.tts_to_file(
            text=texto, speaker_wav=str(ref_path), language=language, file_path=str(output_path)
        )
        logger.info(f"Audio generado exitosamente en {output_path}")

        del tts

    return output_path
