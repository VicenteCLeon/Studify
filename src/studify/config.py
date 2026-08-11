"""Configuración central leída desde variables de entorno / archivo .env."""

from functools import lru_cache

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
    # siga siendo válida si el docente mueve o borra el archivo de su carpeta.
    documentos_dir: str = "data/documentos"


@lru_cache
def get_settings() -> Settings:
    return Settings()
