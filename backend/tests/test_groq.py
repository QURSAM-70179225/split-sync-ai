"""Groq provider: model discovery, retired-model rollover, JSON parsing, provider selection. No network."""
import json

import pytest

import ai_parser
import groq_client
from config import Settings, get_settings

GOOD = {"total_amount": 100, "currency": "USD", "description": "Concert Tickets", "payer_name": "You",
        "split_type": "custom", "participants": ["You", "Alex"],
        "custom_shares": [{"name": "Alex", "amount": 60}, {"name": "You", "amount": 40}], "category": "entertainment"}


class FakeResp:
    def __init__(self, status, body):
        self.status_code = status
        self._body = body
        self.text = json.dumps(body)

    def json(self):
        return self._body

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(self.status_code)


@pytest.fixture
def groq(monkeypatch):
    s = get_settings()
    monkeypatch.setattr(s, "groq_api_key", "gsk_test")
    monkeypatch.setattr(s, "ai_offline_mode", False)
    monkeypatch.setattr(s, "groq_model", "")
    monkeypatch.setattr(groq_client, "_working", {"text": None, "vision": None})
    monkeypatch.setattr(groq_client, "_models_cache", {"at": 0.0, "ids": None})
    calls = []
    state = {"models": ["whisper-large-v3", "llama-3.3-70b-versatile", "meta-llama/llama-4-scout-17b-16e-instruct"],
             "reply": json.dumps(GOOD), "gone": set()}

    def fake_get(url, headers, timeout):
        return FakeResp(200, {"data": [{"id": m, "active": True} for m in state["models"]]})

    def fake_post(url, json, headers, timeout):
        calls.append(json)
        assert timeout[1] == get_settings().ai_timeout_s
        if json["model"] in state["gone"]:
            return FakeResp(400, {"error": {"message": "decommissioned", "code": "model_decommissioned"}})
        return FakeResp(200, {"choices": [{"message": {"content": state["reply"]}}]})

    monkeypatch.setattr(groq_client.requests, "get", fake_get)
    monkeypatch.setattr(groq_client.requests, "post", fake_post)
    return calls, state


def test_provider_selection():
    def mk(**kw):
        kw.setdefault("ai_offline_mode", False)
        return Settings(_env_file=None, **kw).active_ai_provider

    assert mk(groq_api_key="gsk_x", gemini_api_key="AIza-x") == "groq"
    assert mk(gemini_api_key="AIza-x") == "gemini"
    assert mk(groq_api_key="gsk_x", ai_provider="gemini") == ""
    assert mk(groq_api_key="gsk_x", ai_offline_mode=True) == ""
    assert mk(groq_api_key="your-groq-key") == ""


def test_groq_custom_split(groq):
    calls, _ = groq
    p = ai_parser.parse_expense_prompt("I paid $100 for concert tickets: Alex owes 60, I owe 40", ["You", "Alex"], "You")
    assert p.split_type == "custom" and p._source == "groq:llama-3.3-70b-versatile"
    assert calls[0]["response_format"] == {"type": "json_object"}
    assert "JSON Schema" in calls[0]["messages"][0]["content"]


def test_groq_skips_retired_model(groq):
    calls, state = groq
    state["gone"] = {"llama-3.3-70b-versatile"}
    state["models"].append("openai/gpt-oss-120b")
    ai_parser.parse_expense_prompt("I paid $100 for tickets: Alex owes 60, I owe 40", ["You", "Alex"], "You")
    assert [c["model"] for c in calls] == ["llama-3.3-70b-versatile", "openai/gpt-oss-120b"]
    assert groq_client.current_model() == "openai/gpt-oss-120b"


def test_groq_receipt_uses_vision_model(groq):
    calls, state = groq
    state["reply"] = json.dumps({**GOOD, "merchant": "Cafe", "items": [{"name": "Burger", "price": 60,
                                 "assigned_to": ["Alex"]}], "tax_and_tip": 0})
    r = ai_parser.parse_receipt(b"\x89PNG", "image/png", ["You", "Alex"], "You", "Alex had the burger")
    assert calls[0]["model"].startswith("meta-llama/llama-4")
    img = calls[0]["messages"][1]["content"][1]["image_url"]["url"]
    assert img.startswith("data:image/png;base64,") and r.items[0].assigned_to == ["Alex"]


