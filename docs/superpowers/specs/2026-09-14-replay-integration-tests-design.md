# Renforcer les tests d'intégration par rejeu de session

Date : 2026-09-14
Statut : approuvé

## Contexte

Le dépôt `mardik-prod-aveugle` contenait, dès le départ, 9 incidents
d'observabilité et de concurrence, révélés par la suite de tests fournie
(voir `CHANGELOG.md`). Tous ont été corrigés :

- 7 ont été détectés et vérifiés par des **tests unitaires**
  (`tests/unit/`), en appelant directement `Agent.run_turn` ou
  `SessionStore.record_turn`.
- 2 ont été détectés et vérifiés par des **tests d'intégration**
  (`tests/integration/test_replay.py`), en rejouant une session enregistrée
  via `runner.replay()`.

Le brief demande explicitement, dans sa partie « Développement » :

> - Écrire des tests d'intégration rejouant des sessions réelles.
> - Diagnostiquer et corriger au moins deux incidents récurrents.
> - Vérifier que les tests d'intégration détectent désormais ces incidents.

Les tests unitaires suffisent à documenter le comportement de chaque brique
isolée, mais ne prouvent pas que le pipeline complet (agent + télémétrie +
store partagé), rejoué dans des conditions proches du réel, se comporte
correctement de bout en bout. C'est cette preuve qui manque aujourd'hui.

## Objectif

Ajouter des tests d'intégration qui, en rejouant une session, détectent
spécifiquement les incidents suivants (déjà corrigés dans le code, donc ces
tests seront verts dès leur écriture — ils servent de filet de
non-régression réaliste, pas de nouveaux correctifs) :

1. propagation du contexte de trace OpenTelemetry au thread du LLM ;
2. émission de la métrique de latence ;
3. émission du log structuré de fin de tour ;
4. absence de race condition dans le compteur de tours sous rejeu concurrent.

## Non-objectifs

- Ne pas modifier le code de production (`src/mardik/`) : il est déjà
  correct, validé par les tests unitaires existants.
- Ne pas dupliquer un test unitaire existant à l'identique dans
  `tests/integration/` — chaque nouveau test doit apporter une preuve que
  seul le chemin de rejeu peut apporter (contexte partagé, thread réel,
  concurrence sur un store partagé).
- Ne pas introduire de framework BDD/Gherkin : la suite existante est en
  pytest simple, on reste cohérent avec l'existant.
- Ne pas retirer les tests unitaires existants : la pyramide de tests
  (unitaire → intégration) reste telle quelle.

## Conception

### Nouvelle fixture de session

`sessions/incident_duplicate_delivery.json` — scénario réaliste d'un
incident récurrent de support client : un message utilisateur livré deux
fois au backend (retry réseau ou double-clic), qui doit être traité comme
deux tours distincts sans perte d'incrément. Même structure que les fixtures
existantes (`session_id`, liste de `messages`).

### Nouveaux tests — `tests/integration/test_replay.py`

Chaque test utilise les fixtures déjà disponibles dans `conftest.py`
(`fake_llm`, `telemetry`, `span_exporter`, `metric_reader`) et passe par
`runner.replay()`, jamais par `Agent.run_turn()` directement — c'est le
chemin réellement executé en production (rejeu = requête utilisateur).

| Test | Fixture de session | Assertion | Incident couvert |
|---|---|---|---|
| `test_replay_produces_single_connected_trace` | `replay_delivery` | les spans `agent.turn`, `llm.invoke`, `tool.call` partagent le même `trace_id` | propagation de contexte OTel au thread worker du LLM |
| `test_replay_emits_latency_metric` | `replay_delivery` | un point de données `latency_ms` est présent après le rejeu | métrique de latence jamais enregistrée |
| `test_replay_logs_turn_completion` | `replay_delivery` | l'événement de log structuré `turn.completed` est émis | `print()` utilisé à la place d'un log structuré |
| `test_concurrent_replay_counts_every_turn` | `incident_duplicate_delivery` | rejouer la même session deux fois concurremment sur un `SessionStore` partagé aboutit à `store.turns(session_id) == 2` | race condition dans `SessionStore.record_turn` |

**Regroupement des assertions** : le trace_id partagé entre les trois spans
est vérifié dans un seul test (ils dépendent du même mécanisme de
propagation de contexte). La métrique de latence et le log structuré restent
dans des tests séparés : ce sont deux signaux indépendants, et une
régression sur l'un ne doit pas masquer une régression sur l'autre.

### Test de concurrence — détail

Contrairement au test unitaire existant (`test_record_turn_counts_every_concurrent_turn`,
qui appelle directement `store.record_turn()` 1000 fois pour maximiser la
détection de la race condition), ce test d'intégration reste volontairement
réaliste : deux threads appellent chacun `runner.replay()` avec la même
`session_data` et le même `SessionStore` (`threading.Thread` + `join()`,
comme dans le test unitaire), simulant une livraison dupliquée d'un même
message. Il ne remplace pas le test unitaire (qui reste la
meilleure preuve statistique de l'absence de race condition sous charge) ;
il prouve que le chemin réel (agent + store) se comporte correctement dans
un scénario plausible.

## Critères de réussite

- Les 4 nouveaux tests passent (`uv run pytest tests/integration/ -v`).
- La suite complète reste verte (`uv run pytest`).
- `ruff check .` ne signale rien de nouveau.
- `CHANGELOG.md` référence les nouveaux tests et la fixture ajoutée.
