# Amélioration de l'entretien technique — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Transformer le script d'entretien mono-fichier en un projet à deux mondes (cœur révélé autonome + outillage évaluateur), avec une chaîne d'énigme multi-endpoints « hard », mesure du candidat, et une base de tests/CI.

**Architecture :** `core.py` contient TOUTE la logique de l'énigme et reste déployable seul ; il est le seul fichier renvoyé par `inspect.getsource`. `instrument.py` importe `core.app`, y greffe un middleware de mesure et l'endpoint d'admin. `evaluation.py` agrège les jalons par candidat. La dépendance est strictement à sens unique : `instrument`/`evaluation` → `core`, jamais l'inverse. Un test le prouve mécaniquement.

**Tech Stack :** Python 3.11, FastAPI, Uvicorn, pyfiglet, pytest, httpx (TestClient).

---

## File Structure

| Fichier | Responsabilité |
|---|---|
| `core.py` | RÉVÉLÉ, autonome. Token éphémère, ASCII art robuste, chaîne (fil d'Ariane + couche protocole), `/healthz`, `/custom-tasks`. Renommé depuis `entretien-technique.py`. |
| `instrument.py` | ÉVALUATEUR. `from core import app`, middleware de mesure, route `/admin/report`. Point d'entrée hébergé. |
| `evaluation.py` | Registre en mémoire des timelines par candidat + génération du rapport JSON. |
| `tests/test_puzzle.py` | Invariants de l'énigme (transformation, fenêtre, fil d'Ariane, couche C) + mesure. |
| `tests/test_self_contained.py` | Extrait le source révélé, le lance en sous-process isolé, vérifie qu'il démarre seul. |
| `requirements.txt` | Dépendances FIGÉES (core + outillage + tests). |
| `Dockerfile` | `pip install -r requirements.txt`, `HEALTHCHECK`, lance `instrument.py`. |
| `docker-compose.yaml` | Sans clé `version:`, avec `healthcheck`, lance l'instance d'entretien. |
| `.github/workflows/ci.yml` | Lint léger + pytest. |
| `README.md` | Réécrit : modèle deux mondes, lancer une session, lire le rapport, env, note dépôt public. |

**Note :** `entretien-technique.py` est supprimé au profit de `core.py`. Le `inspect.getsource(inspect.getmodule(generate_token))` continuera de renvoyer `core.py` (le module où `generate_token` est défini), donc le candidat reçoit un fichier propre.

---

## Task 1: Scaffolding — requirements figés, renommage en `core.py`, `/healthz`

**Files:**
- Create: `requirements.txt`
- Rename/Modify: `entretien-technique.py` → `core.py`
- Test: `tests/test_puzzle.py`

- [ ] **Step 1: Créer `requirements.txt` (versions figées)**

```
fastapi==0.115.6
uvicorn==0.34.0
pyfiglet==1.0.2
pytest==8.3.4
httpx==0.28.1
```

- [ ] **Step 2: Renommer le script en `core.py`**

Run:
```bash
git mv entretien-technique.py core.py
```

- [ ] **Step 3: Écrire le test d'amorçage + healthz (échoue)**

Create `tests/test_puzzle.py`:

```python
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
```

- [ ] **Step 4: Lancer le test, vérifier l'échec sur `/healthz`**

Run: `python -m pytest tests/test_puzzle.py -v`
Expected: `test_root_returns_instructions` PASS, `test_healthz_ok` FAIL (404).

- [ ] **Step 5: Ajouter l'endpoint `/healthz` dans `core.py`**

Add after the `explain_custom` route in `core.py`:

```python
@app.get("/healthz", response_class=PlainTextResponse)
def healthz():
    return "ok"
```

- [ ] **Step 6: Lancer les tests, vérifier le succès**

Run: `python -m pytest tests/test_puzzle.py -v`
Expected: 2 PASS.

- [ ] **Step 7: Commit**

```bash
git add requirements.txt core.py tests/test_puzzle.py
git commit -m "refactor(core): renomme le script en core.py, fige les deps, ajoute /healthz"
```

