from conftest import say


def test_health(client):
    body = client.get("/api/health").json()
    assert body["status"] == "ok"
    assert body["ai_mode"] == "offline"
    assert body["paypal_mode"] == "demo"


def test_group_validation(client):
    r = client.post("/api/groups", json={"name": "X", "members": [{"name": "A"}, {"name": "a"}]})
    assert r.status_code == 422


def test_parse_equal_split_and_category(client, trio):
    gid, ids = trio
    res = say(client, gid, "I paid $60 for dinner, split between me, Alex, and Sarah", ids["You"])
    e = res["expense"]
    assert e["amount"] == 60 and e["payer"]["name"] == "You"
    assert e["category"] == "food"
    assert sorted(s["owed_amount"] for s in e["splits"]) == [20, 20, 20]


def test_balances_simplify(client, trio):
    gid, ids = trio
    say(client, gid, "I paid $60 for dinner, split between me, Alex, and Sarah", ids["You"])
    say(client, gid, "Alex paid $30 for the Uber split with me", ids["You"])
    say(client, gid, "Sarah covered $45 for groceries split between everyone", ids["You"])
    bal = client.get(f"/api/groups/{gid}/balances").json()
    net = {m["user"]["name"]: m["net"] for m in bal["members"]}
    assert net == {"You": 10, "Alex": -20, "Sarah": 10}
    assert round(sum(net.values()), 2) == 0
    assert len(bal["debts"]) == 2
    assert bal["naive_transfer_count"] >= len(bal["debts"])


def test_unknown_member_auto_added(client, trio):
    gid, ids = trio
    res = say(client, gid, "I paid $40 for pizza with Priya", ids["You"])
    assert [m["name"] for m in res["new_members"]] == ["Priya"]


def test_bad_amount_is_422(client, trio):
    gid, ids = trio
    r = client.post(f"/api/groups/{gid}/expenses/parse", json={"text": "we had fun", "sender_id": ids["You"]})
    assert r.status_code == 422


def test_demo_settlement_flow(client, trio):
    gid, ids = trio
    say(client, gid, "I paid $50 for tickets split with Alex", ids["You"])
    r = client.post("/api/settlements/pay", json={"group_id": gid, "from_user_id": ids["Alex"], "to_user_id": ids["You"], "amount": 999})
    assert r.status_code == 422
    r = client.post("/api/settlements/pay", json={"group_id": gid, "from_user_id": ids["Alex"], "to_user_id": ids["You"], "amount": 25})
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["mode"] == "demo" and "paypal=demo" in body["approval_url"]
    sid, oid = body["settlement"]["id"], body["settlement"]["paypal_order_id"]
    assert client.post(f"/api/settlements/{sid}/capture", json={"order_id": "WRONG"}).status_code == 422
    st = client.post(f"/api/settlements/{sid}/capture", json={"order_id": oid}).json()
    assert st["status"] == "completed"
    # idempotent
    assert client.post(f"/api/settlements/{sid}/capture", json={"order_id": oid}).json()["status"] == "completed"
    assert client.get(f"/api/groups/{gid}/balances").json()["debts"] == []
    splits = client.get(f"/api/groups/{gid}/expenses").json()[0]["splits"]
    assert all(s["status"] == "paid" for s in splits)


def test_insights_ask_nudge_export(client, trio):
    gid, ids = trio
    say(client, gid, "I paid $60 for dinner, split between me, Alex, and Sarah", ids["You"])
    say(client, gid, "Alex paid $30 for the Uber split with me", ids["You"])
    ins = client.get(f"/api/groups/{gid}/insights").json()
    assert ins["total_spent"] == 90 and ins["expense_count"] == 2
    assert {c["category"] for c in ins["by_category"]} == {"food", "transport"}
    assert ins["highlights"]

    ans = client.post(f"/api/groups/{gid}/ask", json={"question": "How much did we spend on food?", "sender_id": ids["You"]}).json()
    assert "60.00" in ans["answer"]

    n = client.post(f"/api/groups/{gid}/nudge", json={"from_user_id": ids["Alex"], "to_user_id": ids["You"], "amount": 5, "tone": "funny"}).json()
    assert "Alex" in n["message"]

    csv = client.get(f"/api/groups/{gid}/export.csv")
    assert csv.status_code == 200 and csv.text.startswith("date,description")
    assert "Dinner" in csv.text


def test_receipt_requires_ai(client, trio):
    gid, ids = trio
    r = client.post(f"/api/groups/{gid}/expenses/receipt", files={"file": ("r.png", b"\x89PNG", "image/png")},
                    data={"sender_id": str(ids["You"])})
    assert r.status_code == 422 and "Gemini" in r.json()["detail"]
    r = client.post(f"/api/groups/{gid}/expenses/receipt", files={"file": ("r.txt", b"hi", "text/plain")})
    assert r.status_code == 415


def test_demo_seed(client):
    g = client.post("/api/demo/seed").json()
    assert len(g["members"]) == 4
    ins = client.get(f"/api/groups/{g['id']}/insights").json()
    assert ins["expense_count"] == 9 and ins["payments_saved"] >= 0


def test_delete_expense(client, trio):
    gid, ids = trio
    eid = say(client, gid, "I paid $10 for coffee with Alex", ids["You"])["expense"]["id"]
    assert client.delete(f"/api/expenses/{eid}").status_code == 204
    assert client.get(f"/api/groups/{gid}/expenses").json() == []


def test_offline_description_after_amount(client, trio):
    gid, ids = trio
    e = say(client, gid, "Alex covered the $24 Uber, split with me", ids["You"])["expense"]
    assert e["description"] == "Uber" and e["category"] == "transport" and e["payer"]["name"] == "Alex"
    e = say(client, gid, "I paid 40 bucks for pizza with Sarah", ids["You"])["expense"]
    assert e["description"] == "Pizza"
