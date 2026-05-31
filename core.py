from fastapi import FastAPI, Depends, HTTPException, status, Header
from fastapi.responses import PlainTextResponse
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from datetime import datetime
import base64
import codecs
import hashlib
import inspect
import uvicorn
import pyfiglet
import os

entreprise=os.getenv('TT_COMPANY', 'THOSTED')
custom_tasks=os.getenv('TT_CUSTOMTASKS', None)

app = FastAPI(title="Entretien Technique", docs_url=None, redoc_url=None, openapi_url=None)
security = HTTPBearer()

def generate_token():
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    raw = now.encode()
    return hashlib.sha256(raw).hexdigest()[:64]

@app.get("/", response_class=PlainTextResponse)
def explain():
    return f'''# Bienvenue dans cet entretien technique
## Le contexte :
Vous vous appretez à passer un entretien technique pour {entreprise}.
Cet entretien a pour objectif de tester vos capacités a résoudre des problèmes d'administration systèmes et/ou de DEVOPS. 

## L'entretien :
### ETAPE 1 :
Faites un GET sur /token
Vous verrez un ASCII art avec un token à l'intérieur
Récupérez le token
Mais attention :
- il est modifié
- vous devez remplacer toutes les lettres 'Z' par des 'A'
- vous devez passer le token en minuscules (lowercase)

### ETAPE 2 :
Faites un POST sur /token avec ce token transformé
Le token doit être placé dans le header Authorization en tant que Bearer
Si le token est correct et encore valide (1 seconde), vous récupérez le code source du site web actuel

### ETAPE 3 :
Dans ce code source, repérez la constante FIL_ARIANE.
Elle est encodée en ROT13 puis base64 et décode le chemin d'un endpoint caché.
Décodez-la, puis appelez cet endpoint en respectant ce que le code exige (un header).
Il vous révélera, encodé de la même façon, l'étape finale de l'entretien.'''

@app.get("/custom-tasks/"+entreprise, response_class=PlainTextResponse)
def explain_custom():
    if not custom_tasks: return explain() + "\n Et en fait rien de plus."
    return explain() + '\n\n' + '\n\n'.join([ f'### ETAPE {i+4} :\n' + t for i,t in enumerate(custom_tasks.split('\n\n'))])

@app.get("/token", response_class=PlainTextResponse)
def get_token():
    token = generate_token()
    token = token.upper()
    token = token.replace("A", "Z")

    token_line = "| " + token + " |"
    token_frame = "+" + "-" * (len(token) + 2) + "+"

    try:
        ascii_image = pyfiglet.figlet_format(text=entreprise, font="bigmono12", width=float("inf"))
    except pyfiglet.FontNotFound:
        # La police bigmono12 n'est pas embarquée par défaut ; on retombe sur la police standard.
        ascii_image = pyfiglet.figlet_format(text=entreprise, width=float("inf"))
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

@app.get("/healthz", response_class=PlainTextResponse)
def healthz():
    return "ok"

@app.post("/token", response_class=PlainTextResponse)
def post_token(credentials: HTTPAuthorizationCredentials = Depends(security)):
    current_token = generate_token()
    if credentials.credentials != current_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Token invalide ou expiré"
        )

    source_code = inspect.getsource(inspect.getmodule(generate_token))
    return source_code


def _encode_path(path: str) -> str:
    return base64.b64encode(codecs.encode(path, "rot_13").encode()).decode()


def _decode_path(token: str) -> str:
    return codecs.encode(base64.b64decode(token).decode(), "rot_13")


# Indice obfusqué (ROT13 puis base64) : décode vers le prochain endpoint.
FIL_ARIANE = "L2VyeW52Zg=="


@app.get("/relais", response_class=PlainTextResponse)
def relais(x_entretien: str = Header(default=None)):
    if x_entretien != entreprise.lower()[::-1]:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Header X-Entretien manquant ou incorrect",
        )
    return _encode_path(f"/custom-tasks/{entreprise}")


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000, reload=False)
