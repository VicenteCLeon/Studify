"""La narración de una cápsula: qué se narra y en qué archivo queda.

Lo usan el visor, que sintetiza (`routers/student.py`), y la supresión, que
borra (`routers/legal.py`). Están juntos porque tienen que coincidir: si la
supresión calculara el guion o el directorio por su cuenta, bastaría con que el
visor cambiara uno de los dos para que los audios dejaran de borrarse sin
ningún aviso. Eso ya pasó: desde H10 los WAV se nombran por huella y la
supresión seguía buscando `capsula_{id}.wav`.
"""

from collections.abc import Iterable
from pathlib import Path

from studify.config import Settings
from studify.media import audio

# Junto al paquete y no relativo al directorio de trabajo: es la carpeta que
# `main.py` publica en `/public`. Con una ruta relativa, arrancar el servidor
# desde otra carpeta escribía los audios en un lugar que nadie sirve ni borra.
DIRECTORIO_AUDIO = Path(__file__).resolve().parents[1] / "public" / "audio"

# Lo que se narra cuando la cápsula no trae ni activación ni concepto. Es un
# texto genérico, común a todos: no es dato de ningún estudiante.
GUION_POR_DEFECTO = (
    "Esta es una microcápsula adaptativa sintetizada con IA para el canal auditivo."
)


def guion(contenido_json: dict | None) -> str:
    """El texto que se narra de una cápsula: la activación y el concepto central."""
    contenido = contenido_json or {}
    texto = f"{contenido.get('activacion', '')} {contenido.get('concepto_central', '')}"
    return texto.strip() or GUION_POR_DEFECTO


def archivos(guiones: Iterable[str], ajustes: Settings | None = None) -> set[str]:
    """Los nombres de WAV que pueden existir para estos guiones, con cualquier voz.

    El guion genérico se deja fuera: lo comparten todas las cápsulas sin texto
    y no pertenece a nadie.
    """
    return {
        f"{audio.huella_de_audio(texto, voz, ajustes)}.wav"
        for texto in guiones
        if texto != GUION_POR_DEFECTO
        for voz in audio.voces_posibles(ajustes)
    }
