"""Script de prueba de generación de audio para el tema Primera Forma Normal (1FN).

Utiliza la función `generar_audio` de `studify.media.audio` (XTTS-v2 / TTS)
con el archivo de referencia de voz `tests/referencia.wav`.
"""

import sys
from pathlib import Path

# Añadir src al path para importar studify
sys.path.insert(0, str(Path("src").resolve()))

from studify.media.audio import generar_audio

TEXTO_EXPLICACION_1FN = (
    "La Primera Forma Normal, o uno F N, es la regla basica de la normalizacion "
    "relacional en bases de datos. Significa que cada celda de una tabla debe "
    "contener un valor atomico e indivisible, eliminando cualquier lista o "
    "conjunto de datos repetidos. Por ejemplo, guardar varios numeros de telefono "
    "en una sola columna dificulta hacer busquedas precisas en S Q L. Al aplicar la "
    "Primera Forma Normal, cada telefono se ubica en su propia fila, garantizando "
    "consultas mas rapidas y una estructura limpia."
)

OUTPUT_WAV = Path("data/audio_prueba_1fn.wav")


def main():
    print("=== Prueba de Generacion de Audio para 1FN ===")
    print(f"Texto a sintetizar: '{TEXTO_EXPLICACION_1FN}'")
    print(f"Archivo de salida objetivo: {OUTPUT_WAV.resolve()}")

    res = generar_audio(TEXTO_EXPLICACION_1FN, OUTPUT_WAV, language="es")

    if res and res.exists():
        size_kb = res.stat().st_size / 1024
        print("\n[EXITO] Audio generado correctamente!")
        print(f"  - Ruta: {res.resolve()}")
        print(f"  - Tamaño: {size_kb:.2f} KB")
    else:
        print("\n[ERR] No se pudo generar el archivo de audio. Revisa los logs.")


if __name__ == "__main__":
    main()
