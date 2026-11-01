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
    # 0.2: motores de voz, componentes de terceros y licencias, licencia del
    # código y declaración de prototipo académico. Fecha = día en que se publique.
    # 0.3: acceso opcional con Google y recuperación del perfil vinculado.
    # 0.4: Google obligatorio antes de guardar el perfil VARK en la web.
    version="0.4",
    actualizado=date(2026, 11, 1),
)

PRIVACIDAD = Documento(
    clave="privacidad",
    titulo="Política de Privacidad",
    ruta="/privacidad",
    template="legal/privacidad.html",
    # 0.2: motores de voz (Kokoro y Piper en vez de XTTS-v2) y preferencia de
    # voz (`voz_genero`, `voz_modo`) como dato nuevo.
    # 0.3: «Salir» y la sesión compartida (R2): `origen_registro` como dato
    # nuevo, la cookie del mismo nombre y el vencimiento de la sesión.
    # Fecha = día en que se publique.
    # 0.4: rol del piloto y perfil general fijo para el grupo control.
    # 0.5: identidad Google y cookies/transacciones temporales de autenticación.
    # 0.6: continuidad del borrador al autenticar y Google para guardar VARK.
    version="0.6",
    actualizado=date(2026, 11, 1),
)

DOCUMENTOS = (TERMINOS, PRIVACIDAD)
