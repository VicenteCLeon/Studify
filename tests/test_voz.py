import torch
from TTS.api import TTS

print("--- INICIANDO PRUEBA REALISTA ---")

# --- PARCHE PARA PYTORCH 2.6+ ---
# Desactivamos el bloqueo estricto de seguridad para permitir la carga de XTTS
_original_load = torch.load


def _patched_load(*args, **kwargs):
    kwargs["weights_only"] = False
    return _original_load(*args, **kwargs)


torch.load = _patched_load
# ---------------------------------

print("Cargando XTTS-v2 en la tarjeta gráfica...")
tts = TTS("tts_models/multilingual/multi-dataset/xtts_v2").to(
    "cuda" if torch.cuda.is_available() else "cpu"
)

print("Sintetizando clonación de voz...")
tts.tts_to_file(
    text="Hola Vicente Cisternas. Como puedes notar, la diferencia en la calidad y la entonación de este modelo es abismal, podemos clonar voces usando de referencia un archivo de audio.",
    speaker_wav="referencia.wav",
    language="es",
    file_path="prueba_realista.wav",
)
print("¡Proceso terminado! Revisa prueba_realista.wav")
