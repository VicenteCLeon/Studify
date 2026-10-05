"""Descarga los modelos de voz del visor a `tts_modelos_dir` (por defecto `data/voces`).

Uso:
    python scripts/descargar_voces.py            # Kokoro y Piper
    python scripts/descargar_voces.py --forzar   # vuelve a bajar aunque ya estén

Los modelos no se versionan (pesan ~410 MB y `data/` está en `.gitignore`), así
que cada instalación los baja con este script. Cada archivo se verifica contra
su SHA-256: si la fuente cambia el archivo, el script falla en vez de dejar un
modelo distinto del que se midió en PRUEBAS_VARK.md.

Licencias (ver PRUEBAS_VARK.md, «Licencias»):
- Kokoro: pesos Apache-2.0 (hexgrad/Kokoro-82M); `kokoro-onnx` es MIT, pero
  depende de `phonemizer` y `espeak-ng`, que son GPL-3.0.
- Piper `es_ES-sharvard-medium`: datos CC BY 3.0, **exige atribución**; el
  paquete `piper-tts` es GPL-3.0.
"""

import argparse
import hashlib
import os
import sys
import urllib.request
from dataclasses import dataclass
from pathlib import Path

# Como los demás scripts: así funciona aunque `studify` no esté instalado en el
# entorno (con `pip install -e .` ya resuelve a `src/` por sí solo).
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from studify.config import get_settings  # noqa: E402

KOKORO_BASE = "https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0"
# Commit fijo de rhasspy/piper-voices (no `main`), para que la URL apunte siempre
# al mismo archivo. Su SHA-256 se verificó contra el MD5 de `voices.json`.
PIPER_REVISION = "c10ece1aade47bb51c153c893d14e5bf8e5b7117"
PIPER_BASE = (
    f"https://huggingface.co/rhasspy/piper-voices/resolve/{PIPER_REVISION}"
    "/es/es_ES/sharvard/medium"
)


@dataclass(frozen=True)
class Archivo:
    nombre: str
    url: str
    sha256: str


ARCHIVOS = (
    Archivo(
        "kokoro-v1.0.onnx",
        f"{KOKORO_BASE}/kokoro-v1.0.onnx",
        "7d5df8ecf7d4b1878015a32686053fd0eebe2bc377234608764cc0ef3636a6c5",
    ),
    Archivo(
        "voices-v1.0.bin",
        f"{KOKORO_BASE}/voices-v1.0.bin",
        "bca610b8308e8d99f32e6fe4197e7ec01679264efed0cac9140fe9c29f1fbf7d",
    ),
    Archivo(
        "es_ES-sharvard-medium.onnx",
        f"{PIPER_BASE}/es_ES-sharvard-medium.onnx",
        "40febfb1679c69a4505ff311dc136e121e3419a13a290ef264fdf43ddedd0fb1",
    ),
    Archivo(
        "es_ES-sharvard-medium.onnx.json",
        f"{PIPER_BASE}/es_ES-sharvard-medium.onnx.json",
        "7438c9b699c72b0c3388dae1b68d3f364dc66a2150fe554a1c11f03372957b2c",
    ),
)


def sha256(ruta: Path) -> str:
    h = hashlib.sha256()
    with ruta.open("rb") as f:
        for bloque in iter(lambda: f.read(1 << 20), b""):
            h.update(bloque)
    return h.hexdigest()


def descargar(archivo: Archivo, directorio: Path, *, forzar: bool) -> None:
    destino = directorio / archivo.nombre
    if destino.exists() and not forzar:
        if sha256(destino) == archivo.sha256:
            print(f"ok      {archivo.nombre} (ya estaba)")
            return
        print(f"aviso   {archivo.nombre} existe pero su SHA-256 no coincide; se vuelve a bajar")

    parcial = destino.with_name(destino.name + ".partial")
    print(f"bajando {archivo.nombre} …", flush=True)
    try:
        urllib.request.urlretrieve(archivo.url, parcial)
        obtenido = sha256(parcial)
        if obtenido != archivo.sha256:
            raise SystemExit(
                f"error   {archivo.nombre}: SHA-256 {obtenido} no coincide con "
                f"{archivo.sha256}. No se instala."
            )
        os.replace(parcial, destino)
    finally:
        parcial.unlink(missing_ok=True)
    print(f"ok      {archivo.nombre} ({destino.stat().st_size / 2**20:.0f} MB)")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--forzar", action="store_true", help="vuelve a bajar todo")
    args = parser.parse_args()

    directorio = Path(get_settings().tts_modelos_dir)
    directorio.mkdir(parents=True, exist_ok=True)
    for archivo in ARCHIVOS:
        descargar(archivo, directorio, forzar=args.forzar)
    print(f"modelos en {directorio.resolve()}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
