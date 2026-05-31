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
