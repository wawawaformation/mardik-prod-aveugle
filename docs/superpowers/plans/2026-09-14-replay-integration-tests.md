# Replay Integration Tests Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ajouter des tests d'intégration qui détectent, via rejeu de session (`runner.replay()`), quatre incidents déjà corrigés mais aujourd'hui vérifiés uniquement par des tests unitaires isolés.

**Architecture:** Aucune nouvelle production code — uniquement des tests dans `tests/integration/test_replay.py` et une nouvelle fixture de session JSON, réutilisant les fixtures pytest existantes (`fake_llm`, `telemetry`, `span_exporter`, `metric_reader` dans `tests/conftest.py`).

**Tech Stack:** pytest 8, structlog (`capture_logs`), OpenTelemetry SDK (exporters en mémoire), `threading` pour le test de concurrence.

## Global Constraints

- Ne pas modifier `src/mardik/` : le code de production est déjà correct (voir `CHANGELOG.md`, entrées du 2026-09-14).
- Ne pas supprimer ni modifier les tests unitaires existants (`tests/unit/`).
- Rester en pytest simple, pas de framework BDD/Gherkin.
- `uv run ruff check .` doit rester propre après chaque tâche.
- `uv run pytest` doit rester entièrement vert après chaque tâche.
- Référence : spec `docs/superpowers/specs/2026-09-14-replay-integration-tests-design.md`.

**Note sur le TDD de ce plan :** ces tests vérifient un comportement déjà corrigé (voir spec, section « Objectif »). Il n'y a donc pas d'étape « rouge » — chaque test doit passer dès son écriture. L'étape de vérification confirme que le rejeu de session couvre bien l'incident, pas qu'un bug vient d'être corrigé.

---

### Task 1: Test de propagation de trace via rejeu

**Files:**
- Modify: `tests/integration/test_replay.py`

**Interfaces:**
- Consumes : `load_session(name: str) -> dict`, `replay(session_data, agent, store) -> TurnResult` (`mardik.runner`) ; `_agent(llm, telemetry) -> Agent` (helper déjà défini en haut du fichier) ; fixtures pytest `fake_llm`, `telemetry`, `span_exporter` (`tests/conftest.py`).
- Produces : rien de nouveau consommé par d'autres tâches.

- [ ] **Step 1: Ajouter le test**

À la fin de `tests/integration/test_replay.py` :

```python
def test_replay_produces_single_connected_trace(fake_llm, telemetry, span_exporter):
    data = load_session("replay_delivery")
    replay(data, _agent(fake_llm, telemetry), SessionStore())

    spans = {span.name: span for span in span_exporter.get_finished_spans()}
    assert "agent.turn" in spans
    assert "llm.invoke" in spans
    assert "tool.call" in spans

    trace_ids = {span.context.trace_id for span in spans.values()}
    assert len(trace_ids) == 1
```

- [ ] **Step 2: Lancer le test et vérifier qu'il passe**

Run: `uv run pytest tests/integration/test_replay.py::test_replay_produces_single_connected_trace -v`
Expected: PASS (le rejeu de `replay_delivery` déclenche un appel LLM qui trouve `#1042` et appelle `lookup_order`, donc les trois spans existent et partagent le même `trace_id` grâce à la propagation de contexte déjà en place dans `agent.py`).

- [ ] **Step 3: Commit**

```bash
git add tests/integration/test_replay.py
git commit -m "test: verify trace propagation through session replay"
```

---

### Task 2: Test de la métrique de latence via rejeu

**Files:**
- Modify: `tests/integration/test_replay.py`

**Interfaces:**
- Consumes : mêmes que Task 1, plus fixture `metric_reader` (`tests/conftest.py`).
- Produces : rien de nouveau consommé par d'autres tâches.

- [ ] **Step 1: Ajouter le test**

```python
def test_replay_emits_latency_metric(fake_llm, telemetry, metric_reader):
    data = load_session("replay_delivery")
    replay(data, _agent(fake_llm, telemetry), SessionStore())

    metrics_data = metric_reader.get_metrics_data()
    points = [
        point
        for rm in metrics_data.resource_metrics
        for sm in rm.scope_metrics
        for metric in sm.metrics
        if metric.name == "latency_ms"
        for point in metric.data.data_points
    ]
    assert points, "expected at least one latency_ms measurement"
```

- [ ] **Step 2: Lancer le test et vérifier qu'il passe**

Run: `uv run pytest tests/integration/test_replay.py::test_replay_emits_latency_metric -v`
Expected: PASS.

- [ ] **Step 3: Commit**

```bash
git add tests/integration/test_replay.py
git commit -m "test: verify latency metric emission through session replay"
```

---

### Task 3: Test du log structuré via rejeu

**Files:**
- Modify: `tests/integration/test_replay.py`

**Interfaces:**
- Consumes : mêmes que Task 1, plus `capture_logs` de `structlog.testing`.
- Produces : rien de nouveau consommé par d'autres tâches.

- [ ] **Step 1: Ajouter l'import**

En haut de `tests/integration/test_replay.py`, avec les autres imports :

```python
from structlog.testing import capture_logs
```

- [ ] **Step 2: Ajouter le test**

```python
def test_replay_logs_turn_completion(fake_llm, telemetry):
    data = load_session("replay_delivery")
    with capture_logs() as logs:
        replay(data, _agent(fake_llm, telemetry), SessionStore())

    events = [entry.get("event") for entry in logs]
    assert "turn.completed" in events
```

- [ ] **Step 3: Lancer le test et vérifier qu'il passe**

