---
title: "Q3 — Les points à instrumenter pour rendre une trace exploitable"
metadata:
  duree_cible: "2 min"
  images:
    - q3_points_instrumentation.png
---

## Question du brief

> Quels points instrumenter pour rendre une trace exploitable ?

## Message clé

Une requête utilisateur doit produire une trace unique et connexe, du client jusqu'au dernier appel externe. Sans propagation du contexte de trace, l'arbre se fragmente et perd toute valeur diagnostique.

## Ce qu'il faut dire

- Suivre le flux sur le schéma, de haut en bas : Client → API Gateway (span racine, avec `trace_id`) → Orchestrateur d'agent → trois branches parallèles (Retrieval, LLM, Outils) → Collecte.
- Insister sur un point différenciant : le **span racine** porte le `trace_id` ; le **span d'orchestration** porte les **versions** (modèle, prompt, config) — c'est ce qui permet de relier un incident à une release précise.
- Trois conventions à citer rapidement : nommer les spans explicitement (pas `tool_call` générique), séparer modèle / outils / état, et instrumenter dès le départ plutôt qu'après l'incident.
- Terminer sur l'encadré rouge : le rejeu de sessions réelles implique de stocker des prompts réels — anonymisation obligatoire à l'enregistrement, sinon le dispositif de test devient lui-même un problème de conformité.

## Transition vers Q4

Une fois la trace en place, reste à savoir comment l'exploiter quand un test échoue.
