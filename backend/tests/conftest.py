import os
import sys
import tempfile
from pathlib import Path

import pytest

# Configure BEFORE the app modules are imported: offline AI, demo PayPal, throwaway DB.
_tmp = tempfile.mkdtemp()
os.environ.update(
    AI_OFFLINE_MODE="true",
    GEMINI_API_KEY="",
    PAYPAL_MODE="demo",
    PAYPAL_CLIENT_ID="",
    PAYPAL_CLIENT_SECRET="",
    DATABASE_URL=f"sqlite:///{Path(_tmp) / 'test.db'}",
)
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fastapi.testclient import TestClient  # noqa: E402

import main  # noqa: E402


@pytest.fixture(scope="session")
def client():
    with TestClient(main.app) as c:
        yield c


@pytest.fixture
def trio(client):
    """A fresh group: You, Alex, Sarah."""
    g = client.post("/api/groups", json={"name": "Trip", "members": [{"name": "You"}, {"name": "Alex"}, {"name": "Sarah"}]}).json()
    ids = {m["name"]: m["id"] for m in g["members"]}
    return g["id"], ids


def say(client, gid, text, sender):
    r = client.post(f"/api/groups/{gid}/expenses/parse", json={"text": text, "sender_id": sender})
    assert r.status_code == 201, r.text
    return r.json()