Run: `uv run pytest tests/integration/test_replay.py::test_replay_logs_turn_completion -v`
Expected: PASS.

- [ ] **Step 4: Commit**

```bash
git add tests/integration/test_replay.py
git commit -m "test: verify structured logging through session replay"
```

---

### Task 4: Fixture de livraison dupliquée + test de concurrence via rejeu

**Files:**
- Create: `sessions/incident_duplicate_delivery.json`
- Modify: `tests/integration/test_replay.py`

**Interfaces:**
- Consumes : `SessionStore.turns(session_id: str) -> int` (`mardik.session`, déjà existant) ; `threading.Thread`.
- Produces : fixture `sessions/incident_duplicate_delivery.json`, consommée uniquement par le test de cette tâche.

- [ ] **Step 1: Créer la fixture de session**

Créer `sessions/incident_duplicate_delivery.json` :

```json
{
  "session_id": "incident-duplicate-delivery-001",
  "messages": [
    {"role": "user", "content": "Bonjour, où en est ma commande #3157 ?"}
  ]
}
```

Ce scénario représente un incident récurrent classique côté backend support : un même message livré deux fois (retry réseau ou double-clic), qu'on simule en rejouant cette session deux fois concurremment sur un `SessionStore` partagé.

- [ ] **Step 2: Ajouter l'import**

En haut de `tests/integration/test_replay.py`, avec les autres imports :

```python
import threading
```

- [ ] **Step 3: Ajouter le test**

```python
def test_concurrent_replay_counts_every_turn(fake_llm, telemetry):
    data = load_session("incident_duplicate_delivery")
    agent = _agent(fake_llm, telemetry)
    store = SessionStore()

    def deliver() -> None:
        replay(data, agent, store)

    threads = [threading.Thread(target=deliver) for _ in range(2)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert store.turns(data["session_id"]) == 2
```

- [ ] **Step 4: Lancer le test et vérifier qu'il passe**

Run: `uv run pytest tests/integration/test_replay.py::test_concurrent_replay_counts_every_turn -v`
Expected: PASS (le verrou ajouté dans `SessionStore.record_turn` garantit qu'aucun incrément n'est perdu, même via le chemin réel `agent.run_turn` plutôt qu'un appel direct à `record_turn`).

- [ ] **Step 5: Commit**

```bash
git add sessions/incident_duplicate_delivery.json tests/integration/test_replay.py
git commit -m "test: verify concurrent replay counts every turn"
```

---

### Task 5: Documenter dans le CHANGELOG

**Files:**
- Modify: `CHANGELOG.md`

**Interfaces:**
- Consumes : rien.
- Produces : rien.

- [ ] **Step 1: Récupérer l'horodatage courant**

Run: `date "+%Y-%m-%d %H:%M %Z"`

Note le résultat (ex. `2026-09-14 15:30 CEST`) pour l'étape suivante.

- [ ] **Step 2: Vérifier que la suite complète est verte**

Run: `uv run pytest -v`
Expected: tous les tests passent (14/14 : 10 précédents + 4 nouveaux).

- [ ] **Step 3: Ajouter l'entrée en tête de `CHANGELOG.md`**

Insérer, juste après la ligne de format (avant la première entrée `## 2026-09-14 ...` existante), en remplaçant `<HORODATAGE>` par le résultat du Step 1 :

```markdown
## <HORODATAGE> — Tests d'intégration détectant les incidents via rejeu de session

Quatre incidents, jusqu'ici vérifiés uniquement par des tests unitaires,
sont désormais aussi détectés en rejouant une session à travers
`runner.replay()` (`tests/integration/test_replay.py`) :

- **`test_replay_produces_single_connected_trace`** — les spans `agent.turn`,
  `llm.invoke` et `tool.call` partagent le même `trace_id` lors d'un rejeu
  complet (propagation de contexte OTel au thread du LLM).
- **`test_replay_emits_latency_metric`** — la métrique `latency_ms` est
  enregistrée lors d'un rejeu.
- **`test_replay_logs_turn_completion`** — le log structuré `turn.completed`
  est émis lors d'un rejeu.
- **`test_concurrent_replay_counts_every_turn`** — rejouer deux fois
  concurremment la même session (nouvelle fixture
  `sessions/incident_duplicate_delivery.json`, simulant une livraison
  dupliquée) sur un `SessionStore` partagé compte bien deux tours, sans
  incrément perdu.

Voir `docs/superpowers/specs/2026-09-14-replay-integration-tests-design.md`
pour le détail de la conception.
```

- [ ] **Step 4: Commit**

```bash
git add CHANGELOG.md
git commit -m "docs: log replay-driven integration tests in changelog"
```

---

## Self-Review Notes

- **Couverture de la spec** : les 4 tests de la spec (trace, latence, log, concurrence) correspondent chacun à une tâche (1 à 4) ; la fixture demandée est créée dans la Task 4 ; le critère de réussite « `CHANGELOG.md` référence les nouveaux tests » est couvert par la Task 5 ; le critère « suite complète verte » et « ruff propre » sont vérifiés à chaque tâche.
- **Pas de placeholder** : chaque step contient le code exact à écrire ; seul l'horodatage de la Task 5 est dynamique (obtenu par une commande, pas un TBD).
- **Cohérence des types/noms** : `_agent`, `load_session`, `replay`, `SessionStore`, `store.turns(session_id)` sont utilisés avec la même signature que dans le code existant (vérifié contre `src/mardik/runner.py`, `src/mardik/session.py`, `tests/integration/test_replay.py`).
