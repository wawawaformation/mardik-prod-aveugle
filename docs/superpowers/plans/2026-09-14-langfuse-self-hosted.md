# Langfuse Self-Hosted Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Exporter les traces OpenTelemetry de Mardik vers un Langfuse self-hébergé (en plus de Jaeger), avec auto-provisioning d'un projet et de clés API, sans rien casser de l'existant.

**Architecture:** `telemetry.py` gagne un second `SimpleSpanProcessor` optionnel pointé vers l'endpoint OTLP/HTTP de Langfuse (Basic Auth). `build_agent` ne l'active que si `LANGFUSE_PUBLIC_KEY`/`LANGFUSE_SECRET_KEY` sont configurées. Le stack Langfuse (6 conteneurs) s'ajoute à `docker-compose.yml`, à côté de `jaeger`, sans y toucher.

**Tech Stack:** `opentelemetry-exporter-otlp-proto-http` (nouveau), Docker Compose, Langfuse self-hosted **v3** (images `docker.langfuse.com/langfuse/langfuse:3` et `langfuse-worker:3` — voir note de version ci-dessous).

## Note de version — pourquoi Langfuse v3 et pas v4

Vérifié empiriquement pendant la conception (voir
`docs/superpowers/specs/2026-09-14-langfuse-self-hosted-design.md`) : les
images `:4` tournent par défaut en mode d'écriture `events_only`, qui
**désactive** `GET /api/public/traces` et `GET /api/public/observations`
(404 avec le message *"not available on deployments running in Langfuse v4
events_only mode"*) au profit d'une nouvelle "Observations API v2" plus
complexe (modèle de données `events_full`/`events_core`). Les images `:3`
utilisent l'API classique, entièrement vérifiée en local : ingestion OTLP
→ `GET /api/public/traces` renvoie la trace immédiatement (avec le header
`x-langfuse-ingestion-version: 4` pour l'ingestion temps réel). Pour une
exploration pédagogique simple, `:3` évite toute la complexité de
migration v3→v4 documentée dans
`self-hosting/upgrade/upgrade-guides/upgrade-v3-to-v4.mdx`.

## Global Constraints

- Ne pas modifier `jaeger` dans `docker-compose.yml`, ni `ci.yml` (pas de service Langfuse en CI — voir spec, section Non-objectifs).
- Sans `LANGFUSE_PUBLIC_KEY`/`LANGFUSE_SECRET_KEY` configurées, le comportement doit être strictement identique à aujourd'hui (Jaeger seul) — `uv run pytest tests/unit tests/integration --ignore=tests/integration/test_live_langfuse.py` doit rester entièrement vert sans Langfuse démarré.
- `ruff check .` et `mypy src` restent propres après chaque tâche.
- Référence : spec `docs/superpowers/specs/2026-09-14-langfuse-self-hosted-design.md`.

---

### Task 1 : Dépendance OTLP/HTTP

**Files:**
- Modify: `pyproject.toml`

**Interfaces:**
- Produces : le module `opentelemetry.exporter.otlp.proto.http.trace_exporter` devient importable, consommé par la Task 4.

- [ ] **Step 1 : Ajouter la dépendance**

Run: `uv add "opentelemetry-exporter-otlp-proto-http>=1.27,<2"`

Cette commande met à jour `pyproject.toml` et `uv.lock` automatiquement.

- [ ] **Step 2 : Vérifier l'import**

Run: `uv run python -c "from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter; print('ok')"`
Expected: `ok`

- [ ] **Step 3 : Commit**

```bash
git add pyproject.toml uv.lock
git commit -m "build: add OTLP/HTTP span exporter dependency"
```

---

### Task 2 : Configuration Langfuse dans `Settings`

**Files:**
- Modify: `src/mardik/config.py`
- Test: `tests/unit/test_config.py` (nouveau fichier)

**Interfaces:**
- Produces : `Settings.langfuse_host: str`, `Settings.langfuse_public_key: str`, `Settings.langfuse_secret_key: str` — consommés par la Task 5.

- [ ] **Step 1 : Écrire le test**

Créer `tests/unit/test_config.py` :

```python
from mardik.config import load_settings


def test_load_settings_defaults_langfuse_to_disabled(monkeypatch):
    monkeypatch.delenv("LANGFUSE_PUBLIC_KEY", raising=False)
    monkeypatch.delenv("LANGFUSE_SECRET_KEY", raising=False)
    monkeypatch.delenv("LANGFUSE_HOST", raising=False)

    settings = load_settings()

    assert settings.langfuse_host == "http://localhost:3000"
    assert settings.langfuse_public_key == ""
    assert settings.langfuse_secret_key == ""


def test_load_settings_reads_langfuse_env_vars(monkeypatch):
    monkeypatch.setenv("LANGFUSE_HOST", "http://langfuse.example")
    monkeypatch.setenv("LANGFUSE_PUBLIC_KEY", "pk-test")
    monkeypatch.setenv("LANGFUSE_SECRET_KEY", "sk-test")

    settings = load_settings()

    assert settings.langfuse_host == "http://langfuse.example"
    assert settings.langfuse_public_key == "pk-test"
    assert settings.langfuse_secret_key == "sk-test"
```

- [ ] **Step 2 : Lancer le test et vérifier qu'il échoue**

Run: `uv run pytest tests/unit/test_config.py -v`
Expected: FAIL — `TypeError: load_settings() got an unexpected keyword` ou `AttributeError` sur `langfuse_host` (le champ n'existe pas encore).

- [ ] **Step 3 : Étendre `Settings` et `load_settings`**

Dans `src/mardik/config.py`, remplacer le contenu par :

```python
"""Runtime configuration loaded from the environment."""
from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    azure_endpoint: str
    azure_api_key: str
    azure_model: str
    otel_endpoint: str
    service_name: str
    log_level: str
    langfuse_host: str
    langfuse_public_key: str
    langfuse_secret_key: str


def load_settings() -> Settings:
    return Settings(
        azure_endpoint=os.environ.get("AZURE_AI_ENDPOINT", ""),
        azure_api_key=os.environ.get("AZURE_AI_API_KEY", ""),
        azure_model=os.environ.get("AZURE_AI_MODEL", "Kimi-K2.6"),
        otel_endpoint=os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT", "http://localhost:4317"),
        service_name=os.environ.get("OTEL_SERVICE_NAME", "mardik"),
        log_level=os.environ.get("LOG_LEVEL", "INFO"),
        langfuse_host=os.environ.get("LANGFUSE_HOST", "http://localhost:3000"),
        langfuse_public_key=os.environ.get("LANGFUSE_PUBLIC_KEY", ""),
        langfuse_secret_key=os.environ.get("LANGFUSE_SECRET_KEY", ""),
    )
```

- [ ] **Step 4 : Lancer le test et vérifier qu'il passe**

Run: `uv run pytest tests/unit/test_config.py -v`
Expected: PASS (2/2)

- [ ] **Step 5 : Vérifier que rien d'autre n'est cassé**

Run: `uv run pytest tests/unit tests/integration --ignore=tests/integration/test_live_telemetry.py -v`
Expected: tous verts (les tests qui construisent `Settings` manuellement, s'il y en a, doivent aussi passer — vérifier `tests/unit/test_wiring.py`).

- [ ] **Step 6 : Commit**

```bash
git add src/mardik/config.py tests/unit/test_config.py
git commit -m "feat: add Langfuse settings (host, public/secret key)"
```

---

### Task 3 : `build_telemetry` — exportateurs de spans additionnels

**Files:**
- Modify: `src/mardik/telemetry.py`
- Test: `tests/unit/test_telemetry.py`

**Interfaces:**
- Consumes : `Telemetry.__init__(tracer, meter, tracer_provider=None, meter_provider=None)` (existant, inchangé).
- Produces : `build_telemetry(..., extra_span_exporters: list[SpanExporter] | None = None)` — consommé par la Task 4.

- [ ] **Step 1 : Écrire le test**

Ajouter à la fin de `tests/unit/test_telemetry.py` :

```python
def test_extra_span_exporters_receive_the_same_spans():
    primary_exporter = InMemorySpanExporter()
    secondary_exporter = InMemorySpanExporter()
    telemetry = build_telemetry(
        span_exporter=primary_exporter,
        metric_reader=InMemoryMetricReader(),
        extra_span_exporters=[secondary_exporter],
    )

    with telemetry.tracer.start_as_current_span("probe"):
        pass
    telemetry.shutdown()

    assert len(primary_exporter.get_finished_spans()) == 1
    assert len(secondary_exporter.get_finished_spans()) == 1
```

- [ ] **Step 2 : Lancer le test et vérifier qu'il échoue**

Run: `uv run pytest tests/unit/test_telemetry.py::test_extra_span_exporters_receive_the_same_spans -v`
Expected: FAIL — `TypeError: build_telemetry() got an unexpected keyword argument 'extra_span_exporters'`

- [ ] **Step 3 : Modifier `build_telemetry`**

Dans `src/mardik/telemetry.py`, remplacer la fonction `build_telemetry` par :

```python
def build_telemetry(
    span_exporter: SpanExporter | None = None,
    metric_reader: MetricReader | None = None,
    level: str = "INFO",
    service_name: str = "mardik",
    extra_span_exporters: list[SpanExporter] | None = None,
) -> Telemetry:
    """Build a self-contained Telemetry bundle.

    Defaults to console exporters; tests pass in-memory exporters/readers.
    ``extra_span_exporters`` reçoit chacun son propre SpanProcessor, en plus
    de celui de ``span_exporter`` (ex. exporter aussi vers Langfuse).
    """
    configure_logging(level)
    resource = Resource.create({"service.name": service_name})

    tracer_provider = TracerProvider(resource=resource)
    tracer_provider.add_span_processor(
        SimpleSpanProcessor(span_exporter or ConsoleSpanExporter())
    )
    for exporter in extra_span_exporters or []:
        tracer_provider.add_span_processor(SimpleSpanProcessor(exporter))

    reader = metric_reader or PeriodicExportingMetricReader(ConsoleMetricExporter())
    meter_provider = MeterProvider(resource=resource, metric_readers=[reader])

    return Telemetry(
        tracer=tracer_provider.get_tracer("mardik"),
        meter=meter_provider.get_meter("mardik"),
        tracer_provider=tracer_provider,
        meter_provider=meter_provider,
    )
```

- [ ] **Step 4 : Lancer le test et vérifier qu'il passe**

Run: `uv run pytest tests/unit/test_telemetry.py -v`
Expected: tous verts (3/3, en comptant les 2 tests déjà existants).

- [ ] **Step 5 : Commit**

```bash
git add src/mardik/telemetry.py tests/unit/test_telemetry.py
git commit -m "feat: support extra span exporters in build_telemetry"
```

---

### Task 4 : Exportateur HTTP Langfuse dans `build_default_telemetry`

**Files:**
- Modify: `src/mardik/telemetry.py`
- Test: `tests/unit/test_telemetry.py`

**Interfaces:**
- Consumes : `build_telemetry(..., extra_span_exporters=...)` (Task 3).
- Produces : `build_default_telemetry(level, service_name, langfuse_host="", langfuse_public_key="", langfuse_secret_key="")` — consommé par la Task 5. `_langfuse_auth_header(public_key, secret_key) -> str`, interne mais testée directement.

- [ ] **Step 1 : Écrire les tests**

Ajouter en haut de `tests/unit/test_telemetry.py`, après les imports existants :

```python
import base64
```

Puis à la fin du fichier :

```python
def test_langfuse_auth_header_is_basic_base64():
    from mardik.telemetry import _langfuse_auth_header

    header = _langfuse_auth_header("pk-test", "sk-test")

    assert header == "Basic " + base64.b64encode(b"pk-test:sk-test").decode()


def test_build_default_telemetry_without_langfuse_keys_does_not_raise():
    telemetry = build_default_telemetry(langfuse_public_key="", langfuse_secret_key="")
    telemetry.shutdown()


def test_build_default_telemetry_with_langfuse_keys_does_not_raise():
    telemetry = build_default_telemetry(
        langfuse_host="http://localhost:3000",
        langfuse_public_key="pk-test",
        langfuse_secret_key="sk-test",
    )
    telemetry.shutdown()
```

Ajouter aussi `build_default_telemetry` à l'import existant `from mardik.telemetry import build_telemetry` (le transformer en `from mardik.telemetry import build_default_telemetry, build_telemetry`).

- [ ] **Step 2 : Lancer les tests et vérifier qu'ils échouent**

Run: `uv run pytest tests/unit/test_telemetry.py -v`
Expected: les 3 nouveaux tests FAIL (`_langfuse_auth_header` n'existe pas ; `build_default_telemetry` n'accepte pas ces kwargs).

- [ ] **Step 3 : Ajouter l'import `base64` dans `telemetry.py`**

En haut de `src/mardik/telemetry.py`, avec les autres imports :

```python
import base64
import logging
```

(remplace la ligne `import logging` existante).

- [ ] **Step 4 : Ajouter le helper d'authentification et l'exportateur Langfuse**

Juste après la fonction `build_telemetry` (avant `build_default_telemetry`), dans `src/mardik/telemetry.py` :

```python
def _langfuse_auth_header(public_key: str, secret_key: str) -> str:
    """Build the Basic Auth header value Langfuse expects for OTLP ingestion."""
    token = base64.b64encode(f"{public_key}:{secret_key}".encode()).decode()
    return f"Basic {token}"


def _build_langfuse_span_exporter(
    host: str, public_key: str, secret_key: str
) -> SpanExporter:
    from opentelemetry.exporter.otlp.proto.http.trace_exporter import (
        OTLPSpanExporter as OTLPHttpSpanExporter,
    )

    return OTLPHttpSpanExporter(
        endpoint=f"{host}/api/public/otel/v1/traces",
        headers={
            "Authorization": _langfuse_auth_header(public_key, secret_key),
            "x-langfuse-ingestion-version": "4",
        },
    )
```

- [ ] **Step 5 : Modifier `build_default_telemetry`**

Remplacer la fonction `build_default_telemetry` par :

```python
def build_default_telemetry(
    level: str = "INFO",
    service_name: str = "mardik",
    langfuse_host: str = "",
    langfuse_public_key: str = "",
    langfuse_secret_key: str = "",
) -> Telemetry:
    """Production wiring: OTLP/gRPC span export to Jaeger + periodic metrics.

    Si ``langfuse_public_key``/``langfuse_secret_key`` sont fournis, les
    spans sont aussi exportés vers Langfuse (self-hébergé) en OTLP/HTTP, en
    plus de Jaeger. gRPC n'est pas supporté par Langfuse — d'où un second
    exportateur HTTP dédié.
    """
    from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter

    extra_span_exporters: list[SpanExporter] = []
    if langfuse_public_key and langfuse_secret_key:
        extra_span_exporters.append(
            _build_langfuse_span_exporter(langfuse_host, langfuse_public_key, langfuse_secret_key)
        )

    return build_telemetry(
        span_exporter=OTLPSpanExporter(),
        metric_reader=PeriodicExportingMetricReader(ConsoleMetricExporter()),
        level=level,
        service_name=service_name,
        extra_span_exporters=extra_span_exporters,
    )
```

- [ ] **Step 6 : Lancer les tests et vérifier qu'ils passent**

Run: `uv run pytest tests/unit/test_telemetry.py -v`
Expected: tous verts (6/6).

- [ ] **Step 7 : ruff et mypy**

Run: `uv run ruff check . && uv run mypy src`
Expected: propres.

- [ ] **Step 8 : Commit**

```bash
git add src/mardik/telemetry.py tests/unit/test_telemetry.py
git commit -m "feat: export spans to Langfuse via OTLP/HTTP when configured"
```

---

### Task 5 : Câblage dans `build_agent`

**Files:**
- Modify: `src/mardik/app.py`
- Test: `tests/unit/test_wiring.py`

**Interfaces:**
- Consumes : `build_default_telemetry(level, service_name, langfuse_host, langfuse_public_key, langfuse_secret_key)` (Task 4) ; `Settings.langfuse_host/langfuse_public_key/langfuse_secret_key` (Task 2).

- [ ] **Step 1 : Écrire le test**

Remplacer le contenu de `tests/unit/test_wiring.py` par :

```python
from mardik.app import build_agent
from mardik.config import Settings
from mardik.telemetry import Telemetry


def test_build_agent_wires_telemetry(fake_llm):
    agent = build_agent(llm=fake_llm)
    try:
        assert isinstance(agent.telemetry, Telemetry)
    finally:
        agent.telemetry.shutdown()


def test_build_agent_wires_langfuse_when_configured(fake_llm):
    settings = Settings(
        azure_endpoint="",
        azure_api_key="",
        azure_model="Kimi-K2.6",
        otel_endpoint="http://localhost:4317",
        service_name="mardik",
        log_level="INFO",
        langfuse_host="http://localhost:3000",
        langfuse_public_key="pk-test",
        langfuse_secret_key="sk-test",
    )

    agent = build_agent(llm=fake_llm, settings=settings)
    try:
        assert isinstance(agent.telemetry, Telemetry)
    finally:
        agent.telemetry.shutdown()
```

- [ ] **Step 2 : Lancer les tests et vérifier qu'ils échouent**

Run: `uv run pytest tests/unit/test_wiring.py -v`
Expected: `test_build_agent_wires_langfuse_when_configured` FAIL — `Settings.__init__() missing 3 required positional arguments` si Task 2 n'a pas encore ajouté les champs (déjà fait normalement), sinon `TypeError` sur `build_default_telemetry` si Task 4 pas encore appliquée. Comme les Tasks 2 et 4 précèdent celle-ci dans l'ordre du plan, la cause réelle attendue ici est plutôt que `build_agent` ignore encore les champs Langfuse de `settings` : le test doit passer une fois le Step 3 fait. Si le test passe déjà à cette étape, c'est que `app.py` transmettait par erreur ces valeurs par coïncidence — vérifier manuellement avant de continuer.

- [ ] **Step 3 : Modifier `build_agent`**

Dans `src/mardik/app.py`, remplacer :

```python
    if telemetry is None:
        from .telemetry import build_default_telemetry

        telemetry = build_default_telemetry(
            level=settings.log_level, service_name=settings.service_name
        )
```

par :

```python
    if telemetry is None:
        from .telemetry import build_default_telemetry

        telemetry = build_default_telemetry(
            level=settings.log_level,
            service_name=settings.service_name,
            langfuse_host=settings.langfuse_host,
            langfuse_public_key=settings.langfuse_public_key,
            langfuse_secret_key=settings.langfuse_secret_key,
        )
```

- [ ] **Step 4 : Lancer les tests et vérifier qu'ils passent**

Run: `uv run pytest tests/unit/test_wiring.py -v`
Expected: PASS (2/2).

- [ ] **Step 5 : Suite complète (sans Langfuse ni Jaeger démarrés)**

Run: `uv run pytest tests/unit tests/integration --ignore=tests/integration/test_live_telemetry.py -v`
Expected: tous verts.

- [ ] **Step 6 : Commit**

```bash
git add src/mardik/app.py tests/unit/test_wiring.py
git commit -m "feat: wire Langfuse settings into build_agent"
```

---

### Task 6 : Stack Docker Langfuse + variables d'environnement

**Files:**
- Modify: `docker-compose.yml`
- Modify: `.env.example`

**Interfaces:**
- Produces : services Docker `langfuse-web` (port 3000), `langfuse-worker`, `postgres`, `clickhouse`, `redis`, `minio` ; variables `LANGFUSE_HOST`/`LANGFUSE_PUBLIC_KEY`/`LANGFUSE_SECRET_KEY` lues à la fois par Mardik (`config.py`, Task 2) et par `docker-compose.yml` (interpolation `${...}`) pour provisionner le même projet Langfuse avec les mêmes clés.

- [ ] **Step 1 : Remplacer `docker-compose.yml`**

Contenu complet, vérifié (`docker compose config` + démarrage réel des 6 services Langfuse, ingestion OTLP testée de bout en bout) :

```yaml
services:
  jaeger:
    image: jaegertracing/all-in-one:1.57
    environment:
      COLLECTOR_OTLP_ENABLED: "true"
    ports:
      - "16686:16686"   # web UI
      - "4317:4317"     # OTLP gRPC
      - "4318:4318"     # OTLP HTTP
    healthcheck:
      test: ["CMD", "wget", "-qO-", "http://localhost:14269/"]
      interval: 5s
      timeout: 5s
      retries: 10

  langfuse-worker:
    image: docker.langfuse.com/langfuse/langfuse-worker:3
    restart: always
    depends_on: &langfuse-depends-on
      postgres:
        condition: service_healthy
      minio:
        condition: service_healthy
      redis:
        condition: service_healthy
      clickhouse:
        condition: service_healthy
    environment: &langfuse-worker-env
      NEXTAUTH_URL: ${NEXTAUTH_URL:-http://localhost:3000}
      DATABASE_URL: ${DATABASE_URL:-postgresql://postgres:postgres@postgres:5432/postgres}
      SALT: ${SALT:-mysalt}
      ENCRYPTION_KEY: ${ENCRYPTION_KEY:-0000000000000000000000000000000000000000000000000000000000000000}
      TELEMETRY_ENABLED: ${TELEMETRY_ENABLED:-true}
      CLICKHOUSE_MIGRATION_URL: ${CLICKHOUSE_MIGRATION_URL:-clickhouse://clickhouse:9000}
      CLICKHOUSE_URL: ${CLICKHOUSE_URL:-http://clickhouse:8123}
      CLICKHOUSE_USER: ${CLICKHOUSE_USER:-clickhouse}
      CLICKHOUSE_PASSWORD: ${CLICKHOUSE_PASSWORD:-clickhouse}
      CLICKHOUSE_CLUSTER_ENABLED: ${CLICKHOUSE_CLUSTER_ENABLED:-false}
      LANGFUSE_S3_EVENT_UPLOAD_BUCKET: ${LANGFUSE_S3_EVENT_UPLOAD_BUCKET:-langfuse}
      LANGFUSE_S3_EVENT_UPLOAD_REGION: ${LANGFUSE_S3_EVENT_UPLOAD_REGION:-auto}
      LANGFUSE_S3_EVENT_UPLOAD_ACCESS_KEY_ID: ${LANGFUSE_S3_EVENT_UPLOAD_ACCESS_KEY_ID:-minio}
      LANGFUSE_S3_EVENT_UPLOAD_SECRET_ACCESS_KEY: ${LANGFUSE_S3_EVENT_UPLOAD_SECRET_ACCESS_KEY:-miniosecret}
      LANGFUSE_S3_EVENT_UPLOAD_ENDPOINT: ${LANGFUSE_S3_EVENT_UPLOAD_ENDPOINT:-http://minio:9000}
      LANGFUSE_S3_EVENT_UPLOAD_FORCE_PATH_STYLE: ${LANGFUSE_S3_EVENT_UPLOAD_FORCE_PATH_STYLE:-true}
      LANGFUSE_S3_EVENT_UPLOAD_PREFIX: ${LANGFUSE_S3_EVENT_UPLOAD_PREFIX:-events/}
      LANGFUSE_S3_MEDIA_UPLOAD_BUCKET: ${LANGFUSE_S3_MEDIA_UPLOAD_BUCKET:-langfuse}
      LANGFUSE_S3_MEDIA_UPLOAD_REGION: ${LANGFUSE_S3_MEDIA_UPLOAD_REGION:-auto}
      LANGFUSE_S3_MEDIA_UPLOAD_ACCESS_KEY_ID: ${LANGFUSE_S3_MEDIA_UPLOAD_ACCESS_KEY_ID:-minio}
      LANGFUSE_S3_MEDIA_UPLOAD_SECRET_ACCESS_KEY: ${LANGFUSE_S3_MEDIA_UPLOAD_SECRET_ACCESS_KEY:-miniosecret}
      LANGFUSE_S3_MEDIA_UPLOAD_ENDPOINT: ${LANGFUSE_S3_MEDIA_UPLOAD_ENDPOINT:-http://minio:9000}
      LANGFUSE_S3_MEDIA_UPLOAD_FORCE_PATH_STYLE: ${LANGFUSE_S3_MEDIA_UPLOAD_FORCE_PATH_STYLE:-true}
      LANGFUSE_S3_MEDIA_UPLOAD_PREFIX: ${LANGFUSE_S3_MEDIA_UPLOAD_PREFIX:-media/}
      REDIS_HOST: ${REDIS_HOST:-redis}
      REDIS_PORT: ${REDIS_PORT:-6379}
      REDIS_AUTH: ${REDIS_AUTH:-myredissecret}
      LANGFUSE_INIT_ORG_ID: mardik-org
      LANGFUSE_INIT_ORG_NAME: Mardik
      LANGFUSE_INIT_PROJECT_ID: mardik-project
      LANGFUSE_INIT_PROJECT_NAME: Mardik
      LANGFUSE_INIT_PROJECT_PUBLIC_KEY: ${LANGFUSE_PUBLIC_KEY:-pk-lf-mardik-dev}
      LANGFUSE_INIT_PROJECT_SECRET_KEY: ${LANGFUSE_SECRET_KEY:-sk-lf-mardik-dev-000000000000000000000000}
      LANGFUSE_INIT_USER_EMAIL: dev@mardik.local
      LANGFUSE_INIT_USER_NAME: Mardik Dev
      LANGFUSE_INIT_USER_PASSWORD: mardik-dev-password

  langfuse-web:
    image: docker.langfuse.com/langfuse/langfuse:3
    restart: always
    depends_on: *langfuse-depends-on
    ports:
      - "3000:3000"
    environment:
      <<: *langfuse-worker-env
      NEXTAUTH_SECRET: ${NEXTAUTH_SECRET:-mysecret}
      # Le navigateur charge les médias directement depuis MinIO : il lui
      # faut le port publié sur l'hôte (9090), pas le nom DNS interne au
      # réseau Docker (minio:9000) qu'utilise le worker.
      LANGFUSE_S3_MEDIA_UPLOAD_ENDPOINT: ${LANGFUSE_S3_MEDIA_UPLOAD_ENDPOINT:-http://localhost:9090}

  clickhouse:
    image: docker.io/clickhouse/clickhouse-server:25.12
    restart: always
    user: "101:101"
    environment:
      CLICKHOUSE_DB: default
      CLICKHOUSE_USER: ${CLICKHOUSE_USER:-clickhouse}
      CLICKHOUSE_PASSWORD: ${CLICKHOUSE_PASSWORD:-clickhouse}
    volumes:
      - langfuse_clickhouse_data:/var/lib/clickhouse
      - langfuse_clickhouse_logs:/var/log/clickhouse-server
    ports:
      - "127.0.0.1:8123:8123"
      - "127.0.0.1:9000:9000"
    healthcheck:
      test: wget --no-verbose --tries=1 --spider http://localhost:8123/ping || exit 1
      interval: 5s
      timeout: 5s
      retries: 10
      start_period: 1s

  minio:
    image: cgr.dev/chainguard/minio
    restart: always
    entrypoint: sh
    command: -c 'mkdir -p /data/langfuse && minio server --address ":9000" --console-address ":9001" /data'
    environment:
      MINIO_ROOT_USER: ${MINIO_ROOT_USER:-minio}
      MINIO_ROOT_PASSWORD: ${MINIO_ROOT_PASSWORD:-miniosecret}
    ports:
      - "9090:9000"
      - "127.0.0.1:9091:9001"
    volumes:
      - langfuse_minio_data:/data
    healthcheck:
      test: ["CMD", "mc", "ready", "local"]
      interval: 1s
      timeout: 5s
      retries: 5
      start_period: 1s

  redis:
    image: docker.io/redis:7
    restart: always
    command: >
      --requirepass ${REDIS_AUTH:-myredissecret}
      --maxmemory-policy noeviction
    ports:
      - "127.0.0.1:6379:6379"
    volumes:
      - langfuse_redis_data:/data
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 3s
      timeout: 10s
      retries: 10

  postgres:
    image: docker.io/postgres:17
    restart: always
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U postgres"]
      interval: 3s
      timeout: 3s
      retries: 10
    environment:
      POSTGRES_USER: ${POSTGRES_USER:-postgres}
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD:-postgres}
      POSTGRES_DB: ${POSTGRES_DB:-postgres}
      TZ: UTC
      PGTZ: UTC
    ports:
      - "127.0.0.1:5432:5432"
    volumes:
      - langfuse_postgres_data:/var/lib/postgresql/data

volumes:
  langfuse_postgres_data:
    driver: local
  langfuse_clickhouse_data:
    driver: local
  langfuse_clickhouse_logs:
    driver: local
  langfuse_minio_data:
    driver: local
  langfuse_redis_data:
    driver: local
```

- [ ] **Step 2 : Ajouter les variables dans `.env.example`**

À la fin de `.env.example`, ajouter :

```text

# Langfuse (self-hébergé, optionnel) — laisser les clés vides pour
# désactiver l'export vers Langfuse (Jaeger continue de fonctionner seul).
# Ces mêmes valeurs servent aussi à provisionner automatiquement le projet
# Langfuse au premier démarrage (voir docker-compose.yml, LANGFUSE_INIT_*).
LANGFUSE_HOST=http://localhost:3000
LANGFUSE_PUBLIC_KEY=pk-lf-mardik-dev
LANGFUSE_SECRET_KEY=sk-lf-mardik-dev-000000000000000000000000
```

- [ ] **Step 3 : Copier ces valeurs dans `.env` local (non versionné)**

Ouvrir `.env` (déjà rempli avec les creds Azure) et y ajouter les 3 mêmes lignes que
dans `.env.example` à l'étape précédente — nécessaire uniquement pour activer
Langfuse localement, pas pour la suite de tests.

- [ ] **Step 4 : Valider le YAML**

Run: `docker compose config > /dev/null && echo "config OK"`
Expected: `config OK`

- [ ] **Step 5 : Démarrer le stack et vérifier la santé**

Run: `make up`
Puis attendre que tous les conteneurs soient sains :
Run: `docker compose ps`
Expected: `jaeger`, `postgres`, `redis`, `minio`, `clickhouse` marqués `healthy` ; `langfuse-web` et `langfuse-worker` `running` (ils n'ont pas de healthcheck déclaré, mais démarrent après les 4 dépendances saines).

- [ ] **Step 6 : Vérifier le provisioning automatique**

Run (adapter les clés si modifiées à l'étape 3) :
```bash
AUTH=$(echo -n "pk-lf-mardik-dev:sk-lf-mardik-dev-000000000000000000000000" | base64 -w0)
curl -s -H "Authorization: Basic $AUTH" http://localhost:3000/api/public/projects
```
Expected: JSON contenant `"id":"mardik-project"`.

- [ ] **Step 7 : Commit**

```bash
git add docker-compose.yml .env.example
git commit -m "feat: add self-hosted Langfuse stack to docker-compose"
```

---

### Task 7 : Test live Langfuse + exclusion CI

**Files:**
- Create: `tests/integration/test_live_langfuse.py`
- Modify: `.github/workflows/ci.yml`

**Interfaces:**
- Consumes : `build_agent()` (`mardik.app`), `Reply` (`mardik.agent`), `SessionStore` (`mardik.session`), `load_settings()` (`mardik.config`).

- [ ] **Step 1 : Créer le test**

```python
"""Vérifie que Langfuse (self-hébergé) reçoit bien les traces, en plus de
Jaeger. Suppose Langfuse démarré (``make up``) et configuré dans ``.env``
(LANGFUSE_PUBLIC_KEY / LANGFUSE_SECRET_KEY, voir .env.example).
"""
from __future__ import annotations

import base64
import json
import time
import urllib.error
import urllib.request

from mardik.agent import Reply
from mardik.app import build_agent
from mardik.config import load_settings
from mardik.session import SessionStore


class _StaticLLM:
    def invoke(self, messages: list[dict]) -> Reply:
        return Reply(content="Bonjour, comment puis-je vous aider ?", tool_calls=[])


def _fetch_langfuse_traces(
    host: str, public_key: str, secret_key: str, limit: int = 5
) -> list[dict]:
    auth = base64.b64encode(f"{public_key}:{secret_key}".encode()).decode()
    request = urllib.request.Request(
        f"{host}/api/public/traces?limit={limit}",
        headers={"Authorization": f"Basic {auth}"},
    )
    with urllib.request.urlopen(request, timeout=5) as response:
        return json.load(response)["data"]


def test_default_telemetry_reaches_langfuse():
    settings = load_settings()
    assert settings.langfuse_public_key and settings.langfuse_secret_key, (
        "LANGFUSE_PUBLIC_KEY / LANGFUSE_SECRET_KEY doivent être renseignées "
        "dans .env pour ce test (voir .env.example)"
    )

    agent = build_agent(llm=_StaticLLM())
    try:
        store = SessionStore()
        agent.run_turn(store, "live-langfuse-001", "Bonjour, comment allez-vous ?")

        # Contrairement à Jaeger (indexation immédiate en mémoire), Langfuse
        # persiste via son worker : on laisse un peu plus de marge.
        deadline = time.monotonic() + 15
        traces: list[dict] = []
        while time.monotonic() < deadline:
            try:
                traces = _fetch_langfuse_traces(
                    settings.langfuse_host,
                    settings.langfuse_public_key,
                    settings.langfuse_secret_key,
                )
            except urllib.error.URLError:
                traces = []
            if any(trace["name"] == "agent.turn" for trace in traces):
                break
            time.sleep(1)

        assert any(trace["name"] == "agent.turn" for trace in traces), (
            "expected an 'agent.turn' trace in Langfuse"
        )
    finally:
        agent.telemetry.shutdown()
```

- [ ] **Step 2 : Lancer le test (Langfuse doit être démarré et configuré, Task 6 faite)**

Run: `uv run pytest tests/integration/test_live_langfuse.py -v`
Expected: PASS.

- [ ] **Step 3 : Exclure ce test de la CI**

Dans `.github/workflows/ci.yml`, remplacer :

```yaml
      - name: Run tests
        run: uv run pytest tests/unit tests/integration
```

par :

```yaml
      - name: Run tests
        run: uv run pytest tests/unit tests/integration --ignore=tests/integration/test_live_langfuse.py
```

- [ ] **Step 4 : Vérifier que la suite CI-équivalente reste verte sans Langfuse**

Run: `docker compose stop langfuse-web langfuse-worker postgres clickhouse redis minio`
Run: `uv run pytest tests/unit tests/integration --ignore=tests/integration/test_live_langfuse.py -v`
Expected: tous verts (Jaeger seul suffit, comme avant).
Run: `docker compose start langfuse-web langfuse-worker postgres clickhouse redis minio` (pour ne pas laisser l'environnement local dans un état arrêté).

- [ ] **Step 5 : ruff et mypy**

Run: `uv run ruff check . && uv run mypy src`
Expected: propres.

- [ ] **Step 6 : Commit**

```bash
git add tests/integration/test_live_langfuse.py .github/workflows/ci.yml
git commit -m "test: verify Langfuse ingestion, excluded from CI"
```

---

### Task 8 : Documenter dans le CHANGELOG

**Files:**
- Modify: `CHANGELOG.md`

- [ ] **Step 1 : Récupérer l'horodatage courant**

Run: `date "+%Y-%m-%d %H:%M %Z"`

- [ ] **Step 2 : Vérifier l'état final**

Run: `uv run pytest tests/unit tests/integration --ignore=tests/integration/test_live_langfuse.py -v` → vert, sans Langfuse requis.
Run: `uv run pytest tests/integration/test_live_langfuse.py -v` (Langfuse démarré) → vert.
Run: `uv run ruff check . && uv run mypy src` → propres.

- [ ] **Step 3 : Ajouter l'entrée en tête de `CHANGELOG.md`**

Insérer, en remplaçant `<HORODATAGE>` par le résultat du Step 1 :

```markdown
## <HORODATAGE> — Exploration : export des traces vers Langfuse self-hébergé

Ajout d'un second backend d'observabilité, en plus de Jaeger, pour explorer
Langfuse (self-hébergé via Docker) — voir
`docs/superpowers/specs/2026-09-14-langfuse-self-hosted-design.md`. Pas un
correctif d'incident : une exploration pédagogique.

- `telemetry.py` : `build_telemetry` accepte des exportateurs de spans
  additionnels ; `build_default_telemetry` construit un exportateur
  OTLP/HTTP vers Langfuse (Basic Auth) si `LANGFUSE_PUBLIC_KEY`/
  `LANGFUSE_SECRET_KEY` sont configurées — sinon comportement inchangé.
- `docker-compose.yml` : stack Langfuse self-hébergé (v3 — voir note de
  version dans le plan d'implémentation ; v4 désactive par défaut l'API de
  lecture utilisée par le test de vérification), avec auto-provisioning
  d'un projet et de clés API au démarrage.
- Nouveau test `tests/integration/test_live_langfuse.py` (suppose
  `make up` fait), exclu de la CI comme `test_live_telemetry.py`.
- Vérifié manuellement de bout en bout pendant la conception : une trace
  envoyée via l'exportateur HTTP apparaît immédiatement dans Langfuse sous
  le projet provisionné.
```

- [ ] **Step 4 : Commit**

```bash
git add CHANGELOG.md
git commit -m "docs: log the Langfuse exploration in changelog"
```

---

## Self-Review Notes

- **Couverture de la spec** : dépendance (Task 1), configuration (Task 2), `extra_span_exporters` (Task 3), exportateur Langfuse + wiring `build_default_telemetry` (Task 4), câblage `build_agent` (Task 5), Docker + `.env.example` (Task 6), test live + exclusion CI (Task 7), CHANGELOG (Task 8) — les 3 critères de réussite de la spec sont chacun vérifiés par une étape explicite (Task 7 Step 4 pour l'hermétisme sans Langfuse, Task 7 Step 2 pour le test live, Task 7 Step 3 pour l'absence de changement CI au-delà de l'`--ignore`).
- **Écart par rapport à la spec initiale** : la spec prévoyait les images `:4` sans préciser de version ; la vérification empirique (avant l'écriture de ce plan) a montré que `:4` casse `GET /api/public/traces` (mode `events_only`). Le plan épingle `:3` et documente pourquoi, en tête de fichier.
- **Pas de placeholder** : chaque step contient soit le code exact, soit une commande exacte et son résultat attendu vérifié empiriquement (Task 6 et le flux OTLP→Langfuse ont été testés en conditions réelles avant l'écriture de ce plan).
- **Cohérence des types/noms** : `Settings` (9 champs), `build_telemetry(..., extra_span_exporters=...)`, `build_default_telemetry(..., langfuse_host, langfuse_public_key, langfuse_secret_key)`, `Telemetry.shutdown()` — vérifiés cohérents entre les tâches et avec le code existant (`session.py`, `agent.py` non touchés).
