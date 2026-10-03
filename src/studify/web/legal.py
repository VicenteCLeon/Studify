"""Versión vigente de los documentos legales (Términos y Privacidad).

El **texto** de cada documento vive en su template (`templates/legal/`), que es
donde se edita. Acá solo queda lo que el código necesita comparar: la versión y
la fecha de la última actualización. La aceptación que da el estudiante se
guarda contra estas versiones, así que **cambiar el texto de forma sustantiva
exige subir la versión aquí**: es lo que hace que se le vuelva a pedir.

Una corrección de forma (una tilde, un enlace roto) no necesita versión nueva;
un cambio en qué datos se tratan, para qué o con quién, sí.
"""

from dataclasses import dataclass
from datetime import date

MESES = (
    "enero", "febrero", "marzo", "abril", "mayo", "junio", "julio",
    "agosto", "septiembre", "octubre", "noviembre", "diciembre",
)  # fmt: skip


@dataclass(frozen=True, slots=True)
class Documento:
    clave: str
    titulo: str
    ruta: str
    template: str
    version: str
    actualizado: date

    @property
    def actualizado_texto(self) -> str:
        """`2 de octubre de 2026`: la fecha como se lee en Chile."""
        d = self.actualizado
        return f"{d.day} de {MESES[d.month - 1]} de {d.year}"


TERMINOS = Documento(
    clave="terminos",
    titulo="Términos y Condiciones",
    ruta="/terminos",
    template="legal/terminos.html",
    version="0.1",
    actualizado=date(2026, 10, 2),
)

PRIVACIDAD = Documento(
    clave="privacidad",
    titulo="Política de Privacidad",
    ruta="/privacidad",
    template="legal/privacidad.html",
    version="0.1",
    actualizado=date(2026, 10, 2),
)

DOCUMENTOS = (TERMINOS, PRIVACIDAD)
