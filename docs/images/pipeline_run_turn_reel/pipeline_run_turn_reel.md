# Fiche de lecture — Pipeline d'un tour de conversation (état réel)

**Schéma :** [`pipeline_run_turn_reel.drawio`](pipeline_run_turn_reel.drawio) / [`.png`](pipeline_run_turn_reel.png)

## Objectif de lecture

Suivre le déroulement effectif de `Agent.run_turn()` et repérer les points
où l'instrumentation annoncée par le README ne correspondait pas au code —
**avant** les correctifs de la session du 2026-09-14.

## Ce qu'on voit

Un flux séquentiel : ouverture du span `agent.turn` → stockage du message →
`record_turn()` → appel LLM dans un thread worker (span `llm.invoke`) →
branche timeout → branche appel d'outil → stockage de la réponse → sortie.
Cinq encarts rouges pointillés annotent, à l'endroit exact où ils se
produisent, les points de défaillance observés.

## Points clés à retenir

- Le thread worker qui appelle le LLM ne propageait pas le contexte OTel :
  le span `llm.invoke` démarrait sa propre trace, déconnectée de `agent.turn`.
- Un `TimeoutError` était avalé (`return None`) au lieu d'être relevé comme
  erreur métier — crash `AttributeError` plus loin dans le flux.
- `_dispatch_tool` n'ouvrait aucun span : les appels d'outils étaient
  invisibles dans les traces.
- La sortie utilisait `print()` et n'enregistrait aucune métrique de
  latence.
- `record_turn()` avait une race condition classique (lecture-sleep-écriture
  sans verrou).

## Statut

**Historique.** Les 5 points annotés ont tous été corrigés (voir
`CHANGELOG.md`, entrées du 2026-09-14 10:44 et 11:49). Le schéma garde sa
valeur pédagogique : il montre *pourquoi* chaque correctif était nécessaire,
pas l'état actuel du code.

## Voir aussi

- `src/mardik/agent.py`, `src/mardik/session.py`
- `docs/comprendre_le_code.md`
- `livrables/journal_incidents.md` (incidents #1, #3, #4, #5, #6, #7)
