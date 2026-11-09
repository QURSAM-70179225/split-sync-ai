"""Central configuration loaded from environment variables / .env."""
from functools import lru_cache
from typing import Literal

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # --- AI ---
    # auto -> Groq if GROQ_API_KEY is set, else Gemini if GEMINI_API_KEY is set, else offline
    ai_provider: Literal["auto", "groq", "gemini"] = "auto"
    groq_api_key: str = ""
    groq_model: str = ""          # empty = auto-pick from the models your key can use
    groq_vision_model: str = ""   # used for receipt photos; empty = auto-pick
    gemini_api_key: str = ""
    gemini_model: str = "gemini-3.8-flash"
    ai_offline_mode: bool = False
    ai_timeout_s: int = 25        # hard limit per AI request

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
    # Serve the built React app from this folder (single-URL deployments). Empty = API only.
    static_dir: str = ""
    # Seed the "Bali Trip" demo group when the database is empty (hosted demos for judges).
    seed_demo_on_start: bool = False
    # Set automatically by Render; used as the public URL when FRONTEND_URL is left at its default.
    render_external_url: str = ""

    @field_validator("groq_api_key", "gemini_api_key", "paypal_client_id", "paypal_client_secret", mode="before")
    @classmethod
    def _ignore_placeholders(cls, v):
        """Treat template values like 'your-gemini-api-key' as unset, so a fresh .env just works."""
        v = (v or "").strip()
        return "" if v.lower().startswith(("your-", "your_", "<", "changeme")) else v

    @property
    def active_ai_provider(self) -> str:
        """'groq', 'gemini' or '' (offline)."""
        if self.ai_offline_mode:
            return ""
        if self.ai_provider == "groq":
            return "groq" if self.groq_api_key else ""
        if self.ai_provider == "gemini":
            return "gemini" if self.gemini_api_key else ""
        return "groq" if self.groq_api_key else "gemini" if self.gemini_api_key else ""

    @property
    def ai_enabled(self) -> bool:
        return bool(self.active_ai_provider)

    @property
    def public_url(self) -> str:
        """Base URL PayPal redirects back to after checkout."""
        if self.render_external_url and "localhost" in self.frontend_url:
            return self.render_external_url.rstrip("/")
        return self.frontend_url.rstrip("/")

    @property
    def effective_paypal_mode(self) -> str:
        if self.paypal_mode == "auto":
            return "sandbox" if (self.paypal_client_id and self.paypal_client_secret) else "demo"
        return self.paypal_mode


@lru_cache
def get_settings() -> Settings:
    return Settings()