---

## Task 2: Invariant de transformation du token

But : verrouiller par un test la propriété « obfuscation réversible » dont dépend toute l'énigme. Pas de changement de comportement.

**Files:**
- Test: `tests/test_puzzle.py`

- [ ] **Step 1: Écrire le test d'invariant (échoue à la compilation tant que le helper n'existe pas)**

Add to `tests/test_puzzle.py`:

```python
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
```

- [ ] **Step 2: Lancer le test, vérifier le succès**

Run: `python -m pytest tests/test_puzzle.py::test_token_obfuscation_is_reversible -v`
Expected: PASS (caractérise le comportement existant).

- [ ] **Step 3: Écrire le test de fenêtre temporelle**

Add to `tests/test_puzzle.py`:

```python
def test_post_token_rejects_wrong_token():
    r = client.post("/token", headers={"Authorization": "Bearer deadbeef"})
    assert r.status_code == 401


def test_post_token_accepts_current_token():
    token = core.generate_token()
    r = client.post("/token", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200
    assert "def generate_token" in r.text  # renvoie le source de core.py
```

- [ ] **Step 4: Lancer les tests, vérifier le succès**

Run: `python -m pytest tests/test_puzzle.py -v`
Expected: tous PASS (note : `test_post_token_accepts_current_token` suppose l'exécution dans la même seconde ; quasi instantané avec TestClient).

- [ ] **Step 5: Commit**

```bash
git add tests/test_puzzle.py
git commit -m "test(core): verrouille l'invariant de transformation et la validation du token"
```

---

## Task 3: Fiabiliser le découpage de l'ASCII art

But : ne plus jamais lever d'`IndexError`/affichage cassé quand le token ne tient pas dans la largeur de la figure (nom long, autre police). Fallback : cadre du token affiché SOUS l'art.

**Files:**
- Modify: `core.py` (fonction `get_token`)
- Test: `tests/test_puzzle.py`

- [ ] **Step 1: Écrire le test de robustesse (échoue)**

Add to `tests/test_puzzle.py`:

```python
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
```

- [ ] **Step 2: Lancer le test, vérifier l'échec**

Run: `python -m pytest tests/test_puzzle.py::test_get_token_survives_long_company -v`
Expected: FAIL (slicing actuel produit un rendu cassé / dépend de la largeur).

- [ ] **Step 3: Réécrire `get_token` avec fallback**

Replace the body of `get_token` in `core.py` with:

```python
@app.get("/token", response_class=PlainTextResponse)
def get_token():
    token = generate_token()
    token = token.upper()
    token = token.replace("A", "Z")

    token_line = "| " + token + " |"
    token_frame = "+" + "-" * (len(token) + 2) + "+"

    ascii_image = pyfiglet.figlet_format(text=entreprise, font="bigmono12", width=float("inf"))
    lines = ascii_image.split("\n")
    h = len(lines)
    w = max((len(line) for line in lines), default=0)

    # Si la figure est assez large, on incruste le cadre en son centre.
    if w >= len(token_frame) + 4 and h >= 4:
        mid = h // 2
        out = []
        for i, line in enumerate(lines):
            line = line.ljust(w)
            if i in (mid - 1, mid + 1):
                start = w // 2 - len(token_frame) // 2
                out.append(line[:start] + token_frame + line[start + len(token_frame):])
            elif i == mid:
                start = w // 2 - len(token_line) // 2
                out.append(line[:start] + token_line + line[start + len(token_line):])
            else:
                out.append(line)
        return "\n".join(out)

    # Fallback : la figure est trop étroite -> on affiche le cadre dessous.
    return ascii_image + "\n" + token_frame + "\n" + token_line + "\n" + token_frame
```

- [ ] **Step 4: Lancer les tests, vérifier le succès**

Run: `python -m pytest tests/test_puzzle.py -v`
Expected: tous PASS.

- [ ] **Step 5: Commit**

```bash
git add core.py tests/test_puzzle.py
git commit -m "fix(core): fiabilise le rendu de l'ASCII art avec fallback hors-borne"
```

---

## Task 4: Fil d'Ariane (hop 1) + couche protocole

But : après l'obtention du source, le candidat décode une constante (ROT13+base64) présente dans `core.py` qui révèle l'endpoint `/relais`. `/relais` exige un header (couche C) et renvoie, encodé, le chemin de l'étape finale `/custom-tasks/{entreprise}`.

**Files:**
- Modify: `core.py`
- Test: `tests/test_puzzle.py`

- [ ] **Step 1: Écrire les tests du fil d'Ariane et de la couche C (échouent)**

Add to `tests/test_puzzle.py`:

```python
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
```

- [ ] **Step 2: Lancer les tests, vérifier l'échec**

Run: `python -m pytest tests/test_puzzle.py -k "fil_ariane or relais" -v`
Expected: FAIL (`FIL_ARIANE` et `/relais` n'existent pas).

- [ ] **Step 3: Ajouter les helpers, la constante et l'endpoint `/relais` dans `core.py`**

Add the imports `base64` and `codecs` at the top of `core.py` (near the other imports), then add after `generate_token`:

```python
def _encode_path(path: str) -> str:
    return base64.b64encode(codecs.encode(path, "rot_13").encode()).decode()


def _decode_path(token: str) -> str:
    return codecs.encode(base64.b64decode(token).decode(), "rot_13")


# Indice obfusqué (ROT13 puis base64) : décode vers le prochain endpoint.
FIL_ARIANE = "L2VyeW52Zg=="
```

Add the `Header` import to the FastAPI import line at the top of `core.py`:

```python
from fastapi import FastAPI, Depends, HTTPException, status, Header
```

Add the `/relais` route after `post_token`:

```python
@app.get("/relais", response_class=PlainTextResponse)
def relais(x_entretien: str = Header(default=None)):
    if x_entretien != entreprise.lower()[::-1]:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Header X-Entretien manquant ou incorrect",
        )
    return _encode_path(f"/custom-tasks/{entreprise}")
```

- [ ] **Step 4: Lancer les tests, vérifier le succès**

Run: `python -m pytest tests/test_puzzle.py -k "fil_ariane or relais" -v`
Expected: 3 PASS. (Le littéral `L2VyeW52Zg==` décode bien : base64 → `/erynvf`, ROT13 → `/relais`.)

- [ ] **Step 5: Mettre à jour le texte des consignes (`explain`)**

In `core.py`, replace the `### ETAPE 3 :` block of the `explain()` return string with:

```
### ETAPE 3 :
Dans ce code source, repérez la constante FIL_ARIANE.
Elle est encodée en ROT13 puis base64 et décode le chemin d'un endpoint caché.
Décodez-la, puis appelez cet endpoint en respectant ce que le code exige (un header).
Il vous révélera, encodé de la même façon, l'étape finale de l'entretien.
```

- [ ] **Step 6: Lancer toute la suite, vérifier le succès**

Run: `python -m pytest tests/test_puzzle.py -v`
Expected: tous PASS.

- [ ] **Step 7: Commit**

```bash
git add core.py tests/test_puzzle.py
git commit -m "feat(core): ajoute le fil d'Ariane (ROT13+base64) et l'endpoint /relais avec couche protocole"
```

---

## Task 5: Registre d'évaluation (`evaluation.py`)

But : un store en mémoire, thread-safe, qui agrège les jalons par candidat (clé IP+User-Agent) et produit un rapport JSON.

**Files:**
- Create: `evaluation.py`
- Test: `tests/test_puzzle.py`

- [ ] **Step 1: Écrire les tests du registre (échouent)**

Add to `tests/test_puzzle.py`:

```python
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
```

- [ ] **Step 2: Lancer les tests, vérifier l'échec**

Run: `python -m pytest tests/test_puzzle.py -k registry -v`
Expected: FAIL (module `evaluation` absent).

- [ ] **Step 3: Créer `evaluation.py`**

```python
"""Registre d'évaluation — agrège les jalons par candidat. ÉVALUATEUR uniquement.

Ce module n'est jamais importé par core.py : il vit côté outillage et n'apparaît
donc pas dans le source révélé au candidat.
"""
import threading
import time


class Registry:
    def __init__(self):
        self._data = {}
        self._lock = threading.Lock()

    def record(self, key: str, event: str, detail: str | None = None):
        with self._lock:
            entry = self._data.setdefault(
                key, {"events": [], "failed_attempts": 0, "errors": []}
            )
            entry["events"].append({"event": event, "ts": time.time()})
            if event == "post_token_fail":
                entry["failed_attempts"] += 1
                if detail:
                    entry["errors"].append(detail)

    def report(self) -> dict:
        with self._lock:
            out = {}
            for key, entry in self._data.items():
                events = entry["events"]
                start = next((e["ts"] for e in events if e["event"] == "start"), None)
                final = next((e["ts"] for e in events if e["event"] == "final"), None)
                duration = (
                    round(final - start, 3)
                    if start is not None and final is not None
                    else None
                )
                out[key] = {
                    "events": events,
                    "failed_attempts": entry["failed_attempts"],
                    "errors": entry["errors"],
                    "duration_to_final_seconds": duration,
                }
            return out


registry = Registry()
```

- [ ] **Step 4: Lancer les tests, vérifier le succès**

Run: `python -m pytest tests/test_puzzle.py -k registry -v`
Expected: 2 PASS.

- [ ] **Step 5: Commit**

```bash
git add evaluation.py tests/test_puzzle.py
git commit -m "feat(evaluation): registre en mémoire des timelines candidat"
```

---

## Task 6: Outillage évaluateur (`instrument.py`) — middleware + rapport admin

But : démarrer l'instance hébergée. Importe `core.app`, greffe un middleware qui enregistre les jalons, expose `/admin/report` protégé par `TT_ADMIN_SECRET`. `core` n'est jamais modifié.

**Files:**
- Create: `instrument.py`
- Test: `tests/test_puzzle.py`

- [ ] **Step 1: Écrire les tests d'instrumentation (échouent)**

Add to `tests/test_puzzle.py`:

```python
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
```

- [ ] **Step 2: Lancer les tests, vérifier l'échec**

Run: `python -m pytest tests/test_puzzle.py -k instrument -v`
Expected: FAIL (module `instrument` absent).

- [ ] **Step 3: Créer `instrument.py`**

```python
"""Point d'entrée ÉVALUATEUR : enveloppe core.app de mesure et d'admin.

Règle d'or : ce module importe core ; core n'importe jamais ce module.
Le POST /token renvoie donc le source de core.py, sans aucune instrumentation.
"""
import os

import uvicorn
from fastapi import Header, HTTPException, status
from fastapi.responses import JSONResponse

from core import app
from evaluation import registry

ADMIN_SECRET = os.getenv("TT_ADMIN_SECRET", "change-me")


@app.middleware("http")
async def track(request, call_next):
    response = await call_next(request)
    client_host = request.client.host if request.client else "unknown"
    key = f"{client_host}|{request.headers.get('user-agent', '')}"
    path = request.url.path
    method = request.method
    status_code = response.status_code

    if method == "GET" and path == "/":
        registry.record(key, "start")
    elif method == "GET" and path == "/token":
        registry.record(key, "get_token")
    elif method == "POST" and path == "/token":
        if status_code == 200:
            registry.record(key, "post_token_ok")
        else:
            registry.record(key, "post_token_fail", detail=request.headers.get("authorization"))
    elif method == "GET" and path == "/relais" and status_code == 200:
        registry.record(key, "hop1")
    elif method == "GET" and path.startswith("/custom-tasks/"):
        registry.record(key, "final")

    return response


@app.get("/admin/report")
def admin_report(x_admin_secret: str = Header(default=None)):
    if x_admin_secret != ADMIN_SECRET:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Secret admin requis"
        )
    return JSONResponse(registry.report())


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000, reload=False)
```

- [ ] **Step 4: Lancer les tests, vérifier le succès**

Run: `python -m pytest tests/test_puzzle.py -k instrument -v`
Expected: 2 PASS.

- [ ] **Step 5: Lancer toute la suite, vérifier le succès**

Run: `python -m pytest tests/test_puzzle.py -v`
Expected: tous PASS.

- [ ] **Step 6: Commit**

```bash
git add instrument.py tests/test_puzzle.py
git commit -m "feat(instrument): middleware de mesure + endpoint admin protégé, sans toucher core"
```

---

## Task 7: Test de déployabilité autonome (`test_self_contained.py`)

But : prouver mécaniquement que le `core.py` extrait via l'API démarre seul, sans aucune dépendance à l'outillage.

**Files:**
- Create: `tests/test_self_contained.py`

- [ ] **Step 1: Écrire le test (échoue si l'extrait n'est pas autonome)**

Create `tests/test_self_contained.py`:

```python
import hashlib
import socket
import subprocess
import sys
import time
from datetime import datetime

import httpx
from fastapi.testclient import TestClient

import core


def _free_port() -> int:
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port


def _real_token() -> str:
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    return hashlib.sha256(now.encode()).hexdigest()[:64]


def test_extracted_core_boots_standalone(tmp_path):
    # 1. Récupère le source révélé via l'API
    token = core.generate_token()
    src = TestClient(core.app).post(
        "/token", headers={"Authorization": f"Bearer {token}"}
    ).text
    assert "import evaluation" not in src  # garde-fou : pas d'instrumentation

    # 2. Écrit l'extrait dans un fichier isolé
    extracted = tmp_path / "extracted.py"
    extracted.write_text(src)

    # 3. Lance l'extrait dans un sous-process propre via uvicorn
    port = _free_port()
    proc = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "extracted:app", "--port", str(port)],
        cwd=tmp_path,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )
    try:
        base = f"http://127.0.0.1:{port}"
        # 4. Attend que /healthz réponde (max ~10s)
        deadline = time.time() + 10
        ready = False
        while time.time() < deadline:
            if proc.poll() is not None:
                raise AssertionError(
                    "L'extrait n'a pas démarré seul:\n" + proc.stdout.read().decode()
                )
            try:
                if httpx.get(base + "/healthz", timeout=0.5).status_code == 200:
                    ready = True
                    break
            except httpx.HTTPError:
                time.sleep(0.2)
        assert ready, "Timeout: /healthz n'a jamais répondu"

        # 5. Rejoue le POST /token avec un token recalculé (retry pour la frontière de seconde)
        ok = False
        for _ in range(3):
            r = httpx.post(
                base + "/token",
                headers={"Authorization": f"Bearer {_real_token()}"},
                timeout=2,
            )
            if r.status_code == 200:
                ok = True
                break
        assert ok, "POST /token n'a pas abouti sur l'instance autonome"
    finally:
        proc.terminate()
        proc.wait(timeout=5)
```

- [ ] **Step 2: Lancer le test, vérifier le succès**

Run: `python -m pytest tests/test_self_contained.py -v`
Expected: PASS (l'extrait démarre et répond ; échouerait si `core` importait l'outillage).

- [ ] **Step 3: Commit**

```bash
git add tests/test_self_contained.py
git commit -m "test(self-contained): prouve que le core extrait se déploie sans l'outillage"
```

---

## Task 8: Dockerfile, docker-compose, healthcheck

But : l'image installe les deps figées, expose un `HEALTHCHECK`, et lance l'instance d'entretien (`instrument.py`). Le compose perd la clé `version:` obsolète et gagne un `healthcheck`.

**Files:**
- Modify: `Dockerfile`
- Modify: `docker-compose.yaml`

- [ ] **Step 1: Réécrire le `Dockerfile`**

```dockerfile
FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

COPY core.py /app/core.py
COPY evaluation.py /app/evaluation.py
COPY instrument.py /app/instrument.py

EXPOSE 8000

HEALTHCHECK --interval=10s --timeout=3s --retries=3 \
  CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/healthz').read()==b'ok' else 1)"

CMD ["python", "instrument.py"]
```

- [ ] **Step 2: Réécrire le `docker-compose.yaml`**

```yaml
services:
  fastapi-test-technique:
    build: .
    ports:
      - "8000:8000"
    environment:
      TT_COMPANY: MA PETITE ENTREPRISE
      TT_ADMIN_SECRET: change-me
      TT_CUSTOMTASKS: |
        Vous devez rédiger un Dockerfile et un docker-compose pour faire fonctionner cette application
        Vous n'avez pas le droit de changer le code source

        Vous devez rédiger les manifests kubernetes pour faire fonctionner l'appli dans un kind

        Vous devez mettre en place un workflow ci/cd de votre choix en lien avec cette application

        BONUS:
        - Proposez une méthode pour obtenir le temps de réalisation d'un candidat.
        - Entourez cette appli d'un ecosystème de production (vous définirez vous même "ecosystème de production")

        Vous devez creer une archive {nom-candidat}-{date}.zip avec les éléments suivants:
        - le script pour récuperer le code source de l'application (ou la liste des commandes)
        - le Dockerfile
        - le docker-compose
        - les manifests kubernetes dans un dossier 'kubernetes'
        - un README.md qui contiendra
          + une explication de votre méthode de travail
          + une explication de l'utilisation de vos scripts
          + vos remarques sur l'entretien
        Vous devez envoyer cette archive au mail suivant: toto@tata.tutu
    healthcheck:
      test: ["CMD", "python", "-c", "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/healthz').read()==b'ok' else 1)"]
      interval: 10s
      timeout: 3s
      retries: 3
```

- [ ] **Step 3: Vérifier la validité du compose**

Run: `docker compose config`
Expected: rendu YAML valide, aucune erreur, pas d'avertissement sur `version`.

- [ ] **Step 4: Commit**

```bash
git add Dockerfile docker-compose.yaml
git commit -m "build(docker): healthcheck, deps figées, lance instrument.py, nettoie le compose"
```

---

## Task 9: Workflow CI

But : exécuter la suite de tests à chaque push/PR.

**Files:**
- Create: `.github/workflows/ci.yml`

- [ ] **Step 1: Créer `.github/workflows/ci.yml`**

```yaml
name: CI

on:
  push:
  pull_request:

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.11"
      - name: Install dependencies
        run: pip install -r requirements.txt
      - name: Run tests
        run: python -m pytest -v
```

- [ ] **Step 2: Vérifier la syntaxe YAML localement**

Run: `python -c "import yaml; yaml.safe_load(open('.github/workflows/ci.yml'))" && echo OK`
Expected: `OK`.

- [ ] **Step 3: Commit**

```bash
git add .github/workflows/ci.yml
git commit -m "ci: exécute la suite pytest sur push et PR"
```

---

## Task 10: Réécriture du README

But : documenter le modèle deux mondes, le lancement d'une session, la lecture du rapport, les variables d'env et la note dépôt public.

**Files:**
- Modify: `README.md`

- [ ] **Step 1: Réécrire `README.md`**

```markdown
# Entretien Technique – DevOps / Systèmes

Exercice d'entretien orienté **administration système** et **DevOps** autour d'une
petite application FastAPI. Le candidat doit « casser » une API en plusieurs étapes,
récupérer son code source, suivre une chaîne d'endpoints cachés, puis conteneuriser
et déployer l'application.

---

## Modèle « deux mondes »

Le projet sépare strictement deux responsabilités :

- **`core.py` — le cœur RÉVÉLÉ et autonome.** Toute la logique de l'énigme. C'est le
  seul fichier renvoyé au candidat via `inspect.getsource`, et il se déploie seul
  (`python core.py`).
- **`instrument.py` + `evaluation.py` — l'outillage ÉVALUATEUR.** Mesure du candidat
  et rapport. Ces modules importent `core` ; `core` ne les importe **jamais**. Le
  candidat ne voit donc aucune trace d'instrumentation dans le source révélé.

Le test `tests/test_self_contained.py` prouve mécaniquement cette séparation.

---

## L'énigme (Phase A)

1. `GET /` — consignes.
2. `GET /token` — token éphémère (valide **1 seconde**) incrusté dans un ASCII art.
   Le token est obfusqué : remplacer les `Z` par des `A`, puis passer en minuscules.
3. `POST /token` avec `Authorization: Bearer <token transformé>` — renvoie le source
   de `core.py`.
4. Dans le source : la constante `FIL_ARIANE` (ROT13 puis base64) décode le chemin
   d'un endpoint caché (`/relais`).
5. `GET /relais` exige un header `X-Entretien` (couche protocole) et renvoie, encodé,
   le chemin de l'étape finale `GET /custom-tasks/{TT_COMPANY}` — les consignes de
   rendu (Phase B : Dockerfile, k8s, CI, livraison).

---

## Lancer une session d'entretien

### docker-compose (recommandé)
```bash
docker compose up --build
```

### docker seul
```bash
docker build -t entretien-technique .
docker run -p 8000:8000 -e TT_ADMIN_SECRET=monsecret entretien-technique
```

API disponible sur http://localhost:8000

---

## Lire le rapport d'évaluation

L'outillage agrège par candidat (heuristique IP + User-Agent) les jalons de
progression, le nombre de tentatives échouées et les traces d'erreur de
transformation.

```bash
curl -H "X-Admin-Secret: $TT_ADMIN_SECRET" http://localhost:8000/admin/report
```

Renvoie un JSON : timeline, durée jusqu'à l'étape finale, tentatives, erreurs.

---

## Variables d'environnement

| Variable | Défaut | Rôle |
|---|---|---|
| `TT_COMPANY` | `THOSTED` | Nom dans l'ASCII art, l'endpoint final et le header `X-Entretien`. |
| `TT_CUSTOMTASKS` | `None` | Tâches additionnelles, séparées par `\n\n`. |
| `TT_ADMIN_SECRET` | `change-me` | Secret du rapport `/admin/report` (outillage uniquement). |

---

## Tests

```bash
pip install -r requirements.txt
python -m pytest -v
```

---

## Note : dépôt public

Ce dépôt est public : l'énigme est volontairement « livre ouvert ». Sa valeur tient à
la **pression temporelle** (fenêtre d'1 s imposant le scripting) et à la **variation
par session** via `TT_COMPANY` / `TT_CUSTOMTASKS`. Le secret d'admin et le mécanisme
d'évaluation vivent hors du source révélé.

---

## Licence
Publié sous licence **MIT**.
```

- [ ] **Step 2: Commit**

```bash
git add README.md
git commit -m "docs: réécrit le README pour le modèle deux mondes et la chaîne d'énigme"
```

---

## Final verification

- [ ] **Lancer toute la suite**

Run: `python -m pytest -v`
Expected: tous les tests PASS (`tests/test_puzzle.py` + `tests/test_self_contained.py`).

- [ ] **Vérifier le compose**

Run: `docker compose config`
Expected: YAML valide, sans clé `version`.

---

## Self-Review (rempli par l'auteur du plan)

- **Couverture du spec :** Composant 1 `core.py` → Tasks 1-4 ; Composant 2 `instrument.py` → Task 6 ; Composant 3 `evaluation.py` → Task 5 ; Composant 4 tests → Tasks 2-7 ; Composant 5 packaging/CI → Tasks 8-9 ; README → Task 10. Robustesse ASCII → Task 3. Difficulté figée « hard » (fenêtre 1 s native, ROT13+base64, header couche C) → Tasks 2-4. Aucun `TT_DIFFICULTY`. ✓
- **Placeholders :** aucun TBD/TODO ; chaque step de code contient le code complet. ✓
- **Cohérence des types :** `Registry.record(key, event, detail=None)` et `Registry.report()` identiques entre `evaluation.py` (Task 5) et leur usage dans `instrument.py` (Task 6) et les tests. `FIL_ARIANE`, `_encode_path`, `_decode_path` cohérents entre `core.py` (Task 4) et les tests. Header `X-Entretien` = `entreprise.lower()[::-1]` partout. ✓
```
