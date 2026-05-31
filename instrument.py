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
