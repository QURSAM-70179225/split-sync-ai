from ledger import scale_to_total, split_equal


def test_split_equal_sums_exactly():
    parts = split_equal(100, 3)
    assert parts == [33.34, 33.33, 33.33]
    assert round(sum(parts), 2) == 100


def test_split_equal_single():
    assert split_equal(12.5, 1) == [12.5]


def test_scale_to_total_distributes_tax():
    out = scale_to_total([20, 10], 33)
    assert round(sum(out), 2) == 33
    assert out[0] == 22 and out[1] == 11


def test_placeholder_keys_are_ignored():
    from config import Settings

    s = Settings(_env_file=None, gemini_api_key="your-gemini-api-key", paypal_client_id="your-sandbox-client-id",
                 paypal_client_secret="x")
    assert s.gemini_api_key == "" and not s.ai_enabled
    assert s.effective_paypal_mode == "demo"


def test_gemini_client_is_reused():
    """google-genai >= 3 closes a garbage-collected Client; the client must be cached."""
    import ai_parser

    assert hasattr(ai_parser._client, "cache_info")


def test_fallback_is_reported(monkeypatch):
    """If Gemini errors, the response must say the offline parser was used (not 'gemini')."""
    import ai_parser
    from config import get_settings

    monkeypatch.setattr(get_settings(), "gemini_api_key", "AIza-test")
    monkeypatch.setattr(get_settings(), "ai_offline_mode", False)

    def boom(*a, **k):
        raise RuntimeError("Cannot send a request, as the client has been closed.")

    monkeypatch.setattr(ai_parser, "_generate", boom)
    parsed = ai_parser.parse_expense_prompt("I paid $10 for tea with Alex", ["You", "Alex"], "You")
    assert parsed._source == "offline" and "client has been closed" in parsed._fallback_reason
