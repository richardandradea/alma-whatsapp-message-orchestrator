from __future__ import annotations

import os
from pathlib import Path
from typing import Optional, Annotated

from pydantic import Field, SecretStr, ValidationError
from pydantic import StringConstraints as SC
from pydantic_settings import BaseSettings, SettingsConfigDict

def _from_env_or_file_any(*vars_: str, required: bool = False) -> Optional[str]:
    """
    Devuelve el primer valor encontrado entre VAR o VAR_FILE (contenido del archivo).
    Si required=True y no encuentra ninguno, levanta RuntimeError.
    """
    for var in vars_:
        # 1) Directo desde env
        v = os.getenv(var)
        if v:
            return v

        # 2) Desde archivo VAR_FILE
        file_path = os.getenv(f"{var}_FILE")
        if file_path:
            p = Path(file_path)
            if not p.is_file():
                raise FileNotFoundError(f"{var}_FILE apunta a un archivo inexistente: {file_path}")
            return p.read_text(encoding="utf-8").strip()

    if required:
        names = " o ".join([f"{v}({v}_FILE)" for v in vars_])
        raise RuntimeError(f"Falta secreto requerido: define {names}")
    return None


# Validaciones declarativas (Pydantic v2)
EnvStr = Annotated[str, SC(pattern=r"^(dev|qa|prod)$")]
LogLevelStr = Annotated[str, SC(pattern=r"^(DEBUG|INFO|WARNING|ERROR|CRITICAL)$")]


class Settings(BaseSettings):
    # --- App ---
    app_name: str = Field("orchestrator-whatsapp-inbound", alias="APP_NAME")
    env: EnvStr = Field("dev", alias="ENV")
    log_level: LogLevelStr = Field("INFO", alias="LOG_LEVEL")
    port: int = Field(8080, alias="PORT")

    # --- Agente ---
    agent_app_name: str = Field("alma", alias="AGENT_APP_NAME")
    agent_url: str = Field("", alias="AGENT_URL")

    # --- WhatsApp API (opcional, para enviar respuestas) ---
    whatsapp_api_url: str = Field("", alias="WHATSAPP_API_URL")
    whatsapp_access_token: Optional[SecretStr] = Field(default=None, alias="WHATSAPP_ACCESS_TOKEN")

    # --- Integraciones / Secretos ---
    whatsapp_verify_token: SecretStr

    # --- Config de pydantic-settings ---
    model_config = SettingsConfigDict(
        env_file=".env",               # útil en local; opcional en contenedores
        env_file_encoding="utf-8",
        extra="ignore",
        validate_default=True,
    )

    @classmethod
    def load(cls) -> "Settings":
        """
        Construye Settings combinando envs normales y *_FILE.
        Acepta tanto OPENAI_API_KEY como OPEN_AI_API_KEY (compat).
        """
        overrides = {}

        whvtk = _from_env_or_file_any("WHATSAPP_VERIFY_TOKEN", required=True)
        overrides["whatsapp_verify_token"] = SecretStr(whvtk)  # type: ignore[arg-type]
        
        # WhatsApp API token (opcional)
        whatsapp_token = _from_env_or_file_any("WHATSAPP_ACCESS_TOKEN", required=False)
        if whatsapp_token:
            overrides["whatsapp_access_token"] = SecretStr(whatsapp_token)  # type: ignore[arg-type]

        try:
            return cls(**overrides)
        except ValidationError as e:
            raise RuntimeError(f"Configuración inválida: {e}") from e


# --- Singleton sencillo para evitar releer en cada import ---
_settings: Optional[Settings] = None

def get_settings() -> Settings:
    global _settings
    if _settings is None:
        _settings = Settings.load()
    return _settings