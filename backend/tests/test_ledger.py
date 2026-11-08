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
