from fastapi.testclient import TestClient
import core

client = TestClient(core.app)


def test_root_returns_instructions():
    r = client.get("/")
    assert r.status_code == 200
    assert "entretien technique" in r.text.lower()


def test_healthz_ok():
    r = client.get("/healthz")
    assert r.status_code == 200
    assert r.text.strip() == "ok"
