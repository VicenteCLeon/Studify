import gc
import logging
from contextlib import contextmanager

logger = logging.getLogger(__name__)


@contextmanager
def vram_isolated():
    """
    Context manager utilitario para limpiar la VRAM de forma segura antes
    y después de cada inferencia pesada (FLUX, XTTS, SVD).
    Garantiza que no haya acumulación de memoria entre canales.
    """
    try:
        import torch

        has_torch = True
    except ImportError:
        has_torch = False

    def clean_memory():
        gc.collect()
        if has_torch and torch.cuda.is_available():
            torch.cuda.empty_cache()

    # Limpieza preventiva antes de iniciar
    clean_memory()
    logger.info("VRAM limpiada (pre-generación).")

    try:
        yield
    finally:
        # Limpieza obligatoria tras la inferencia
        clean_memory()
        logger.info("VRAM limpiada (post-generación).")
