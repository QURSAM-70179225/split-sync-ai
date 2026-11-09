"""Settle-Up Agent: intent → deterministic plan → guarded execution (offline AI, demo PayPal)."""
import pytest
from conftest import say

from agent import _offline_intent


@pytest.fixture
def owing(client, trio):
    """Net result: You owe Alex $5 and Sarah $15."""
    gid, ids = trio
    say(client, gid, "Alex paid $50 for pizza split with me", ids["You"])       # You owe Alex 25
    say(client, gid, "Sarah paid $30 for taxi split with me", ids["You"])       # You owe Sarah 15
    say(client, gid, "I paid $40 for drinks split with Alex", ids["You"])       # Alex owes You 20 → nets to You owe Alex 5
    return gid, ids


@pytest.mark.parametrize("text,intent,people", [
    ("Settle everything for me", "settle_all", []),
    ("Pay back Sarah", "pay_specific", ["Sarah"]),
    ("pay all my debts", "pay_my_debts", []),
    ("Remind everyone who owes me", "collect", []),
    ("what's the weather", "unknown", []),
])
def test_offline_intent(text, intent, people):
    got = _offline_intent(text, ["You", "Alex", "Sarah"], "You")
    assert got.intent == intent and got.people == people


def plan(client, gid, sender, text):
    r = client.post(f"/api/groups/{gid}/agent/plan", json={"text": text, "sender_id": sender})
    assert r.status_code == 200, r.text
    return r.json()


def test_plan_pays_only_my_debts_with_ledger_amounts(client, owing):
    gid, ids = owing
    p = plan(client, gid, ids["You"], "Settle everything for me")
    pays = {(a["to_user"]["name"], a["amount"]) for a in p["actions"] if a["kind"] == "pay"}
    assert pays == {("Alex", 5.0), ("Sarah", 15.0)}
    assert all(a["from_user"]["name"] == "You" for a in p["actions"] if a["kind"] == "pay")
    assert "Nothing happens until you confirm" in p["summary"]


def test_plan_specific_person(client, owing):
    gid, ids = owing
    p = plan(client, gid, ids["You"], "Pay back Sarah")
    assert [(a["kind"], a["to_user"]["name"]) for a in p["actions"]] == [("pay", "Sarah")]


def test_plan_collect_for_creditor(client, owing):
    gid, ids = owing
    p = plan(client, gid, ids["Sarah"], "Remind everyone who owes me")
    assert [(a["kind"], a["from_user"]["name"], a["amount"]) for a in p["actions"]] == [("nudge", "You", 15.0)]


def test_execute_creates_orders_and_nudges(client, owing):
    gid, ids = owing
    p = plan(client, gid, ids["You"], "Settle everything for me")
    actions = [{"kind": a["kind"], "from_user_id": a["from_user"]["id"], "to_user_id": a["to_user"]["id"],
                "amount": a["amount"], "currency": a["currency"]} for a in p["actions"]]
    r = client.post(f"/api/groups/{gid}/agent/execute", json={"sender_id": ids["You"], "actions": actions})
    assert r.status_code == 200, r.text
    out = r.json()
    assert out["mode"] == "demo" and len(out["payments"]) == 2
    for pay in out["payments"]:
        st = pay["settlement"]
        assert st["status"] == "created" and st["paypal_order_id"].startswith("DEMO-")
        assert client.post(f"/api/settlements/{st['id']}/capture", json={"order_id": st["paypal_order_id"]}).json()["status"] == "completed"
    assert plan(client, gid, ids["You"], "pay all my debts")["actions"] == []


def test_execute_refuses_paying_someone_elses_debt(client, owing):
    gid, ids = owing
    r = client.post(f"/api/groups/{gid}/agent/execute", json={"sender_id": ids["Alex"], "actions": [
        {"kind": "pay", "from_user_id": ids["You"], "to_user_id": ids["Sarah"], "amount": 15, "currency": "USD"}]})
    assert r.status_code == 403


def test_execute_refuses_overpaying(client, owing):
    gid, ids = owing
    r = client.post(f"/api/groups/{gid}/agent/execute", json={"sender_id": ids["You"], "actions": [
        {"kind": "pay", "from_user_id": ids["You"], "to_user_id": ids["Sarah"], "amount": 999, "currency": "USD"}]})
    assert r.status_code == 422 and "exceeds" in r.json()["detail"]


def test_execute_refuses_nudging_for_someone_else(client, owing):
    gid, ids = owing
    r = client.post(f"/api/groups/{gid}/agent/execute", json={"sender_id": ids["You"], "actions": [
        {"kind": "nudge", "from_user_id": ids["You"], "to_user_id": ids["Sarah"], "amount": 15, "currency": "USD"}]})
    assert r.status_code == 403
