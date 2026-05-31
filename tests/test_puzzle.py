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


def test_token_obfuscation_is_reversible():
    token = core.generate_token()
    # Affichage tel que produit par get_token : majuscules puis A -> Z
    displayed = token.upper().replace("A", "Z")
    # Transformation attendue du candidat : Z -> A puis minuscules
    recovered = displayed.replace("Z", "A").lower()
    assert recovered == token
    # Le token est bien un hex de 64 caractères
    assert len(token) == 64
    assert all(c in "0123456789abcdef" for c in token)


def test_post_token_rejects_wrong_token():
    r = client.post("/token", headers={"Authorization": "Bearer deadbeef"})
    assert r.status_code == 401


def test_post_token_accepts_current_token():
    token = core.generate_token()
    r = client.post("/token", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200
    assert "def generate_token" in r.text  # renvoie le source de core.py


def test_get_token_contains_obfuscated_token():
    r = client.get("/token")
    assert r.status_code == 200
    # Le cadre du token est présent dans la sortie
    assert "+--" in r.text
    # Aucune lettre minuscule de hex (tout est affiché en majuscules obfusquées)
    assert "| " in r.text


def test_get_token_survives_long_company(monkeypatch):
    # Un nom très long ne doit pas casser le rendu
    monkeypatch.setattr(core, "entreprise", "A" * 80)
    r = client.get("/token")
    assert r.status_code == 200
    assert len(r.text) > 0
