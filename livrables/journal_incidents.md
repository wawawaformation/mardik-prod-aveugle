# Journal des incidents résolus

Détail complet (cause + correctif) dans `CHANGELOG.md`. Ici : vue de synthèse.

| # | Incident | Cause racine | Correctif | Détecté par |
|---|---|---|---|---|
| 1 | Timeout LLM → crash `AttributeError` | `TimeoutError` transformé en `None` au lieu d'être relevé | `agent.py` lève `LLMTimeoutError` | unitaire + intégration |
| 2 | Rejeu de session perdant le contexte | `runner.replay` n'envoyait que le dernier message | préchargement de l'historique avant rejeu | intégration |
| 3 | Race condition sur le compteur de tours | lecture/écriture non atomique dans `record_turn` | `threading.Lock` | unitaire + intégration |
| 4 | Trace coupée entre `agent.turn` et `llm.invoke` | contexte OTel non propagé au thread worker | `context.attach`/`detach` dans le thread | unitaire + intégration |
| 5 | Log de fin de tour non structuré | `print()` au lieu du logger | `telemetry.logger.info("turn.completed", ...)` | unitaire + intégration |
| 6 | Métrique de latence jamais enregistrée | `record_latency` jamais appelé | appel en fin de `run_turn` | unitaire + intégration |
| 7 | Appels d'outils invisibles dans les traces | `_dispatch_tool` sans span | span `tool.call` ajouté | unitaire + intégration |
| 8 | Télémétrie jamais câblée en prod | `build_agent` ignorait le paramètre `telemetry` | télémétrie par défaut construite et transmise | unitaire |
| 9 | Fixture de session manquante | `sessions/incident_timeout.json` absent | fixture ajoutée | intégration |
| 10 | Chemin d'échec invisible | `errors_total` jamais incrémenté, pas de log d'erreur | métrique `errors_total` + log `turn.failed` | unitaire + intégration |
| 11 | Traces invisibles sous le bon nom dans Jaeger | `service.name` jamais câblé dans la `Resource` OTel | `Resource(service.name=...)` transmise aux providers | intégration (contre Jaeger réel) |
| 12 | Le LLM de production n'a jamais fonctionné | `get_llm` utilisait le client Azure AI Inference natif, alors que l'endpoint est compatible OpenAI | `langchain_openai.ChatOpenAI` avec `base_url` | unitaire + appel réel de bout en bout |

**12 incidents corrigés**, suite complète verte (`uv run pytest` → 28/28 sans
Langfuse/Jaeger requis). 10 des 12 sont vérifiés par un test d'intégration ; #8
(câblage télémétrie de `build_agent`) et #12 (client LLM) restent unitaires,
ce dernier vérifié en plus par un vrai appel de bout en bout. Les incidents
#11 et #12 ont tous deux été trouvés en testant contre de vrais services
plutôt qu'avec des mocks — preuve que ce type de vérification a une valeur
que les tests hermétiques n'ont pas.
