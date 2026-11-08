"""Central configuration loaded from environment variables / .env."""
from functools import lru_cache
from typing import Literal

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # --- AI ---
    gemini_api_key: str = ""
    gemini_model: str = "gemini-2.5-flash"
    ai_offline_mode: bool = False

    # --- PayPal ---
    paypal_client_id: str = ""
    paypal_client_secret: str = ""
    paypal_base_url: str = "https://api-m.sandbox.paypal.com"
    paypal_use_payee_email: bool = False
    # auto  -> real sandbox when credentials exist, otherwise simulated demo checkout
    # sandbox -> always PayPal (errors if credentials missing)
    # demo  -> always simulated checkout (never calls PayPal)
    paypal_mode: Literal["auto", "sandbox", "demo"] = "auto"

    # --- App ---
    frontend_url: str = "http://localhost:5173"
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"
    database_url: str = "sqlite:///./splitsync.db"
    max_receipt_mb: int = 8
    log_level: str = "INFO"

    @field_validator("gemini_api_key", "paypal_client_id", "paypal_client_secret", mode="before")
    @classmethod
    def _ignore_placeholders(cls, v):
        """Treat template values like 'your-gemini-api-key' as unset, so a fresh .env just works."""
        v = (v or "").strip()
        return "" if v.lower().startswith(("your-", "your_", "<", "changeme")) else v

    @property
    def ai_enabled(self) -> bool:
        return bool(self.gemini_api_key) and not self.ai_offline_mode

    @property
    def effective_paypal_mode(self) -> str:
        if self.paypal_mode == "auto":
            return "sandbox" if (self.paypal_client_id and self.paypal_client_secret) else "demo"
        return self.paypal_mode


@lru_cache
def get_settings() -> Settings:
    return Settings()
