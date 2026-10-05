"""Configuración central leída desde variables de entorno / archivo .env."""

from functools import lru_cache
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_env: str = "dev"

    database_url: str = "postgresql+psycopg://studify:studify@localhost:5432/studify"

    # Clave con la que se firma la cookie de sesión de la UI (Fase 4). Si queda
    # vacía, `web/sesion.py` genera una efímera al arrancar: la app funciona
    # igual, pero las sesiones no sobreviven a un reinicio (ni a cada recarga de
    # `uvicorn --reload`). Fijarla en el `.env` es lo que hace cómoda la demo.
    session_secret: str = ""

    # Usuario y clave del panel del docente (`/teacher/*`). No hay tabla de
    # usuarios: el cap. 9 identifica al estudiante por su diagnóstico y no por
    # una credencial, y el docente es un rol operativo del piloto —una o dos
    # personas—, no una cuenta que haya que administrar. Una credencial
    # compartida separa las dos vistas sin construir un sistema de usuarios que
    # el informe no pide ni evalúa. No se valida contra la base de datos: el
    # panel tiene que poder abrirse aunque Postgres esté caído, que es
    # justamente cuando más falta hace poder entrar a revisar algo.
    #
    # ⚠️ **`admin` / `admin123` son credenciales de demo, no un secreto.**
    # Quedan como valor por defecto para que el panel funcione nada más clonar
    # el repo, sin depender de un `.env` a medio completar. Cambiarlas antes de
    # exponer el sistema a la cohorte (fijando `TEACHER_USERNAME` y
    # `TEACHER_PASSWORD` en el `.env`) es responsabilidad de quien lo despliegue
    # — acá no se puede distinguir "sigue en admin123 porque nadie lo cambió" de
    # "developer lo dejó así a propósito para la demo local".
    #
    # **Si `TEACHER_PASSWORD` se deja vacía explícitamente, el panel se cierra
    # por completo** (no cae de vuelta al valor por defecto). Es la puerta de la
    # barrera de curación del cap. 12/13: para desactivarla del todo hay que
    # hacerlo a propósito. Ver `web/routers/auth.py`.
    teacher_username: str = "admin"
    teacher_password: str = "admin123"

    # Proveedor LLM con API compatible con OpenAI (DeepSeek / Qwen / GLM).
    # El modelo se decide con datos en el bake-off de la Fase 3.
    llm_base_url: str = "https://api.deepseek.com/v1"
    llm_model: str = "deepseek-chat"
    llm_api_key: str = ""
    llm_temperature: float = 0.4
    llm_timeout: int = 90
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
