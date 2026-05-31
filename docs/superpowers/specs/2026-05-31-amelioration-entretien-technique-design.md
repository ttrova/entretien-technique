# Design — Amélioration de l'entretien technique

**Date :** 2026-05-31
**Statut :** approuvé (en attente de revue du spec écrit)

## Contexte

`entretien-technique` est un serveur FastAPI mono-fichier (~90 lignes) servant de
support d'entretien technique DevOps / sysadmin. Le candidat « casse » l'API en
plusieurs étapes :

1. `GET /` → consignes en texte brut.
2. `GET /token` → token éphémère (SHA-256 du timestamp à la seconde, tronqué à 64
   caractères) incrusté dans un ASCII art `pyfiglet` du nom de l'entreprise. Le
   token est obfusqué : majuscules puis `A` → `Z`.
3. `POST /token` avec `Authorization: Bearer <token transformé>` (inverser :
   `Z` → `A`, puis minuscules). Valide **1 seconde** → l'API renvoie son propre
   code source via `inspect.getsource`.
4. Le source révèle `GET /custom-tasks/{TT_COMPANY}`, tâches configurables par
   variables d'environnement (`TT_COMPANY`, `TT_CUSTOMTASKS`).

Le projet est **public** et livré avec `Dockerfile` + `docker-compose.yaml`, sous
licence MIT.

### Décisions de cadrage

- **Axes retenus :** robustesse/qualité, richesse de l'exercice, évaluation du
  candidat. Packaging/déploiement écarté (c'est en partie le travail du candidat).
- **Identification candidat :** heuristique IP + User-Agent + fenêtre temporelle,
  zéro friction.
- **Chaînage d'énigme :** fil d'Ariane par décodage (A) + couche protocole (C).
- **Difficulté :** fixe, niveau « hard » uniquement (pas de configuration).
- **Dépôt public :** assumé (open-book). La valeur est dans la pression
  temporelle et la variation par env ; on ne sur-investit pas dans l'anti-triche.

## Principe directeur : deux mondes à sens unique

`inspect.getsource(inspect.getmodule(generate_token))` ne renvoie que le **module
où `generate_token` est défini**. C'est le levier de tout le découpage.

```
core.py                     # RÉVÉLÉ, autonome — toute la logique de l'énigme + chaîne
instrument.py               # ÉVALUATEUR — `from core import app`, ajoute middleware + logging
evaluation.py               # store mémoire des timelines + génération du rapport
tests/
  test_puzzle.py            # invariants de l'énigme (transformation, chaîne)
  test_self_contained.py    # extrait le source révélé → le lance isolé → rejoue la chaîne
requirements.txt            # FIGÉ (deps de core + outillage + tests)
Dockerfile / compose        # lancent instrument.py (= l'instance d'entretien)
.github/workflows/ci.yml    # lint + tests
README.md                   # réécrit : 2 mondes, lancer une session, lire le rapport
```

**Règle d'or :** `instrument` (et `evaluation`) importent `core`. `core`
n'importe **jamais** rien de l'outillage. La dépendance est strictement à sens
unique. Conséquence : le `POST /token` renvoie le source de `core.py` **propre**,
sans une ligne d'instrumentation ; le candidat ne voit pas le mécanisme
d'évaluation et n'en hérite pas.

## Composant 1 — `core.py` (révélé, autonome)

Responsabilité : toute la logique de l'énigme, déployable seule (`python core.py`
fonctionne ; `if __name__ == "__main__": uvicorn.run(...)` conservé).

### Chaîne d'énigme (Phase A), niveau « hard »

1. `GET /` → consignes.
2. `GET /token` → token éphémère dans l'ASCII art.
3. `POST /token` (Bearer transformé, **fenêtre 1 s**) → renvoie le source de
   `core.py`.
