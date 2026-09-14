---
title: "Q4 — Relier un test d'intégration échoué à sa cause via les traces"
metadata:
  duree_cible: "2 min"
  images:
    - q4_test_echoue_vers_cause.png
---

## Question du brief

> Comment relier un test d'intégration échoué à une cause via les traces ?

## Message clé

Un « assertion failed » ne fait pas progresser le diagnostic. Le lanceur de tests doit journaliser le `trace_id` de chaque requête — c'est la précondition de tout le reste.

## Ce qu'il faut dire

- Suivre le logigramme en 4 étapes :
  1. **Localiser la trace**, par `trace_id` ou par filtrage.
  2. **Parcourir l'arbre de spans dans l'ordre**, en comparant chaque sortie à ce qu'elle aurait dû produire — pas seulement la réponse finale.
  3. **Isoler la couche fautive** : récupération, prompt, outil ou modèle.
  4. **Corriger, rejouer, et promouvoir la trace en test de non-régression.**
- Point clé à souligner : c'est l'étape 2 qui distingue cette méthode d'un débogage classique — elle permet de trancher entre 4 causes possibles que la seule réponse finale rend indiscernables.
- Conclure sur la boucle : un incident diagnostiqué mais non converti en test rejouable reviendra. C'est la réponse directe au symptôme du brief — des incidents qui reviennent.

## Transition vers la conclusion

C'est cette boucle complète — test qui échoue, trace qui explique, correctif qui se vérifie — qui rend Mardik diagnosticable.
