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
