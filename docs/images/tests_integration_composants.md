# Fiche de lecture — Tests d'intégration : composants en jeu

**Schéma :** [`tests_integration_composants.drawio`](tests_integration_composants.drawio) / [`.png`](tests_integration_composants.png)

## Objectif de lecture

Pour chaque famille de tests de `tests/integration/`, savoir quelles
fixtures sont assemblées (LLM factice, session JSON, store, télémétrie) et
ce que chaque test vérifie précisément.

## Ce qu'on voit

Quatre familles, chacune avec son en-tête (composants partagés) puis la
liste de ses tests avec l'assertion spécifique de chacun :

1. **Chemin de succès** — `fake_llm` + `replay_delivery.json` (5 tests) ;
2. **Chemin d'échec** — `timeout_llm` + `incident_timeout.json` (3 tests) ;
3. **Concurrence** — `fake_llm` + `incident_duplicate_delivery.json`,
   2 threads sur un store partagé (1 test) ;
4. **Backend réel** — `build_agent()` sans fixture, contre un vrai Jaeger
   (1 test).

## Points clés à retenir

- **9 des 10 tests sont hermétiques** (fixtures en mémoire) : ils tournent
  en CI sans Docker.
- Seul le test « backend réel » nécessite Jaeger démarré — c'est pour ça
  qu'un service Jaeger a été ajouté à `ci.yml` plutôt que de l'exclure.
- Le regroupement par famille (plutôt qu'un flux par test) évite 10
  diagrammes redondants pour une info qui se lit mieux en tableau de
  composants.

## Voir aussi

- `tests/integration/test_replay.py`, `tests/integration/test_live_telemetry.py`
- `.github/workflows/ci.yml`
- `CHANGELOG.md` (entrées CI du 2026-09-14 12:12 et 12:15)
