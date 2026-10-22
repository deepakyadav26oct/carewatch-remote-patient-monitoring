import pytest
from fastapi.testclient import TestClient
from app.main import app


@pytest.fixture(scope="module")
def c():
    with TestClient(app) as client:
        yield client


def login(c, user, pw="demo123"):
    r = c.post("/auth/login", data={"username": user, "password": pw})
    return r


def hdr(c, user):
    return {"Authorization": "Bearer " + login(c, user).json()["access_token"]}


def test_login_and_protected_routes(c):
    assert c.get("/patients").status_code == 401
    assert login(c, "dr.rao", "wrong").status_code == 401
    r = login(c, "dr.rao")
    assert r.status_code == 200 and r.json()["user"]["role"] == "physician"
    assert len(c.get("/patients", headers=hdr(c, "dr.rao")).json()) == 8


def test_ingest_needs_key_and_creates_alert(c):
    body = {"patient_id": 1, "hr": 80, "sys": 120, "dia": 80, "spo2": 85, "temp": 37}
    assert c.post("/vitals", json=body).status_code == 401
    r = c.post("/vitals", json=body, headers={"X-API-Key": "test-key"})
    assert r.status_code == 200 and r.json()["new_alerts"] >= 1
    assert c.post("/vitals", json={**body, "spo2": 10}, headers={"X-API-Key": "test-key"}).status_code == 422
    assert "X-Disclaimer" in r.headers


def test_roles_on_acknowledge(c):
    alerts = c.get("/alerts?status=active", headers=hdr(c, "nurse.sen")).json()
    assert alerts
    aid = alerts[0]["id"]
    assert c.post(f"/alerts/{aid}/acknowledge", headers=hdr(c, "nurse.sen")).status_code == 403
    r = c.post(f"/alerts/{aid}/acknowledge", headers=hdr(c, "dr.rao"))
    assert r.status_code == 200 and r.json()["status"] == "acknowledged"


def test_history_and_stats(c):
    h = hdr(c, "dr.rao")
    assert c.get("/patients/1/vitals?hours=1", headers=h).json()
    s = c.get("/model/stats", headers=h).json()
    assert s["alerts_total"] >= 1 and "threshold" in s["alerts_by_layer"]
