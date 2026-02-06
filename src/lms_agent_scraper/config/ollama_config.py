"""Configuración de Ollama / GLM-4.7-Flash."""
from pydantic_settings import BaseSettings, SettingsConfigDict


class OllamaSettings(BaseSettings):
    """Configuración del modelo local Ollama."""

    model_config = SettingsConfigDict(env_prefix="OLLAMA_", env_file=".env", extra="ignore")

    model_name: str = "glm-4.7-flash:q4_K_M"
    base_url: str = "http://localhost:11434"
    temperature: float = 0.1
    num_ctx: int = 8192
    num_predict: int = 2048
    request_timeout: int = 120
    fallback_to_cloud: bool = False
    cloud_provider: str = "anthropic"
