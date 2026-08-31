import logging
from pathlib import Path

from .memory_manager import vram_isolated

logger = logging.getLogger(__name__)


def generar_video(imagen_base: Path, output_path: Path) -> Path | None:
    """
    Genera un video corto usando Stable Video Diffusion (SVD)
    a partir de una imagen inicial generada por FLUX.1.
    """
    try:
        import torch
        from diffusers import StableVideoDiffusionPipeline
        from diffusers.utils import export_to_video, load_image
    except ImportError:
        logger.warning("Faltan dependencias de video (diffusers, torch). Ignorando.")
        return None

    with vram_isolated():
        logger.info("Cargando SVD en memoria...")
        try:
            pipe = StableVideoDiffusionPipeline.from_pretrained(
                "stabilityai/stable-video-diffusion-img2vid-xt",
                torch_dtype=torch.float16,
                variant="fp16",
            )
            pipe.enable_model_cpu_offload()
        except Exception as e:
            logger.error(f"Error cargando SVD: {e}")
            return None

        logger.info("Generando video a partir de imagen...")
        image = load_image(str(imagen_base))
        # SVD requiere que las imágenes sean redimensionadas típicamente a 1024x576 o 576x1024
        image = image.resize((1024, 576))

        generator = torch.manual_seed(42)
        frames = pipe(image, decode_chunk_size=8, generator=generator, num_frames=25).frames[0]

        export_to_video(frames, str(output_path), fps=7)
        logger.info(f"Video generado exitosamente en {output_path}")

        del pipe

    return output_path
