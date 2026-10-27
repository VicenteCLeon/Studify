"""Configuración central leída desde variables de entorno / archivo .env."""

import logging
from functools import lru_cache
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

logger = logging.getLogger(__name__)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # `dev` es el único modo desarrollo y tiene que pedirse explícitamente: sin
    # `APP_ENV` la app se trata como producción y `verificar_configuracion` exige
    # un `SESSION_SECRET` fuerte (O1, 27-oct-2026).
    app_env: str = "prod"

    database_url: str = "postgresql+psycopg://studify:studify@localhost:5432/studify"

    # Clave con la que se firma la cookie de sesión de la UI (Fase 4). Fuera de
    # `APP_ENV=dev` es obligatoria (32 caracteres o más). En desarrollo, si
    # queda vacía, `web/sesion.py` genera una efímera al arrancar: la app
    # funciona igual, pero las sesiones no sobreviven a un reinicio.
    session_secret: str = ""

    # Cuántas horas vale la sesión del estudiante desde que responde el
    # cuestionario. 720 (30 días) para quien estudia en su propio equipo; en un
    # computador compartido conviene bajarla (1–4) para que la sesión de uno no
    # le quede abierta al siguiente. El vencimiento va dentro de la firma (ver
    # `web/sesion.py`), así que no se puede extender desde el navegador.
    sesion_estudiante_horas: int = Field(default=720, ge=1)

    # Usuario y clave del panel del docente (`/teacher/*`). No hay tabla de
    # usuarios: el cap. 9 identifica al estudiante por su diagnóstico y no por
    # una credencial, y el docente es un rol operativo del piloto —una o dos
    # personas—, no una cuenta que haya que administrar. Una credencial
    # compartida separa las dos vistas sin construir un sistema de usuarios que
    # el informe no pide ni evalúa. No se valida contra la base de datos: el
    # panel tiene que poder abrirse aunque Postgres esté caído, que es
    # justamente cuando más falta hace poder entrar a revisar algo.
    #
    # **La clave no tiene valor por defecto** (O1, 27-oct-2026; antes era
    # `admin123`, un secreto tan público como no tener clave). Sin
    # `TEACHER_PASSWORD` el panel queda cerrado para todos —fallar cerrado— y
    # la pantalla de login dice qué variable fijar. Fuera de `APP_ENV=dev`,
    # una clave débil impide arrancar (`verificar_configuracion`). Es la
    # puerta de la barrera de curación del cap. 12/13. Ver `web/routers/auth.py`.
    teacher_username: str = "admin"
    teacher_password: str = ""

    # Proveedor LLM con API compatible con OpenAI (DeepSeek / Qwen / GLM).
    # El modelo se decide con datos en el bake-off de la Fase 3.
    llm_base_url: str = "https://api.deepseek.com/v1"
    llm_model: str = "deepseek-flash"
    # Modo de razonamiento del modelo. `deepseek-flash` razona por defecto y esos
    # tokens se descuentan de `llm_max_tokens`: con 2.000 no queda espacio para
    # la cápsula y la respuesta llega truncada (medido el 10-oct-2026, ver
    # docs/modulo-visual/analisis-modulo-visual.md §10.1). `disabled` lo apaga
    # y `enabled` lo fuerza. Vacío no envía el parámetro: es lo que corresponde
    # con un proveedor que no lo conozca.
    llm_thinking: Literal["", "enabled", "disabled"] = "disabled"
    llm_api_key: str = ""
    llm_temperature: float = 0.4
    llm_timeout: int = 90
    # Reintentos de red por llamada al modelo (timeout, conexión caída, 429,
    # 5xx), distintos de los de reparación de abajo. Sin fijarlo, llama-index
    # usa 3 y los aplica dos veces: en el SDK de OpenAI y otra vez por fuera
    # con tenacity, así que un proveedor caído podía tener al estudiante varios
    # minutos en «Generando…». Con 1, una llamada se intenta como máximo dos
    # veces: con `llm_timeout = 90`, unos 3 minutos en el peor caso.
    llm_max_retries: int = 1
    llm_max_repair_attempts: int = 2
    # Una cápsula de 300 palabras más la estructura JSON ronda los 1.200 tokens.
    # El margen cubre los perfiles largos sin dejar que una respuesta desbocada
    # se corte a la mitad: el validador detecta el truncamiento, pero cuesta una
    # llamada completa.
    llm_max_tokens: int = 2000
    # `response_format={"type": "json_object"}`. DeepSeek lo soporta; se deja
    # como variable porque el bake-off de la Fase 3 compara tres proveedores y
    # no todos lo implementan igual.
    llm_json_mode: bool = True

    # Restricciones estructurales de la microcápsula (cap. 11.1 del informe).
    capsula_min_palabras: int = 150
    capsula_max_palabras: int = 300
    capsula_max_palabras_titulo: int = 10

    # Dónde se guardan los documentos oficiales ingeridos (Fase 2). Se copian
    # al almacén en vez de referenciar la ruta original para que `ruta_archivo`
    documentos_dir: str = "data/documentos"

    # Dónde se guardan los recursos multimedia generados (Fase 6).
    media_dir: str = "data/media"

    # --- Narración del visor (perfil auditivo) --------------------------------
    #
    # Motor con que se sintetiza el audio. `kokoro` es el de la interfaz del
    # estudiante: la voz sale de su preferencia {género, modo} (ver
    # `media/audio.py::resolver_voz`). `xtts` es una opción administrativa
    # explícita: fuerza XTTS-v2 para todos, sin respaldo automático, y necesita
    # el extra `audio-xtts`. Mediciones y decisión en PRUEBAS_VARK.md (Etapa 2).
    tts_motor: Literal["kokoro", "xtts"] = "kokoro"
    # Modelos ONNX y voces descargados por `scripts/descargar_voces.py`. Están
    # bajo `data/`, ignorado por git: pesan cientos de MB y no se versionan.
    tts_modelos_dir: str = "data/voces"
    # Voces del modo «calidad» (Kokoro). Género según VOICES.md de
    # hexgrad/Kokoro-82M: ef_dora 🚺, em_alex 🚹.
    tts_voz_calidad_femenina: str = "ef_dora"
    tts_voz_calidad_masculina: str = "em_alex"
    # Variante de espeak-ng con que Kokoro fonemiza. Kokoro documenta `es`, que
    # pronuncia con distinción (z/ce/ci como θ, a la española); se usa `es-419`,
    # la latinoamericana con seseo, porque los estudiantes del piloto son
    # chilenos (decisión del autor tras escuchar ambas, 05-oct-2026).
    tts_kokoro_idioma: str = "es-419"
    # Voz del modo «rápida» (Piper): un solo modelo con dos hablantes, así que
    # una sola licencia (CC BY 3.0, exige atribución). Los ids salen de
    # `speaker_id_map` del `.onnx.json` ({"M": 0, "F": 1}) y se fijan acá en vez
    # de depender del hablante por defecto de Piper.
    tts_voz_rapida_modelo: str = "es_ES-sharvard-medium"
    tts_hablante_rapida_femenina: int = 1
    tts_hablante_rapida_masculina: int = 0


