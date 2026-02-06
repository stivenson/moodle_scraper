"""Configuración desde variables de ambiente (.env)."""
from pathlib import Path
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class PortalSettings(BaseSettings):
    """Configuración del portal desde variables de ambiente."""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    profile: str = Field(default="moodle_default", alias="PORTAL_PROFILE")
    base_url: str = Field(default="", alias="PORTAL_BASE_URL")
    login_path: str = Field(default="/login/", alias="PORTAL_LOGIN_PATH")
    username: str = Field(default="", alias="PORTAL_USERNAME")
    password: str = Field(default="", alias="PORTAL_PASSWORD")

    @property
    def full_login_url(self) -> str:
        return f"{self.base_url.rstrip('/')}{self.login_path}"


class ScraperSettings(BaseSettings):
    """Configuración del scraper."""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    days_ahead: int = Field(default=7, alias="SCRAPER_DAYS_AHEAD")
    days_behind: int = Field(default=7, alias="SCRAPER_DAYS_BEHIND")
    max_courses: int = Field(default=0, alias="SCRAPER_MAX_COURSES")
    debug_mode: bool = Field(default=False, alias="SCRAPER_DEBUG_MODE")
    save_html_debug: bool = Field(default=False, alias="SCRAPER_SAVE_HTML_DEBUG")


class OutputSettings(BaseSettings):
    """Configuración de salida."""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    dir: Path = Field(default=Path("./reports"), alias="OUTPUT_DIR")
    format: Literal["markdown", "json", "pdf"] = Field(
        default="markdown",
        alias="OUTPUT_FORMAT",
    )


