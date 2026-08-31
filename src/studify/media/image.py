import logging
from pathlib import Path

from .memory_manager import vram_isolated

logger = logging.getLogger(__name__)


def generar_imagen(prompt: str, output_path: Path) -> Path | None:
    """
    Genera una imagen usando FLUX.1 [schnell] en FP8 y la guarda.
    Aplica aislación de VRAM estricta.
    """
    try:
        import torch
        from diffusers import FluxPipeline
    except ImportError:
        logger.warning("Faltan dependencias de imagen (torch, diffusers). Ignorando.")
        return None

    # Offload estricto
    with vram_isolated():
        logger.info("Cargando FLUX.1 [schnell] en memoria...")
        # Usa bfloat16 o float8 según la GPU, Schnell es el destilado rápido
        try:
            pipe = FluxPipeline.from_pretrained(
                "black-forest-labs/FLUX.1-schnell", torch_dtype=torch.bfloat16
            )
            # Para GPUs con menos de 16GB, es vital activar el CPU offloading
            pipe.enable_model_cpu_offload()
        except Exception as e:
            logger.error(f"Error cargando FLUX.1: {e}")
            return None

        logger.info("Generando imagen (1 a 4 steps máximo para Schnell)...")
        # Schnell requiere solo ~4 pasos de inferencia
        result = pipe(
            prompt,
            output_type="pil",
            num_inference_steps=4,
            generator=torch.Generator("cpu").manual_seed(42),  # Semilla determinista opcional
        ).images[0]

        result.save(output_path)
        logger.info(f"Imagen generada exitosamente en {output_path}")

        # Obligamos a borrar el pipeline de la memoria de Python
        del pipe

    return output_path
