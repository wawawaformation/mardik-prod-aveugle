---
title: "Étape 1 — Test d'intégration vs unitaire, et observer une application IA"
metadata:
  duree_cible: "1 min 45"
  images:
    - q1a_perimetre_tests_agent.png
    - q1b_observer_application_ia.png
  source: "Testing Pyramid for AI Agents — Block Engineering Blog"
---

## Question du brief

> Qu'est-ce qu'un test d'intégration pour un agent (vs unitaire), et que veut dire observer une application IA ?

## Message clé

Un test unitaire ne voit qu'une brique ; un test d'intégration rejoue une session réelle. Observer, c'est reconstituer *comment* une réponse a été produite, pas seulement *si* le serveur a répondu.

## Ce qu'il faut dire

- Test unitaire = provider LLM mocké sur une brique isolée. Test d'intégration = toute la chaîne — mais le LLM est non déterministe.
- La solution vient de Block Engineering : **enregistrer une session réelle une fois, la rejouer** ensuite de façon déterministe. On renonce à tester les améliorations du modèle, on gagne la détection de régression sur le code.
- Observer : à gauche, la boîte noire — HTTP 200 ne garantit pas une réponse juste. À droite, la même requête en arbre de spans, où l'étape fautive devient visible.

## Transition

Observer suppose de savoir quoi mesurer.
