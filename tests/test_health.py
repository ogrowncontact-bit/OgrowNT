def test_health_reports_database_and_market_data(client):
    resp = client.get("/api/system/health")
    assert resp.status_code == 200
    body = resp.json()
    names = {c["name"] for c in body["components"]}
    assert {"database", "market_data"} <= names
    assert all(c["status"] == "green" for c in body["components"])
    assert body["overall"] == "green"


def test_root_reports_online(client):
    resp = client.get("/")
    assert resp.status_code == 200
    assert resp.json()["status"] == "online"