4. Le source contient une **constante obfusquée en ROT13+base64** décodant le
   chemin du **hop suivant** (fil d'Ariane). Le candidat lit le code extrait,
   décode la constante, appelle le hop.
5. **Hop 1** → exige une petite transformation supplémentaire **et un header /
   détail de protocole précis** (couche C) → décode le chemin du hop final.
6. **Hop 2 / étape finale** → délivre les consignes de rendu
   (`custom-tasks` / livraison).

Total : **2 hops** après l'obtention du source, couche protocole **activée**.

La **constante obfusquée est un littéral présent dans le source** : c'est
indispensable, sinon le candidat ne pourrait pas la décoder en lisant le code
extrait (`inspect.getsource` renvoie le texte du source, pas des valeurs
calculées au runtime). Le chemin du fil d'Ariane est donc fixe ; la variation
d'une session à l'autre vient de `TT_COMPANY` / `TT_CUSTOMTASKS` et du contenu de
l'étape finale.

### Robustesse intégrée à `core.py`

- **Découpage ASCII art fiabilisé** : ne plante plus si le token ne tient pas
  dans la largeur de la figure (nom d'entreprise long, autre police). Fallback
  propre : si la largeur est insuffisante, afficher le cadre du token sous
  l'ASCII art plutôt que de découper par index hors borne.

### Configuration (`core.py`)

Variables d'environnement (toutes ont un défaut, `core.py` reste autonome) :

- `TT_COMPANY` (défaut `THOSTED`) — nom dans l'ASCII art et l'endpoint custom.
- `TT_CUSTOMTASKS` (défaut `None`) — tâches additionnelles, séparées par `\n\n`.

`TT_DIFFICULTY` **n'existe pas** : le comportement est figé sur « hard ». Le
chemin du fil d'Ariane est un littéral encodé dans `core.py`, pas une valeur
d'environnement.

## Composant 2 — `instrument.py` (évaluateur)

Responsabilité : démarrer l'instance d'entretien réellement hébergée. Importe
l'app de `core`, ajoute un middleware d'observation, expose le rapport.

- `from core import app` puis ajout d'un middleware ASGI qui horodate les
  requêtes pertinentes.
- C'est `instrument.py` (pas `core.py`) que lancent le Dockerfile et le compose
  du dépôt. Le candidat, lui, déploie le `core.py` qu'il a extrait.

## Composant 3 — `evaluation.py` (mesure & rapport)

Responsabilité : agréger les jalons en timelines par candidat et produire le
rapport. Store **en mémoire** (suffisant pour la durée d'un entretien ; pas de
dépendance externe).

### Identification candidat

Heuristique : clé = **IP + User-Agent + fenêtre temporelle**. Approximation
assumée (NAT, reconnexions).

### Jalons enregistrés

- premier `GET /`
- `GET /token`
- premier `POST /token` échoué
- premier `POST /token` réussi
- accès au hop 1 (fil d'Ariane)
- accès au hop 2 / étape finale
- accès `custom-tasks`

### Métriques

- **Tentatives** : nombre de `POST /token` en échec avant le premier succès.
- **Traces d'erreur de transformation** : log du token reçu en échec, pour
  diagnostiquer (lowercase oublié, `Z`→`A` non appliqué, hors fenêtre d'1 s).

### Rapport agrégé

- Endpoint `GET /admin/report`, **protégé par un secret** (`TT_ADMIN_SECRET`,
  variable d'env), renvoyant la timeline + durées + tentatives par candidat en
  **JSON exportable**.
- Cet endpoint et son secret vivent dans `instrument`/`evaluation`, **jamais**
  dans `core` → invisibles dans le source révélé.

## Composant 4 — Tests (`tests/`)

- `test_puzzle.py` : invariants de l'énigme.
  - La transformation `Z`→`A` + minuscules sur le token obfusqué reconstitue bien
    le token courant.
  - La fenêtre d'1 s : un token valide à `t` est rejeté à `t+2 s`.
  - Le fil d'Ariane ROT13+base64 décode vers un chemin existant.
  - Le hop final exige bien le header/protocole de la couche C.
- `test_self_contained.py` : **garantie mécanique de déployabilité**.
  1. appelle l'API, extrait le source révélé,
  2. l'écrit dans un fichier temporaire isolé,
  3. le lance dans un sous-process propre avec uniquement les deps déduites des
     `import`,
  4. rejoue la chaîne de bout en bout contre cette instance.
  - Échoue si quelqu'un introduit par erreur de l'instrumentation dans `core`.

## Composant 5 — Packaging & CI

- `requirements.txt` **figé** (versions épinglées) couvrant deps de `core` +
  outillage + tests.
- `Dockerfile` : `pip install -r requirements.txt`, `HEALTHCHECK`, lance
  `instrument.py`.
- `docker-compose.yaml` : suppression de la clé `version:` obsolète, ajout d'un
  `healthcheck`, lance l'instance d'entretien (`instrument`).
- `.github/workflows/ci.yml` : lint + exécution de la suite pytest.

## README

Réécrit pour couvrir :

- le modèle « deux mondes » (cœur révélé autonome vs outillage évaluateur),
- comment lancer une session d'entretien (`instrument` via compose),
- comment lire le rapport (`/admin/report` + `TT_ADMIN_SECRET`),
- les variables d'environnement disponibles,
- la note « dépôt public / open-book » assumée.

## Gestion des erreurs

- `core.py` : `POST /token` renvoie déjà `401` si token invalide/expiré ;
  conserver. Les hops invalides renvoient `401`/`404` sans fuiter d'indice.
- `/admin/report` : `401` si `TT_ADMIN_SECRET` absent/incorrect.
- Découpage ASCII art : fallback propre, jamais d'`IndexError`.

## Hors périmètre (YAGNI)

- Pas de difficulté configurable (mode « hard » figé).
- Pas de persistance des timelines (store mémoire suffisant).
- Pas de manifests Kubernetes / publication d'image dans le dépôt (c'est le
  travail du candidat).
- Pas d'anti-triche élaboré (dépôt public assumé).
- Pas d'internationalisation.
