# Langfuse self-hébergé en complément de Jaeger

Date : 2026-09-14
Statut : approuvé

## Contexte

Mardik exporte déjà ses traces OpenTelemetry vers Jaeger (générique). Le
projet a un peu de temps disponible en fin de mission ; l'objectif est
d'explorer Langfuse — un outil d'observabilité spécifique aux applications
LLM (prompts, tokens, coûts, sessions, scores) — en le self-hébergeant via
Docker, jamais fait par l'utilisateur auparavant. C'est une exploration
pédagogique, pas un correctif d'incident.

## Objectif

Envoyer les mêmes traces OpenTelemetry vers Langfuse (self-hébergé), **en
plus** de Jaeger, sans rien casser de l'existant (tests, CI, comportement
par défaut sans Langfuse configuré).

## Non-objectifs

- Ne pas remplacer Jaeger — les deux coexistent.
- Ne pas utiliser le SDK Python natif de Langfuse (`@observe`, objets
  `generation`) — on reste sur l'export OTLP générique déjà en place, pour
  ne pas toucher `agent.py`.
- Ne pas ajouter le stack Langfuse à la CI — 6 conteneurs supplémentaires
  pour une exploration personnelle serait disproportionné. Le test associé
  reste local, exclu explicitement de `ci.yml`.
- Ne pas sécuriser la configuration Docker au-delà de ce que fournit le
  compose officiel Langfuse (mots de passe par défaut `CHANGEME`) — usage
  local/dev uniquement, jamais exposé.

## Ce qu'on a vérifié auprès de la documentation officielle Langfuse

- Endpoint d'ingestion OTLP : `POST {LANGFUSE_HOST}/api/public/otel/v1/traces`.
- **HTTP uniquement** (JSON ou protobuf) — gRPC n'est pas supporté par
  Langfuse, contrairement à l'exportateur déjà utilisé pour Jaeger.
- Authentification : Basic Auth, `base64(public_key:secret_key)`, header
  `Authorization: Basic <...>` + `x-langfuse-ingestion-version: 4` (ingestion
  temps réel plutôt que différée de 10 min).
- Auto-provisioning au premier démarrage via les variables d'environnement
  `LANGFUSE_INIT_ORG_ID`, `LANGFUSE_INIT_PROJECT_ID`,
  `LANGFUSE_INIT_PROJECT_PUBLIC_KEY`, `LANGFUSE_INIT_PROJECT_SECRET_KEY`,
  `LANGFUSE_INIT_USER_EMAIL`, `LANGFUSE_INIT_USER_PASSWORD` — évite d'avoir à
  cliquer dans l'UI pour récupérer des clés API.

## Conception

### Docker (`docker-compose.yml`)

Ajout de 6 services, repris du compose officiel Langfuse (v4) :
`postgres`, `clickhouse`, `redis`, `minio`, `langfuse-web` (port 3000),
`langfuse-worker`. Aucun conflit de port avec `jaeger` (16686, 4317, 4318).
Les valeurs `LANGFUSE_INIT_PROJECT_PUBLIC_KEY`/`SECRET_KEY` sont fixées à des
valeurs de dev lisibles (`pk-lf-mardik-dev` / `sk-lf-mardik-dev...`) plutôt
que générées, pour rester reproductible et documentable dans `.env.example`.

### Configuration (`.env.example`, `config.py`)

Nouvelles variables, toutes optionnelles (chaîne vide = désactivé) :

```text
LANGFUSE_HOST=http://localhost:3000
LANGFUSE_PUBLIC_KEY=pk-lf-mardik-dev
LANGFUSE_SECRET_KEY=sk-lf-mardik-dev-000000000000000000000000
```

`Settings` (`config.py`) gagne trois champs correspondants, lus avec des
défauts vides (`os.environ.get(..., "")`).

### Télémétrie (`telemetry.py`)

- `build_telemetry(...)` accepte un nouveau paramètre
  `extra_span_exporters: list[SpanExporter] | None = None` ; pour chacun, un
  `SimpleSpanProcessor` supplémentaire est ajouté au `TracerProvider` déjà
  créé (Jaeger garde son propre processor, inchangé).
- `build_default_telemetry(...)` construit l'exportateur HTTP Langfuse
  (`opentelemetry.exporter.otlp.proto.http.trace_exporter.OTLPSpanExporter`)
  **uniquement si** les clés Langfuse sont fournies, et le passe dans
  `extra_span_exporters`.

### Câblage (`app.py`)

`build_agent` construit la config Langfuse à partir de `Settings` et ne
l'active que si `langfuse_public_key`/`langfuse_secret_key` sont non vides.
Sans configuration Langfuse (cas des tests, de la CI), le comportement est
strictement identique à aujourd'hui.

### Dépendance

Ajout de `opentelemetry-exporter-otlp-proto-http` (`pyproject.toml`).

### Test — `tests/integration/test_live_langfuse.py`

Sur le modèle de `test_live_telemetry.py` : construit l'agent avec la
télémétrie par défaut (Langfuse activé via `.env`), joue un tour, puis
interroge l'API publique Langfuse (`GET /api/public/traces`, même Basic
Auth) en pollant jusqu'à trouver la trace. Suppose Langfuse démarré
(`make up`).

**Exclu de la CI** : `ci.yml` reçoit un `--ignore` explicite sur ce fichier,
comme documenté dans `CHANGELOG.md` (cohérent avec le choix fait pour
`test_live_telemetry.py` avant l'ajout du service Jaeger).

## Critères de réussite

- `uv run pytest tests/unit tests/integration --ignore=tests/integration/test_live_langfuse.py`
  reste entièrement vert, sans Langfuse démarré.
- Avec `make up` (Langfuse + Jaeger), `test_live_langfuse.py` passe : la
  trace apparaît dans Langfuse sous le projet provisionné.
- La CI (`ci.yml`) n'est pas modifiée pour ajouter le stack Langfuse.
- `ruff check .` et `mypy src` restent propres.
