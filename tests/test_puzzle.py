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


def test_get_token_falls_back_when_font_missing(monkeypatch):
    import pyfiglet
    real = pyfiglet.figlet_format

    def fake(*args, **kwargs):
        if kwargs.get("font") == "bigmono12":
            raise pyfiglet.FontNotFound("bigmono12")
        return real(*args, **kwargs)

    monkeypatch.setattr(core.pyfiglet, "figlet_format", fake)
    r = client.get("/token")
    assert r.status_code == 200
    assert "+--" in r.text


def test_get_token_survives_long_company(monkeypatch):
    # Un nom très long ne doit pas casser le rendu
    monkeypatch.setattr(core, "entreprise", "A" * 80)
    r = client.get("/token")
    assert r.status_code == 200
    assert len(r.text) > 0


import base64
import codecs


def _decode_path(s: str) -> str:
    return codecs.encode(base64.b64decode(s).decode(), "rot_13")


def test_fil_ariane_decodes_to_relais():
    # La constante littérale présente dans le source décode vers /relais
    assert _decode_path(core.FIL_ARIANE) == "/relais"


def test_relais_requires_header():
    r = client.get("/relais")
    assert r.status_code == 401


def test_relais_with_header_reveals_next_stage():
    header_value = core.entreprise.lower()[::-1]
    r = client.get("/relais", headers={"X-Entretien": header_value})
    assert r.status_code == 200
    assert _decode_path(r.text.strip()) == f"/custom-tasks/{core.entreprise}"


import evaluation


def test_registry_records_timeline_and_attempts():
    reg = evaluation.Registry()
    reg.record("k1", "start")
    reg.record("k1", "get_token")
    reg.record("k1", "post_token_fail", detail="Bearer xxx")
    reg.record("k1", "post_token_ok")
    reg.record("k1", "final")

    report = reg.report()
    assert "k1" in report
    c = report["k1"]
    assert c["failed_attempts"] == 1
    assert "Bearer xxx" in c["errors"]
    assert {e["event"] for e in c["events"]} >= {"start", "post_token_ok", "final"}
    assert c["duration_to_final_seconds"] is not None
    assert c["duration_to_final_seconds"] >= 0


def test_registry_duration_none_when_incomplete():
    reg = evaluation.Registry()
    reg.record("k2", "start")
    report = reg.report()
    assert report["k2"]["duration_to_final_seconds"] is None


def test_instrument_records_and_reports(monkeypatch):
    monkeypatch.setenv("TT_ADMIN_SECRET", "s3cret")
    import importlib
    import instrument
    importlib.reload(instrument)

    iclient = TestClient(instrument.app)
    iclient.get("/")
    iclient.get("/token")
    iclient.post("/token", headers={"Authorization": "Bearer wrong"})
    token = core.generate_token()
    iclient.post("/token", headers={"Authorization": f"Bearer {token}"})

    # Sans secret -> refusé
    assert iclient.get("/admin/report").status_code == 401
    # Avec secret -> rapport
    r = iclient.get("/admin/report", headers={"X-Admin-Secret": "s3cret"})
    assert r.status_code == 200
    data = r.json()
    assert any(c["failed_attempts"] >= 1 for c in data.values())


def test_instrument_does_not_leak_into_revealed_source():
    # Le source révélé (celui de core) ne doit contenir aucune trace d'instrumentation
    token = core.generate_token()
    src = TestClient(core.app).post(
        "/token", headers={"Authorization": f"Bearer {token}"}
    ).text
    assert "admin/report" not in src
    assert "Registry" not in src
    assert "import evaluation" not in src


def test_instrument_keys_candidates_by_forwarded_ip(monkeypatch):
    # Derrière le reverse proxy, client.host est toujours le proxy :
    # deux candidats au même User-Agent doivent rester distincts.
    monkeypatch.setenv("TT_ADMIN_SECRET", "s3cret")
    import importlib
    import instrument
    importlib.reload(instrument)
    instrument.registry._data.clear()

    iclient = TestClient(instrument.app)
    iclient.get("/", headers={"X-Forwarded-For": "203.0.113.7", "User-Agent": "curl/8"})
    iclient.get("/", headers={"X-Forwarded-For": "198.51.100.9, 10.0.0.1", "User-Agent": "curl/8"})

    data = iclient.get("/admin/report", headers={"X-Admin-Secret": "s3cret"}).json()
    assert set(data) == {"203.0.113.7|curl/8", "198.51.100.9|curl/8"}
