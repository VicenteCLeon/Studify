import sys
from pathlib import Path

# Añadimos src al path para que pueda importar studify
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from studify.media.image import generar_imagen

print("--- INICIANDO PRUEBA VISUAL REALISTA ---")

# Prompt educativo para probar generación de infografías y texto
prompt_visual = "A high quality educational infographic explaining 'THE WATER CYCLE'. Clean vector art style, modern layout. It features three main sections with clear typography: 'EVAPORATION' with an arrow going up from the ocean, 'CONDENSATION' showing clouds forming, and 'PRECIPITATION' showing rain falling on mountains. Minimalist flat design, blue and green color palette, highly detailed, text is clearly legible, white background."
ruta_salida = Path("prueba_visual.png")

print("Cargando Stable Diffusion 3 Medium en la tarjeta gráfica...")
print("(Nota: La primera vez descargará el modelo desde HuggingFace)")

resultado = generar_imagen(prompt_visual, ruta_salida)

if resultado:
    print(f"\n¡Proceso terminado! Revisa la imagen generada en: {resultado.absolute()}")
else:
    print("\nOcurrió un error durante la generación. Revisa los logs arriba.")
