"""Paquete de tests.

Es un paquete regular (y no una carpeta suelta) a propósito: `gruut`, una
dependencia de Coqui TTS, instala su propio paquete `tests` en site-packages.
Sin este archivo, `tests/` del repo era un *namespace package* y Python
prefería el paquete regular de gruut, así que `from tests.conftest import …`
fallaba y 12 archivos de tests no se podían ni importar (hallazgo H9 de
docs/PRUEBAS_VARK.md, 04-oct-2026). Con `__init__.py`, pytest antepone la raíz
del repo a `sys.path` y `tests` resuelve siempre a esta carpeta.
"""
