---
title: "Cas pratique — Le parcours EDD d'Airbnb, du prototype au monitoring"
metadata:
  duree_cible: "2 min"
  source: "Eval-driven development: Lessons from evaluating GenAI at scale — Airbnb Tech Blog"
---

## Scénario (tel que décrit dans l'article)

> Airbnb construit un assistant IA qui répond à des questions sur les politiques de support d'une plateforme de voyage.

## Message clé

Ce cas est la preuve que l'EDD n'est pas une théorie : chaque étape est chiffrée, du prototype brut jusqu'au monitoring de production.

## Ce qu'il faut dire

**Étape 1 — Explorer.** 100 entrées passées dans le prototype, lecture manuelle de chaque sortie. Quatre familles d'erreurs identifiées :
- 15 réponses contiennent des détails de politique absents des documents sources → problème de **fidélité**.
- 8 réponses correctes mais trop verbeuses → problème de **concision**.
- 5 questions valides refusées → **sur-refus**.
- 3 sorties JSON cassées → problème de **format**.

**Étape 2 — Construire les évaluations.** Un check programmatique pour la validité JSON et les limites de longueur. Un juge virtuel pour la fidélité (prompt séparé, modèle différent de celui évalué, raisonnement explicite) et un autre pour la concision — un juge par dimension, jamais un juge unique généraliste. Un PM ou expert métier étiquette 60 exemples, échecs inclus, comme jeu de référence (« golden set »).

**Étape 3 — Calibrer et itérer.** Le juge de fidélité n'est d'accord avec le PM qu'à 78 % — insuffisant. L'analyse révèle qu'il pénalise à tort des paraphrases correctes comme « non fidèles ». Rubrique et exemples ajustés → accord à 88 %. L'équipe améliore ensuite l'étape de retrieval, et les échecs de fidélité chutent nettement. Point méthodologique à citer : on ne fait varier qu'une seule variable à la fois — d'abord le prompt à modèle fixe, puis le modèle à prompt fixe, puis la configuration de serving — pour garder les résultats interprétables.

**Étape 4 — Passer à l'échelle et monitorer.** L'évaluation passe de 100 à 5 000 exemples. En production : échantillonnage quotidien de 5 % du trafic désidentifié, passage des checks programmatiques et des juges virtuels, remontée des cas signalés pour revue humaine. Une revue hebdomadaire du PM referme la boucle : chaque nouveau mode de défaillance découvert devient une nouvelle évaluation.

## Point clé à souligner

La boucle ne s'arrête jamais : le monitoring de production redevient lui-même une nouvelle phase d'exploration. C'est ce mécanisme, pas un chiffre isolé, qui constitue l'apport réel du cas.

## Clôture

Un exemple chiffré vaut mieux qu'un principe abstrait : c'est ce que ce cas pratique apporte à la présentation.
