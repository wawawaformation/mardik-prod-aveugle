# Changelog

Format : le plus récent en premier. Chaque entrée référence le test qui
spécifiait le comportement attendu.

## 2026-09-14 15:20 CEST — Contenu (prompt/réponse) visible dans Langfuse

Suite à l'enrichissement des attributs (entrée précédente) : Langfuse
affichait bien `session.id` et le type d'observation, mais signalait
*"this trace didn't receive an input or output"* — les spans ne portaient
que des métadonnées, jamais le texte réel de la conversation.

Ajouté (`agent.py`), vérifié contre la doc Langfuse
(`property-mapping` : `langfuse.observation.input`/`.output`, string ou
JSON string) : `agent.turn` porte le message utilisateur en entrée et la
réponse finale en sortie ; `llm.invoke` porte l'historique complet envoyé
au LLM (JSON) et le contenu brut de la réponse ; `tool.call` porte les
arguments de l'outil (JSON) et son résultat. Test ajouté :
`test_agent_observability.py::test_spans_carry_input_and_output`. Vérifié
en direct : la trace Langfuse affiche maintenant le vrai prompt et la
vraie réponse.

**Compromis assumé** : contrairement à la recommandation de confidentialité
notée dans le schéma de conception préliminaire (privilégier les
métadonnées aux données brutes), on envoie ici le contenu complet vers un
service tiers self-hébergé — acceptable pour une démo avec des données de
test, à reconsidérer avant tout usage avec de vraies données client.

## 2026-09-14 15:00 CEST — Spans enrichis d'attributs métier (session, modèle, tokens, outil)

Suite à une question sur l'écart Jaeger/Langfuse (`docs/images/traces_jaeger_langfuse_parallele/`) :
les 3 spans (`agent.turn`, `llm.invoke`, `tool.call`) ne portaient aucun
attribut personnalisé, notées "non fait" dans
`docs/images/pipeline_observabilite_mardik/pipeline_observabilite_mardik.md`.
Les deux backends affichaient donc le même waterfall générique — aucune des
vues spécifiques LLM de Langfuse (coût, tokens, regroupement par session)
ne pouvait s'activer.

Corrigé (`agent.py`) : chaque span porte désormais `session.id` et
`langfuse.observation.type` (`agent`/`generation`/`tool` — clé documentée
par Langfuse pour router un span vers ses vues dédiées, plutôt qu'un
attribut ad-hoc). `llm.invoke` ajoute en plus `gen_ai.system`,
`gen_ai.request.model` et `gen_ai.usage.{input,output}_tokens` (lus depuis
`response_metadata`/`usage_metadata` du `AIMessage` réel de `ChatOpenAI` —
absents du `Reply` factice utilisé par les tests, d'où un accès défensif).
`tool.call` ajoute `tool.name`. Noms d'attributs vérifiés contre la doc
Langfuse OTel (`integrations/native/opentelemetry.md`), pas de mémoire.
`session_id` est désormais transmis à `_invoke_llm`/`_invoke_llm_sync`/
`_dispatch_tool` pour pouvoir le poser sur chaque span, pas seulement le
span racine. Test ajouté :
`tests/unit/test_agent_observability.py::test_spans_carry_langfuse_and_session_attributes`.
Jaeger affichera ces clés comme attributs plats (pas de changement de vue) ;
Langfuse les interprète pour ses vues dédiées.

## 2026-09-14 14:48 CEST — 12ᵉ incident : le LLM de prod n'a jamais fonctionné

Repéré en testant le LLM réel pour la démo (jamais exercé jusqu'ici — tous
les tests utilisent un LLM factice) : `uv run python -m mardik.app` plantait
avec `azure.core.exceptions.HttpResponseError: (BadRequest) API version not
supported`. Cause racine (`llm.py::get_llm`) : le code utilisait
`AzureAIChatCompletionsModel` (protocole natif Azure AI Inference), alors
que l'endpoint configuré (`.../openai/v1`) est une route **compatible
OpenAI** — mauvais client, pas un problème de clé ou de quota. Vérifié en
appelant l'endpoint directement avec le SDK `openai` : réponse correcte.

Corrigé : `get_llm` utilise désormais `langchain_openai.ChatOpenAI` avec
`base_url` pointé sur l'endpoint Azure. Dépendance `langchain-azure-ai`
retirée (devenue inutile), `langchain-openai` ajoutée. Test ajouté :
`tests/unit/test_llm.py::test_get_llm_targets_the_configured_openai_compatible_endpoint`.
Vérifié de bout en bout avec un vrai appel : réponse reçue, log
`turn.completed` émis, métrique `latency_ms` enregistrée, trace remontée
dans Jaeger — le premier appel LLM réel de tout le projet a fonctionné.

## 2026-09-14 13:32 CEST — .env chargé automatiquement (python-dotenv)

Repéré juste après l'ajout de Langfuse : `.env` n'était jamais chargé par
rien dans le projet (ni `uv run`, ni le code) — il fallait le `source .env`
à la main dans chaque shell, sans quoi `load_settings()` retombait sur les
valeurs par défaut (vides pour les clés Langfuse), silencieusement.

Corrigé : `config.py` appelle `load_dotenv()` (paquet `python-dotenv`) une
fois à l'import du module. N'écrase jamais une variable déjà présente dans
l'environnement réel (CI, conteneur) — `.env` ne fournit que des valeurs
par défaut locales. Vérifié depuis un shell totalement vierge (`env -i`) :
`tests/integration/test_live_langfuse.py` passe désormais sans sourcing
manuel, et `test_load_settings_defaults_langfuse_to_disabled` (qui dépend
de `monkeypatch.delenv`) continue de passer.

## 2026-09-14 13:28 CEST — Exploration : export des traces vers Langfuse self-hébergé

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

## 2026-09-14 12:26 CEST — Bruit en fin de suite : MeterProvider jamais arrêté

Repéré dans les logs de la CI (visible aussi en local) : un traceback
`Exception while exporting metrics ... I/O operation on closed file`
apparaissait après le « 21 passed ». Cause : `build_default_telemetry`
(utilisé par `test_default_telemetry_reaches_jaeger`) construit un
`MeterProvider` avec un `PeriodicExportingMetricReader` — thread de fond
jamais arrêté, qui tente d'exporter vers stdout après la fermeture de ce
flux par pytest. Les autres tests ne sont pas concernés : ils utilisent
`InMemoryMetricReader`, sans thread d'export réel.

Corrigé : `Telemetry` garde une référence aux providers et expose
`shutdown()` (`telemetry.py`) ; `test_live_telemetry.py` l'appelle dans un
`finally`. Test ajouté :
`test_telemetry.py::test_shutdown_stops_tracer_and_meter_providers`.

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