@lru_cache
def get_settings() -> Settings:
    return Settings()


# --- Verificación al arrancar (O1) --------------------------------------------

MIN_LARGO_SECRETO = 32
MIN_LARGO_CLAVE_DOCENTE = 12

# Valores que circulan en ejemplos y tutoriales. Los cortos ya caen por largo;
# esta lista atrapa los placeholders largos que alguien copia tal cual.
SECRETOS_DE_EJEMPLO = {
    "changeme",
    "change-me",
    "secret",
    "your-secret-key",
    "your-secret-key-here",
    "replace-me-with-a-random-secret",
    "cambia-este-secreto",
    "cambiar-por-un-secreto-aleatorio",
}
CLAVES_DEBILES = {"admin", "admin123", "password", "contraseña", "studify", "docente", "123456"}


class ConfiguracionInsegura(RuntimeError):
    """La configuración no sirve fuera de desarrollo. El mensaje nunca incluye los valores."""


def es_desarrollo(settings: Settings) -> bool:
    return settings.app_env == "dev"


def problemas_de_seguridad(settings: Settings) -> list[str]:
    """Qué impide arrancar en producción. Describe cada problema sin citar el valor."""
    problemas = []

    secreto = settings.session_secret.strip()
    if not secreto:
        problemas.append("SESSION_SECRET no está fijada")
    elif secreto.lower() in SECRETOS_DE_EJEMPLO:
        problemas.append("SESSION_SECRET es un valor de ejemplo conocido")
    elif len(secreto) < MIN_LARGO_SECRETO:
        problemas.append(f"SESSION_SECRET tiene menos de {MIN_LARGO_SECRETO} caracteres")

    # Sin clave el panel queda cerrado: es seguro, así que no impide arrancar.
    clave = settings.teacher_password
    if clave and (clave.lower() in CLAVES_DEBILES or len(clave) < MIN_LARGO_CLAVE_DOCENTE):
        problemas.append(
            "TEACHER_PASSWORD es débil (valor conocido o menos de "
            f"{MIN_LARGO_CLAVE_DOCENTE} caracteres)"
        )
    return problemas


def verificar_configuracion(settings: Settings) -> None:
    """Se niega a arrancar fuera de `APP_ENV=dev` con secretos débiles.

    En desarrollo solo avisa: el secreto efímero de `web/sesion.py` y una clave
    de demo son aceptables en la máquina del autor.
    """
    problemas = problemas_de_seguridad(settings)
    if not problemas:
        return
    if es_desarrollo(settings):
        for problema in problemas:
            logger.warning("APP_ENV=dev: %s. Aceptable solo en desarrollo.", problema)
        if not settings.session_secret:
            logger.warning(
                "APP_ENV=dev: se usa un SESSION_SECRET efímero; las sesiones se "
                "pierden en cada reinicio."
            )
        return
    raise ConfiguracionInsegura(
        "Studify no arranca con esta configuración (APP_ENV="
        f"{settings.app_env!r}): " + "; ".join(problemas) + ". "
        'Genera un secreto con: python -c "import secrets; print(secrets.token_urlsafe(48))" '
        "o usa APP_ENV=dev para desarrollo local."
    )
