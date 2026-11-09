"""Minimal Groq client (OpenAI-compatible Chat Completions over HTTPS).

Model names on Groq change often, so models are discovered from GET /models and
retired ones are skipped automatically. Every request has a hard timeout.
"""
from __future__ import annotations

import logging
import time

import requests

from config import get_settings

log = logging.getLogger("splitsync.groq")

BASE_URL = "https://api.groq.com/openai/v1"
TEXT_PREFERENCES = (
    "llama-3.3-70b-versatile",
    "openai/gpt-oss-120b",
    "openai/gpt-oss-20b",
    "llama-3.1-8b-instant",
)
VISION_PREFERENCES = (
    "meta-llama/llama-4-scout-17b-16e-instruct",
    "meta-llama/llama-4-maverick-17b-128e-instruct",
)
_NOT_CHAT = ("whisper", "tts", "guard", "playai", "orpheus", "distil", "embed", "compound")
# Qwen 3.5+ models are natively multimodal (text + images).
_VISION_HINTS = ("vision", "llama-4", "scout", "maverick", "-vl", "qwen3.5", "qwen3.6", "qwen3.7", "qwen3.8", "qwen3.9")
_MODEL_GONE = ("model_not_found", "model_decommissioned", "model_not_active")

_working: dict[str, str | None] = {"text": None, "vision": None}
_models_cache: dict[str, object] = {"at": 0.0, "ids": None}


class GroqError(RuntimeError):
    def __init__(self, message: str, code: int | None = None, error_code: str = ""):
        super().__init__(message)
        self.code = code
        self.error_code = error_code


def _headers() -> dict[str, str]:
    return {"Authorization": f"Bearer {get_settings().groq_api_key}", "Content-Type": "application/json"}


def _timeout() -> tuple[int, int]:
    return (5, get_settings().ai_timeout_s)


def list_models() -> list[str] | None:
    """Active model ids for this key (cached 10 min). None if the list can't be fetched."""
    if _models_cache["ids"] is not None and time.time() - float(_models_cache["at"]) < 600:
        return _models_cache["ids"]  # type: ignore[return-value]
    try:
        resp = requests.get(f"{BASE_URL}/models", headers=_headers(), timeout=_timeout())
        resp.raise_for_status()
        ids = [m["id"] for m in resp.json().get("data", []) if m.get("active", True)]
    except Exception as exc:  # network / auth: fall back to the preference list
        log.warning("Could not list Groq models: %s", type(exc).__name__)
        return None
    _models_cache.update(at=time.time(), ids=ids)
    return ids


def _candidates(vision: bool) -> list[str]:
    s = get_settings()
    kind = "vision" if vision else "text"
    configured = s.groq_vision_model if vision else s.groq_model
    prefs = VISION_PREFERENCES if vision else TEXT_PREFERENCES
    available = list_models()
    out = [m for m in (_working[kind], configured) if m]
    if available is None:
        out += list(prefs)
    else:
        out += [m for m in prefs if m in available]
        if vision:
            out += [m for m in available if any(h in m for h in _VISION_HINTS)]
        else:
            out += [m for m in available if not any(n in m for n in _NOT_CHAT)]
    return list(dict.fromkeys(out))


def has_vision_model() -> bool:
    """True if this key can use at least one image-capable model."""
    available = list_models()
    if available is None:
        return True  # can't tell; let the request decide
    return any(m in available for m in _candidates(vision=True))


def current_model(vision: bool = False) -> str:
    kind = "vision" if vision else "text"
    if _working[kind]:
        return _working[kind]  # type: ignore[return-value]
    configured = get_settings().groq_vision_model if vision else get_settings().groq_model
    return configured or (VISION_PREFERENCES if vision else TEXT_PREFERENCES)[0]


def _post(model: str, messages: list, json_mode: bool, temperature: float) -> str:
    body: dict = {"model": model, "messages": messages, "temperature": temperature}
    if json_mode:
        body["response_format"] = {"type": "json_object"}
    resp = requests.post(f"{BASE_URL}/chat/completions", json=body, headers=_headers(), timeout=_timeout())
    if resp.status_code >= 400:
        try:
            err = resp.json().get("error", {})
        except ValueError:
            err = {}
        raise GroqError(f"Groq {resp.status_code}: {err.get('message', resp.text[:200])}",
                        code=resp.status_code, error_code=str(err.get("code", "")))
    return resp.json()["choices"][0]["message"]["content"] or ""


def chat(messages: list, *, vision: bool = False, json_mode: bool = False, temperature: float = 0.0) -> str:
    """Run a chat completion, skipping retired models and remembering the one that works."""
    kind = "vision" if vision else "text"
    last: Exception | None = None
    for model in _candidates(vision)[:6]:
        try:
            try:
                text = _post(model, messages, json_mode, temperature)
            except GroqError as exc:
                if json_mode and exc.error_code == "json_validate_failed":
                    text = _post(model, messages, False, temperature)  # we validate the JSON ourselves
                else:
                    raise
        except GroqError as exc:
            if exc.code == 404 or exc.error_code in _MODEL_GONE:
                log.warning("Groq model %s unavailable (%s), trying the next one", model, exc.error_code or exc.code)
                last = exc
                continue
            raise
        if _working[kind] != model:
            log.info("Using Groq %s model %s", kind, model)
            _working[kind] = model
        return text
    raise last or GroqError("No Groq model available for this key")
