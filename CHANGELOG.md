# Changelog

Format : le plus récent en premier. Chaque entrée référence le test qui
spécifiait le comportement attendu.

## 2026-09-14 12:19 CEST — Correctif mypy sur _NoOpSpan.__exit__

Repéré en tâche de fond depuis la correction des incidents unitaires (mis
de côté à l'époque, hors périmètre) : `_NoOpSpan.__exit__` déclarait un
retour `bool` alors qu'il renvoie toujours `False`, ce que mypy signale
comme dangereux (`exit-return`) — un `bool` non littéral laisse penser que
le context manager pourrait avaler des exceptions. Corrigé : retour `None`.
`uv run mypy src` est maintenant propre.

## 2026-09-14 12:15 CEST — La CI démarre maintenant un vrai Jaeger

Suite à l'entrée précédente : `test_live_telemetry.py` restait exclu de la
CI faute de backend réel disponible sur le runner. Ajout d'un service
`jaeger` dans `ci.yml` (image `jaegertracing/all-in-one:1.57`, mêmes ports
et healthcheck que `docker-compose.yml`) ; GitHub Actions attend que son
healthcheck passe avant de lancer les tests. Le `--ignore` est retiré :
`uv run pytest tests/unit tests/integration` tourne désormais en entier
(20/20), y compris la vérification contre un vrai backend OTLP.

## 2026-09-14 12:12 CEST — La CI ne jouait que les tests unitaires

`.github/workflows/ci.yml` lançait `uv run pytest tests/unit` uniquement,
depuis le commit initial. Or 9 des 10 tests de `tests/integration/` sont
hermétiques (fixtures en mémoire, aucune dépendance à Docker) — la CI ne
détectait donc aucune régression sur les incidents vérifiés uniquement par
rejeu de session (perte de contexte, propagation de trace, concurrence...).

Corrigé : la CI lance désormais `tests/unit` et `tests/integration`, en
excluant explicitement `tests/integration/test_live_telemetry.py` (seul
test du dossier qui nécessite un vrai Jaeger démarré, absent en CI).

## 2026-09-14 12:06 CEST — 11ᵉ incident : service.name jamais câblé, traces invisibles sous le bon nom dans Jaeger

Trouvé en ajoutant un test contre le vrai Jaeger (`tests/integration/test_live_telemetry.py`,
suppose `make up` fait) : la trace atteignait bien Jaeger, mais sous le
service `unknown_service`, pas `mardik`. Cause racine (`telemetry.py`) :
`Settings.service_name` (lu depuis `OTEL_SERVICE_NAME`, `config.py`) n'était
jamais transmis à `TracerProvider`/`MeterProvider` — ils étaient construits
sans `resource=`, donc le SDK retombait sur son nom de service par défaut.
En pratique, dans Jaeger, Mardik était donc introuvable en cherchant "mardik".

Corrigé : `build_telemetry`/`build_default_telemetry` construisent une
`opentelemetry.sdk.resources.Resource` avec `service.name` et la passent aux
deux providers ; `build_agent` (`app.py`) transmet `settings.service_name`.
Test ajouté : `tests/unit/test_telemetry.py::test_service_name_is_set_on_spans`.

## 2026-09-14 11:49 CEST — Le chemin d'échec est désormais vérifié par rejeu de session

Ajout de `test_replay_timeout_increments_error_counter` et
`test_replay_timeout_logs_failure` (`tests/integration/test_replay.py`),
réutilisant la fixture `incident_timeout` déjà rejouée par
`test_replay_timeout_incident`. Ils prouvent que `errors_total` et le log
`turn.failed` (ajoutés dans l'entrée précédente) sont bien émis quand
l'incident se produit via le chemin réel (rejeu), pas seulement en appelant
`Agent.run_turn` directement dans un test unitaire.

Bilan : 9 des 10 incidents du journal (`livrables/journal_incidents.md`)
sont maintenant vérifiés par un test d'intégration. Le 10ᵉ (câblage
télémétrie dans `build_agent`) reste volontairement unitaire uniquement :
la télémétrie par défaut utilise un exporteur OTLP réel, le vérifier via un
rejeu complet nécessiterait une vraie connexion réseau vers un collecteur,
ce qui rendrait le test lent et fragile pour peu de valeur ajoutée.

## 2026-09-14 11:39 CEST — Instrumentation du chemin d'échec (métrique errors_total + log turn.failed)

En revue de la checklist "Instrumenter l'application (traces, métriques,
logs structurés)" du brief : le compteur `errors_total` (`telemetry.py`)
existait mais n'était jamais incrémenté, et aucun log structuré n'était émis
quand un tour échouait (seul le chemin de succès avait `turn.completed`).
Un incident réel (ex. timeout LLM) restait donc invisible côté métriques et
logs, malgré la trace (les spans OTel marquent déjà l'erreur automatiquement
sur exception non interceptée).

Corrigé (`agent.py::run_turn`) : le corps du tour est encapsulé dans un
`try/except` qui, en cas d'exception, incrémente `errors_total` (avec
`session_id` et `error.type` en attributs) et journalise un événement
`turn.failed` structuré (session_id, durée, type et message d'erreur) avant
de relever l'exception. Tests ajoutés dans `tests/unit/test_agent_errors.py` :
`test_turn_failure_increments_error_counter`, `test_turn_failure_is_logged_structured`.

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
