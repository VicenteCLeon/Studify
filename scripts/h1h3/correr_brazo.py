"""Corre la batería real (scripts/probar_perfiles_vark.py) contra una variante de `data/h1h3/`.

    python scripts/h1h3/correr_brazo.py <base|prefijo|A|B_topes|B> [propias] [de la batería]

Opciones propias (se quitan antes de pasarle el resto a la batería):
    --s44             reemplaza la batería por 6 perfiles fijos con K 38–39 % (zona K 31–39 %) que
                      reciben la actividad aplicada por la red de seguridad de `rules.py`
    --slugs A,B,...   corre solo esos perfiles (rescates de R1)
    --repetir N       ejecuta la corrida N veces seguidas (rescates de R1: --slugs X --repetir 5)

No modifica el repo: antepone `data/h1h3/<variante>/src` al sys.path y `studify` sale de la copia.
En corridas --live exige --doc: sin eso la batería reescribe docs/PRUEBAS_VARK.md.
Hay que correrlo desde la raíz del repo.
"""

import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
SALIDA = RAIZ / "data" / "h1h3"

S44 = [(25, 37, 38), (37, 25, 38), (25, 36, 39), (33, 28, 39), (38, 23, 39), (23, 38, 39)]


def sacar(argv: list[str], bandera: str, *, con_valor: bool) -> tuple[list[str], str | bool | None]:
    if bandera not in argv:
        return argv, None
    i = argv.index(bandera)
    if con_valor:
        return argv[:i] + argv[i + 2 :], argv[i + 1]
    return argv[:i] + argv[i + 1 :], True


def main() -> int:
    argv = sys.argv[1:]
    if not argv:
        raise SystemExit(__doc__)
    variante, resto = argv[0], argv[1:]
    raiz_variante = SALIDA / variante
    if not (raiz_variante / "src" / "studify").is_dir():
        raise SystemExit(f"no existe {raiz_variante}: corre scripts/h1h3/hacer_variantes.py")

    resto, s44 = sacar(resto, "--s44", con_valor=False)
    resto, slugs = sacar(resto, "--slugs", con_valor=True)
    resto, repetir = sacar(resto, "--repetir", con_valor=True)

    sys.path.insert(0, str(RAIZ))
    sys.path.insert(0, str(RAIZ / "scripts"))
    sys.path.insert(0, str(raiz_variante / "src"))

    import studify

    origen = Path(studify.__file__).parent
    if not str(origen).startswith(str(raiz_variante)):
        raise SystemExit(f"studify no sale de la variante pedida: {origen}")
    print(f"[correr_brazo] studify desde {origen}", flush=True)

    import probar_perfiles_vark as bateria

    from studify.vark.rules import aplicar_reglas

    if "--live" in resto and "--doc" not in resto:
        raise SystemExit("falta --doc <ruta fuera de docs/>: evita reescribir docs/PRUEBAS_VARK.md")

    if s44:
        fijos = [
            bateria.Perfil("C", f"S44{chr(97 + i)}_A{a}-R{r}-K{k}", a=a, r=r, k=k)
            for i, (a, r, k) in enumerate(S44)
        ]
        for perfil in fijos:
            directivas = aplicar_reglas(perfil.vark()).directivas
            if "actividad_aplicada" not in directivas:
                raise SystemExit(f"{perfil.slug} no recibe la actividad aplicada: revisa S44")
        bateria.construir_bateria = lambda fases, n, semilla: fijos
    if slugs:
        pedidos = set(slugs.split(","))
        base = bateria.construir_bateria
        bateria.construir_bateria = lambda f, n, s: [p for p in base(f, n, s) if p.slug in pedidos]

    codigo = 0
    for _ in range(int(repetir or 1)):
        codigo = bateria.main(resto) or codigo
    return codigo


if __name__ == "__main__":
    raise SystemExit(main())
