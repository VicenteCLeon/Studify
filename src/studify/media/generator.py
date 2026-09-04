import logging
from pathlib import Path

from .audio import generar_audio
from .image import generar_imagen

logger = logging.getLogger(__name__)


class GeneradorMultimedia:
    """
    Orquesta la generación secuencial de media (Fase 6) basándose en
    la configuración VARK y el contenido textual generado por el LLM.
    """

    def __init__(self, output_dir: Path):
        self.output_dir = output_dir
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def generar_activos(
        self, configuracion: object, texto_capsula: str, id_capsula: str
    ) -> dict[str, Path | None]:
        """
        Ejecuta de forma estrictamente secuencial la generación de multimedia (imagen y audio).
        """
        resultados = {"visual": None, "auditivo": None}

        # 1. Canal Visual (V) -> Genera Imagen
        if getattr(configuracion, "recursos_visuales", 0) > 0:
            logger.info("El perfil VARK requiere recursos visuales. Ejecutando FLUX.1...")
            prompt_visual = f"Educational highly detailed illustration of the core concept about: {texto_capsula[:100]}"
            out_img = self.output_dir / f"{id_capsula}_visual.png"
            resultados["visual"] = generar_imagen(prompt_visual, out_img)

        # 2. Canal Auditivo (A) -> Genera Audio
        if getattr(configuracion, "audio_activo", False):
            logger.info("El perfil VARK requiere recursos auditivos. Ejecutando XTTS-v2...")
            out_audio = self.output_dir / f"{id_capsula}_audio.wav"
            resultados["auditivo"] = generar_audio(texto_capsula[:250], out_audio)

        return resultados
