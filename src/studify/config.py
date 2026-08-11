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

    # Proveedor LLM con API compatible con OpenAI (DeepSeek / Qwen / GLM).
    # El modelo se decide con datos en el bake-off de la Fase 3.
    llm_base_url: str = "https://api.deepseek.com/v1"
    llm_model: str = "deepseek-chat"
    llm_api_key: str = ""
    llm_temperature: float = 0.4
    llm_timeout: int = 90
    llm_max_repair_attempts: int = 2

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