def test_groq_bad_json_falls_back_offline(groq):
    _, state = groq
    state["reply"] = "sorry, I can't"
    p = ai_parser.parse_expense_prompt("I paid $10 for tea with Alex", ["You", "Alex"], "You")
    assert p._source == "offline" and p._fallback_reason


def test_groq_key_is_scrubbed():
    assert "gsk_abcdefghijklmnop" not in ai_parser._scrub("bad key gsk_abcdefghijklmnop1234 rejected")


RECEIPT = {**GOOD, "merchant": "Cafe", "items": [{"name": "Burger", "price": 60, "assigned_to": ["Alex"]}],
           "tax_and_tip": 0}


def test_receipt_falls_back_to_gemini_when_groq_has_no_vision(groq, monkeypatch):
    calls, state = groq
    state["models"] = ["openai/gpt-oss-120b", "whisper-large-v3"]  # no vision model on this key
    monkeypatch.setattr(get_settings(), "gemini_api_key", "AIza-test")
    seen = {}

    def fake_gemini(contents, system, schema, temperature=0.0):
        seen["contents"] = contents
        return ai_parser.ParsedReceipt.model_validate(RECEIPT)

    monkeypatch.setattr(ai_parser, "_generate_structured", fake_gemini)
    r = ai_parser.parse_receipt(b"\x89PNG", "image/png", ["You", "Alex"], "You", "Alex had the burger")
    assert r._source.startswith("gemini:") and calls == [] and len(seen["contents"]) == 2


def test_receipt_without_any_vision_model_is_a_clear_422(groq, monkeypatch):
    _, state = groq
    state["models"] = ["openai/gpt-oss-120b"]
    monkeypatch.setattr(get_settings(), "gemini_api_key", "")
    with pytest.raises(ai_parser.ExpenseParseError, match="GEMINI_API_KEY"):
        ai_parser.parse_receipt(b"\x89PNG", "image/png", ["You", "Alex"], "You", "")


def test_gemini_overload_rolls_to_next_model(monkeypatch):
    s = get_settings()
    monkeypatch.setattr(s, "groq_api_key", "")
    monkeypatch.setattr(s, "gemini_api_key", "AIza-test")
    monkeypatch.setattr(s, "ai_offline_mode", False)
    monkeypatch.setattr(s, "gemini_model", "gemini-3.8-flash")
    monkeypatch.setattr(ai_parser, "_working_model", None)
    tried = []

    class Models:
        def generate_content(self, model, contents, config):
            tried.append(model)
            if model == "gemini-3.8-flash":
                raise RuntimeError("503 UNAVAILABLE. This model is currently experiencing high demand.")
            return "ok"

    class Client:
        models = Models()

    monkeypatch.setattr(ai_parser, "_client", lambda: Client())
    assert ai_parser._generate("hi", "sys") == "ok"
    assert tried == ["gemini-3.8-flash", "gemini-3.5-flash"]


def test_qwen_multimodal_counts_as_vision(groq):
    calls, state = groq
    state["models"] = ["openai/gpt-oss-120b", "qwen/qwen3.8-27b"]
    state["reply"] = json.dumps(RECEIPT)
    r = ai_parser.parse_receipt(b"\x89PNG", "image/png", ["You", "Alex"], "You", "Alex had the burger")
    assert calls[0]["model"] == "qwen/qwen3.8-27b" and r._source == "groq:qwen/qwen3.8-27b"


def test_label_shows_a_model_the_key_can_use(groq):
    _, state = groq
    state["models"] = ["openai/gpt-oss-120b", "qwen/qwen3.8-27b"]
    assert groq_client.current_model() == "openai/gpt-oss-120b"
    assert groq_client.current_model(vision=True) == "qwen/qwen3.8-27b"
