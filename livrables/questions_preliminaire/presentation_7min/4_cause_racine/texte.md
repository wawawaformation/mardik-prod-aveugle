---
title: "Étape 4 — Relier un test d'intégration échoué à sa cause via les traces"
metadata:
  duree_cible: "1 min 45"
  images:
    - q4_test_echoue_vers_cause.png
  source: "How to trace an LLM failure back to its root cause — Braintrust"
---

## Question du brief

> Comment relier un test d'intégration échoué à une cause via les traces ?

## Message clé

Un « assertion failed » ne fait pas progresser le diagnostic. Le lanceur de tests doit journaliser le `trace_id` de chaque requête — c'est la précondition de tout le reste.

## Ce qu'il faut dire

- Méthode en 4 étapes (Braintrust) : **1.** localiser la trace par `trace_id` ; **2.** parcourir l'arbre de spans dans l'ordre, en comparant chaque sortie à ce qu'elle aurait dû produire — pas seulement la réponse finale ; **3.** isoler la couche fautive (récupération, prompt, outil, modèle) ; **4.** corriger, rejouer, et promouvoir la trace en test de non-régression.
- L'étape 2 est celle qui distingue cette méthode d'un débogage classique : elle tranche entre 4 causes possibles que la seule réponse finale rend indiscernables.
- Un incident diagnostiqué mais non converti en test rejouable reviendra — c'est la réponse directe au symptôme du brief.

## Clôture

Test qui échoue → trace qui explique → correctif qui se vérifie : c'est cette boucle complète qui rend une application diagnosticable. Merci.
