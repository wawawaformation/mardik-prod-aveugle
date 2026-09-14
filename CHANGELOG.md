# Changelog

Format : le plus récent en premier. Chaque entrée référence le test qui
spécifiait le comportement attendu.

## 2026-09-14 11:32 CEST — Tests d'intégration détectant les incidents via rejeu de session

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

## 2026-09-14 10:52 CEST — Correction des 2 incidents révélés par les tests d'intégration

Tous les tests passent désormais (`uv run pytest` → 10/10).

- **`test_replay_preserves_session_context`** — `runner.replay` (`runner.py`)
  n'envoyait au agent que le dernier message du fichier de session, en
  ignorant tous les tours précédents enregistrés : l'agent répondait comme
  s'il découvrait la conversation, perdant le contexte (ex. le numéro de
  commande donné plus tôt). Corrigé : `replay` précharge désormais tous les
  messages sauf le dernier dans le `SessionStore` avant de rejouer le tour
  final, pour que l'historique complet soit transmis au LLM.

- **`test_replay_timeout_incident`** — la fixture `sessions/incident_timeout.json`
  attendue par le test n'existait pas (`FileNotFoundError`). Ajoutée : une
  session de rejeu représentant un incident de timeout récurrent (relance
  utilisateur après une réponse qui ne vient pas).

## 2026-09-14 10:44 CEST — Correction des 7 incidents révélés par les tests unitaires

Tous les tests de `tests/unit/` passent désormais (`uv run pytest tests/unit/`).
Les tests d'intégration (`tests/integration/test_replay.py`) restent rouges,
traités séparément.

- **`test_build_agent_wires_telemetry`** — `build_agent` (`app.py`) construisait
  toujours l'agent sans télémétrie réelle : le paramètre `telemetry` n'était
  jamais transmis à `Agent(...)`. Corrigé : `build_agent` construit une
  `Telemetry` par défaut via `build_default_telemetry` quand aucune n'est
  fournie, et la transmet à `Agent`.

- **`test_record_turn_counts_every_concurrent_turn`** — `SessionStore.record_turn`
  (`session.py`) lisait puis écrivait le compteur en deux temps séparés par un
  `sleep`, sans verrou : sous appels concurrents sur la même session, des
  incréments étaient perdus (race condition classique lecture-modification-écriture).
  Corrigé : ajout d'un `threading.Lock` protégeant la séquence.

- **`test_trace_context_propagated_across_threads`** — le span `llm.invoke`
  s'ouvrait dans un thread worker séparé (`agent.py::_invoke_llm`) sans
  propagation du contexte OpenTelemetry : il démarrait son propre `trace_id`,
  déconnecté du span `agent.turn` parent. Corrigé : le contexte courant est
  capturé avant `thread.start()` puis attaché explicitement dans le worker
  (`opentelemetry.context.attach`/`detach`).

- **`test_turn_completion_is_logged_structured`** — la fin d'un tour était
  journalisée via `print()` au lieu d'un log structuré. Corrigé : remplacé par
  `self.telemetry.logger.info("turn.completed", ...)`.

- **`test_latency_metric_emitted`** — l'instrument `latency_ms` existait
  (`telemetry.py`) mais n'était jamais alimenté. Corrigé : `run_turn` appelle
  `self.telemetry.record_latency(elapsed_ms, session_id=...)` en fin de tour.

- **`test_tool_call_is_traced`** — `_dispatch_tool` (`agent.py`) n'ouvrait
  aucun span : les appels d'outils étaient invisibles dans les traces.
  Corrigé : ouverture d'un span `tool.call` autour de l'exécution de l'outil.

- **`test_llm_timeout_surfaces_as_domain_error`** — un `TimeoutError` levé par
  le LLM était transformé en `None`, ce qui provoquait un `AttributeError`
  (`reply.content` sur `None`) plus loin dans `run_turn`, au lieu d'une erreur
  métier explicite. Corrigé : `_invoke_llm_sync` lève désormais
  `LLMTimeoutError` (déjà définie dans `errors.py` mais jamais utilisée), et le
  thread worker capture toute exception pour la relever dans le thread
  appelant (une exception levée dans un thread Python ne se propage pas
  automatiquement à l'appelant).

## En cours — Tests d'intégration restants

- [ ] `test_replay_timeout_incident` — fixture `sessions/incident_timeout.json`
      manquante.
- [ ] `test_replay_preserves_session_context` — `runner.replay` ne rejoue que
      le dernier message du fichier de session, perdant le contexte des tours
      précédents.
