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

# Réinitialise la pile de middleware si l'app a déjà démarré (ex: rechargement en tests)
# afin de pouvoir attacher le middleware d'instrumentation sans RuntimeError.
app.middleware_stack = None


def client_ip(request) -> str:
    # En production, l'edge Caddy est le seul client direct : la vraie IP du
    # candidat est la première de X-Forwarded-For, que Caddy réécrit lui-même.
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


@app.middleware("http")
async def track(request, call_next):
    response = await call_next(request)
    key = f"{client_ip(request)}|{request.headers.get('user-agent', '')}"
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
    # Pas de log d'accès : Systeam annonce publiquement n'en garder aucun.
    uvicorn.run(app, host="0.0.0.0", port=8000, reload=False, access_log=False)
