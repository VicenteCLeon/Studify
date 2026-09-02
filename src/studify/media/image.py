import logging
from pathlib import Path

from .memory_manager import vram_isolated

logger = logging.getLogger(__name__)


def generar_imagen(prompt: str, output_path: Path) -> Path | None:
    """
    Genera una imagen usando Z-Image Turbo (Alibaba) en FP16 y la guarda.
    Aplica aislación de VRAM estricta y utiliza DirectML para hardware AMD.
    """
    try:
        import torch
        import torch_directml
        from diffusers import AutoPipelineForText2Image, AutoencoderKL
    except ImportError:
        logger.warning(
            "Faltan dependencias de imagen (torch, torch_directml, diffusers). Ignorando."
        )
        return None

    # Mantenemos tu offload estricto de arquitectura
    with vram_isolated():
        try:
            logger.info("Detectando GPU AMD mediante DirectML...")
            dml_device = torch_directml.device()

            # El VAE original de SDXL tiene el mismo bug matemático de AMD que tira pantallas negras/blancas en FP16.
            # Cargamos este VAE oficial corregido para FP16 que da la máxima calidad sin fallar.
            logger.info("Cargando VAE FP16 Fix para evitar imágenes en negro...")
            vae = AutoencoderKL.from_pretrained(
                "madebyollin/sdxl-vae-fp16-fix", 
                torch_dtype=torch.float16
            )

            logger.info("Cargando SDXL Base 1.0 en la VRAM de AMD (Alta calidad)...")
            pipe = AutoPipelineForText2Image.from_pretrained(
                "stabilityai/stable-diffusion-xl-base-1.0", 
                vae=vae,
                torch_dtype=torch.float16,
                variant="fp16",
                use_safetensors=True
            )
            
            # Mandamos el modelo a la GPU
            pipe.to(dml_device)
            
            # Slicing agresivo (slice_size=1): procesa la atención de a UN head a la vez.
            # Más lento, pero usa la VRAM mínima posible en el mid_block de SDXL.
            pipe.enable_attention_slicing(1)
        except Exception as e:
            logger.error(f"Error cargando SDXL Base: {e}")
            return None

        logger.info("Generando infografía de alta calidad (25 pasos en SDXL)...")
        # SDXL Base soporta 768x768 perfectamente en 8GB. 1024x1024 necesita >10GB.
        result = pipe(
            prompt,
            height=768,
            width=768,
            output_type="pil",
            num_inference_steps=25,
            guidance_scale=7.5, 
            generator=torch.Generator("cpu").manual_seed(42),
        ).images[0]

        result.save(output_path)
        logger.info(f"Imagen generada exitosamente en {output_path}")

        # Obligamos a borrar el pipeline de la VRAM
        del pipe

    return output_path
