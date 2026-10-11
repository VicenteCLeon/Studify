"""Exporta esquemas a PNG con las fuentes del sitio, para mostrarlos fuera de la app.

El SVG del render determinístico pide `Figtree` y `Fraunces`, que el navegador
solo tiene dentro de Studify. Para que un PNG se vea igual que en el visor, este
script arma una página con las fuentes autoalojadas de `src/studify/web/static/fonts`
incrustadas, y le saca una captura con Chrome o Edge en modo headless.

Por cada especificación genera tres archivos:

    <nombre>_1600.png        el esquema a 1600 px de ancho, para adjuntar
    <nombre>_movil_375.png   pantalla de 375 px de ancho, a tamaño real (1×)
    <nombre>_movil_375@2x.png  la misma pantalla con la nitidez de un teléfono (2×)

La vista móvil reproduce el visor: fondo y margen lateral de `app.css`, y el
esquema ocupando el ancho disponible. Sirve para juzgar el tamaño del texto; el
archivo 1× es el que hay que mirar al 100 %.

Uso (desde la raíz del repo):

    python docs/modulo-visual/pruebas/exportar_png.py PROG-U1-01_c2 BD-U3-02_c1
    python docs/modulo-visual/pruebas/exportar_png.py --todas --destino <carpeta>
"""

import argparse
import base64
import json
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from PIL import Image

AQUI = Path(__file__).resolve().parent
RAIZ = AQUI.parents[2]
sys.path.insert(0, str(AQUI))

import generar_pruebas as base  # noqa: E402

FUENTES = RAIZ / "src" / "studify" / "web" / "static" / "fonts"
SPECS_LLM = AQUI / "specs_llm"
DESTINO = AQUI / "resultados" / "para_correo"

NAVEGADORES = (
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
    "chrome",
    "chromium",
    "msedge",
)

# Tokens de `app.css`: fondo de la página y margen lateral (`--gutter`) a 375 px.
FONDO_PAGINA = "#FBF8F3"
ANCHO_MOVIL = 375
MARGEN_MOVIL = 17
# La ventana headless no baja de ~500 px en Windows: se captura más ancho y se recorta.
ANCHO_VENTANA = 1000


def _font_faces() -> str:
    """Los mismos `@font-face` de `app.css`, con los archivos incrustados."""
    caras = []
    for familia, archivo, peso in (
        ("Figtree", "figtree-latin.woff2", "300 900"),
        ("Fraunces", "fraunces-latin.woff2", "500 700"),
    ):
        datos = base64.b64encode((FUENTES / archivo).read_bytes()).decode("ascii")
        caras.append(
            f'@font-face {{ font-family: "{familia}"; font-style: normal; font-weight: {peso}; '
            f'font-display: block; src: url("data:font/woff2;base64,{datos}") format("woff2"); }}'
        )
    return "\n".join(caras)


def _navegador() -> str:
    for candidato in NAVEGADORES:
        ruta = candidato if Path(candidato).exists() else shutil.which(candidato)
        if ruta:
            return str(ruta)
    raise SystemExit("no se encontró Chrome ni Edge para sacar la captura")


def _capturar(html: str, destino: Path, ancho: int, alto: int, escala: int) -> None:
    """Captura la esquina superior izquierda de la página, de `ancho` × `alto` px CSS."""
    with tempfile.TemporaryDirectory() as tmp:
        pagina = Path(tmp) / "pagina.html"
        cruda = Path(tmp) / "captura.png"
        pagina.write_text(html, encoding="utf-8")
        subprocess.run(
            [
                _navegador(),
                "--headless=new",
                "--disable-gpu",
                "--hide-scrollbars",
                "--no-first-run",
                f"--user-data-dir={Path(tmp) / 'perfil'}",
                f"--force-device-scale-factor={escala}",
                f"--window-size={max(ancho, ANCHO_VENTANA)},{alto + 200}",
                # Espera a que las fuentes incrustadas terminen de cargar.
                "--virtual-time-budget=4000",
                f"--screenshot={cruda}",
                pagina.as_uri(),
            ],
            check=True,
            capture_output=True,
            timeout=120,
        )
        with Image.open(cruda) as imagen:
            imagen.crop((0, 0, ancho * escala, alto * escala)).save(destino, optimize=True)


def _dimensiones(svg: str) -> tuple[int, int]:
    ancho, alto = re.search(r'viewBox="0 0 (\d+) (\d+)"', svg).groups()
    return int(ancho), int(alto)


def exportar(nombre: str, spec: dict, destino: Path) -> list[Path]:
    svg = base.renderizar_svg(spec)
    ancho, alto = _dimensiones(svg)
    caras = _font_faces()
    salidas = []

    # 1600 px: el SVG a su tamaño natural (800 px CSS) con densidad 2×.
    pagina = (
        f"<!doctype html><meta charset='utf-8'><style>{caras}\n"
        "html, body { margin: 0; background: #FFFFFF; } svg { display: block; }</style>" + svg
    )
    salida = destino / f"{nombre}_1600.png"
    _capturar(pagina, salida, ancho, alto, 1600 // ancho)
    salidas.append(salida)

    # Móvil: el esquema encogido al ancho útil del visor en una pantalla de 375 px.
    util = ANCHO_MOVIL - 2 * MARGEN_MOVIL
    alto_movil = round(alto * util / ancho) + 2 * MARGEN_MOVIL
    svg_movil = re.sub(r' width="\d+" height="\d+"', ' width="100%" height="auto"', svg, count=1)
    pagina = (
        f"<!doctype html><meta charset='utf-8'><style>{caras}\n"
        "html, body { margin: 0; background: #FFFFFF; }\n"
        f".pantalla {{ width: {ANCHO_MOVIL}px; box-sizing: border-box; padding: {MARGEN_MOVIL}px; "
        f"background: {FONDO_PAGINA}; }} svg {{ display: block; }}</style>"
        f"<div class='pantalla'>{svg_movil}</div>"
    )
    for escala, sufijo in ((1, ""), (2, "@2x")):
        salida = destino / f"{nombre}_movil_375{sufijo}.png"
        _capturar(pagina, salida, ANCHO_MOVIL, alto_movil, escala)
        salidas.append(salida)
    return salidas


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("nombres", nargs="*", help="nombres en specs_llm/, sin .json")
    parser.add_argument("--todas", action="store_true")
    parser.add_argument("--destino", type=Path, default=DESTINO)
    args = parser.parse_args()

    nombres = args.nombres
    if args.todas:
        nombres = sorted(p.stem for p in SPECS_LLM.glob("*_c?.json"))
    if not nombres:
        parser.error("indica al menos una especificación, o --todas")
    args.destino.mkdir(parents=True, exist_ok=True)
    for nombre in nombres:
        spec = json.loads((SPECS_LLM / f"{nombre}.json").read_text(encoding="utf-8"))
        for salida in exportar(nombre, spec, args.destino):
            with Image.open(salida) as imagen:
                print(f"{salida.name}: {imagen.width} × {imagen.height} px")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
