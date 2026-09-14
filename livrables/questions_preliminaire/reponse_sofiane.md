# Diagnostic et observabilité d’une application LLM chez Mardik

## 1. Contexte et objectifs

L’application Mardik subit des pannes récurrentes sans que les équipes disposent de tests réalistes ni de traces exploitables pour comprendre les causes profondes.
L’objectif est de rendre le système diagnosticable en combinant :
- des tests d’intégration multi‑sessions, proches des usages réels,
- une observabilité orientée LLM (traces, métriques, logs, évaluations) couvrant l’ensemble du pipeline d’agent.

Ce document propose une note de diagnostic et un schéma d’observabilité, ainsi qu’un article d’ingénierie recommandé sur l’observabilité des systèmes à base de LLM.

---

## 2. Tests unitaires vs tests d’intégration pour un agent

### 2.1. Test unitaire pour un agent

Un test unitaire pour un agent IA vise une brique isolée de la logique d’agent :
- Génération ou transformation de prompt.
- Sélection de tool ou de sous‑agent.
- Parsing et validation de la réponse.
- Petites fonctions de décision (par exemple : choix du prochain outil).

Ces tests restent indispensables, mais ils ne captent ni la latence globale, ni les effets de charge, ni les interactions entre composants (retrieval, LLM, tools, mémoire, réseau).

### 2.2. Test d’intégration pour un agent

Un test d’intégration vérifie un scénario complet de bout en bout :
- Entrée utilisateur → orchestrateur d’agent → retrieval (RAG, bases internes) → appels LLM → appels de tools externes → post‑traitement → réponse.
- Les invariants contrôlés portent sur la latence, le taux d’erreurs, la qualité fonctionnelle de la réponse et la consommation de ressources (tokens/coûts).

Pour un agent multi‑agents ou multi‑tools, un test d’intégration doit valider :
- Le bon enchaînement des étapes (spans dans le trace).
- L’absence de boucles ou d’appels inutiles.
- La cohérence des réponses produites par rapport aux règles métier.

### 2.3. Tests d’intégration multi‑sessions

Dans le contexte Mardik, les tests d’intégration doivent simuler :
- Plusieurs utilisateurs en parallèle (concurrence, contention sur ressources partagées).
- Des sessions longues avec maintien de contexte (mémoire, historique conversaton, caches de retrieval).
- Des scénarios critiques métier (par exemple : génération de documents contractuels, traitements analytiques, workflows multi‑étapes).

Chaque scénario est associé à des critères de succès :
- Latence P95/P99 en dessous d’un seuil.
- Taux d’erreurs par type (timeouts, erreurs de tools, réponses invalides) en dessous d’un seuil.
- Score minimal de qualité (évaluations automatiques ou scripts métier).

---

## 3. Observer une application IA : principes

Observer une application LLM signifie passer d’une « boîte noire » à une « glass box » : il s’agit de suivre comment chaque requête est traitée, pas seulement si le serveur répond.

Les pratiques modernes d’observabilité LLM reposent sur quatre axes :
- **Traces** : arbre de spans pour chaque requête, couvrant toutes les étapes du pipeline.
- **Métriques** : latence, volume, erreurs, consommation de tokens et coûts.
- **Logs** : messages textuels corrélés aux traces, permettant de comprendre le contexte.
- **Évaluations** : scores de qualité, détecteurs de hallucination, indicateurs de sécurité et de conformité.

Un système LLM doit en plus être observé sur sa dimension sémantique :
- Contenu et structure des prompts.
- Drift de comportement dans le temps (changements de modèle, de prompt, de données).
- Respect des politiques internes (sécurité, conformité, ton, style).

---

## 4. Métriques de santé pour une app LLM

### 4.1. Latence

La latence est une métrique clé, à mesurer à plusieurs niveaux :
- Latence end‑to‑end : du moment où l’utilisateur envoie la requête au moment où la réponse est disponible.
- Time‑to‑first‑token (TTFT) : temps jusqu’à la première partie de la réponse.
- Latence par étape : retrieval, appel LLM, tool, post‑traitement.
- Distribution de latence (P50, P95, P99) plutôt que moyenne, pour détecter les cas extrêmes.

### 4.2. Volume et throughput

Les métriques de volume permettent d’anticiper les saturations :
- Nombre de requêtes par minute/heure.
- Sessions actives.
- Répartition du trafic par fonctionnalité (chat, génération de documents, analyses, etc.).

### 4.3. Tokens et coûts

Les systèmes LLM impliquent un coût variable lié au nombre de tokens :
- Tokens en entrée et en sortie par requête.
- Consommation par modèle, par feature et par tenant.
- Coût estimé par requête et par période (journalier, hebdomadaire), avec burn rate par rapport au budget.

Ces métriques permettent de :
- Identifier les scénarios disproportionnés en coût.
- Mettre en place des limites ou des dégradations contrôlées.

### 4.4. Erreurs

Les métriques d’erreurs doivent être segmentées :
- Taux global d’erreurs.
- Erreurs techniques : timeouts, erreurs réseau, rate limits, exceptions serveur.
- Erreurs de tools : échecs d’API métier, validations qui échouent.
- Réponses invalides : formats non respectés, JSON invalide, manque de champs requis.

Cette segmentation permet de prioriser la remédiation (infra vs prompt vs logique métier).

### 4.5. Qualité et sécurité

Les métriques de qualité sont spécifiques aux systèmes LLM :
- Scores de factualité, pertinence, utilité (LLM‑as‑judge ou scripts métiers).
- Indicateurs de hallucination, de toxicité, de non‑conformité.
- Taux de réussite sur un jeu de tests fonctionnels (bench d’évaluation).

La sécurité et la conformité peuvent être suivies via :
- Détecteurs de contenus sensibles.
- Politiques de redaction et d’anonymisation.

---

## 5. Points d’instrumentation : rendre les traces exploitables

Pour qu’un trace soit exploitable, il faut instrumenter les bons points du pipeline :

### 5.1. Span racine par requête

Chaque requête utilisateur doit correspondre à un span racine :
- Attributs typiques : `trace_id`, `user_id`, `session_id`, `feature`, `tenant`.
- Le span couvre tout le cycle : API gateway → service d’orchestration → réponse.

### 5.2. Spans enfants pour chaque étape

Sous le span racine, des spans enfants décrivent :
- Le retrieval : source utilisée (vecteur, BDD), nombre de documents, temps de réponse, taille de contexte.
- L’appel LLM : modèle, version, paramètres (temperature, top_p, etc.), longueur de prompt, tokens in/out, raison de l’arrêt, latence.
- Les tools : nom du tool, arguments, résultat, erreurs, latence.

### 5.3. Logs corrélés aux traces

Les logs doivent être corrélés aux traces via `trace_id` et `span_id` :
- Chaque log inclut ces identifiants en métadonnées.
- Les messages de log décrivent l’état fonctionnel (paramètres importants, décisions d’agent, messages d’erreur).

La corrélation permet de reconstituer l’histoire détaillée d’une requête à partir des traces et des logs.

### 5.4. Métadonnées de version

Les traces doivent embarquer des informations de version :
- Version de modèle.
- Version de prompt.
- Version de configuration d’agent et de routing.

Ainsi, lorsqu’un incident apparaît, il devient possible de le lier à une release, à un changement de prompt ou à une modification de configuration.

### 5.5. Instrumentation privacy‑by‑design

L’observabilité doit respecter les contraintes de confidentialité et de conformité :
- Logs centrés sur des métadonnées (pas de données brutes sensibles).
- Redaction et anonymisation des champs sensibles.
- Contrôle d’accès aux traces et aux logs.

Cette approche permet d’avoir une observabilité riche sans exposer les données réelles des utilisateurs.

---

## 6. Relier un test d’intégration échoué aux causes via les traces

Pour que les tests d’intégration soient utiles au diagnostic, il faut les relier explicitement aux traces.

### 6.1. Trace‑aware testing

Le runner de tests d’intégration doit :
- Récupérer le `trace_id` associé à chaque requête de test.
- Enregistrer ce `trace_id` avec le résultat du test (succès/échec, assertions violées).

En cas d’échec, cela permet de :
- Ouvrir le trace correspondant dans l’outil (Jaeger, Grafana Tempo, Langfuse, LangSmith, etc.).
- Inspecter l’arbre de spans pour voir où le temps est passé et où l’erreur est apparue.

### 6.2. Navigation dans le trace

Les traces détaillées permettent de :
- Identifier le span fautif (retrieval vide, tool en erreur, modèle trop lent).
- Vérifier le contenu des prompts et les arguments des tools au moment du problème.
- Voir la séquence exacte d’appels d’agent (par exemple : boucle sur un tool, retries, timeouts).

### 6.3. Couplage avec les évaluations de qualité

Les tests d’intégration peuvent aussi déclencher des évaluations automatiques :
- Score de qualité (correctness, pertinence, format) attaché au trace.
- Indicateurs de hallucination ou de non‑conformité.

Ainsi, un test peut échouer sur :
- Un problème technique (timeout, exception).
- Un problème fonctionnel (réponse incorrecte, format non respecté).

Dans les deux cas, le trace donne les éléments pour remonter à la cause.

### 6.4. Boucle de remédiation

Une fois le span fautif identifié, la boucle de remédiation peut être organisée :
- Création de tickets sur l’élément incriminé (infra, code, prompt, configuration d’agent, modèle).
- Suivi de la correction via de nouveaux tests d’intégration.
- Comparaison des traces avant/après pour vérifier l’amélioration.

---

## 7. Note de diagnostic pour Mardik (structure proposée)

Une note de diagnostic pour Mardik peut être structurée de la manière suivante.

### 7.1. Contexte et symptômes

- Description synthétique de l’application, des agents et des cas d’usage métier.
- Description des incidents : fréquence, impact utilisateur, symptômes visibles.
- État actuel : absence de tests d’intégration réalistes, manque de traces, logs non corrélés.

### 7.2. Analyse des causes probables

- Risques liés à l’absence de tests d’intégration multi‑sessions :
  - Concurrence mal gérée.
  - Surcharge de modèles ou de bases.
  - Dérives de mémoire ou de caches.
- Risques liés à l’absence d’observabilité LLM :
  - Aucun suivi de tokens, de coûts, de latence fine.
  - Impossibilité de relier un incident à une configuration précise.

### 7.3. Plan d’observabilité

- Stack proposée :
  - OpenTelemetry pour traces et métriques.
  - Backend de traces (Jaeger, Grafana Tempo, Langfuse, LangSmith).
  - Backend de métriques (Prometheus) + Grafana pour dashboards et alertes.
  - Backend de logs (Loki, ELK/OpenSearch).
- Définition de SLOs :
  - Latence P95 par fonctionnalité.
  - Taux d’erreurs par type.
  - Budget de tokens et de coûts par période.

### 7.4. Plan de tests d’intégration

- Liste des scénarios multi‑sessions à couvrir.
- Critères de succès et d’échec par scénario.
- Intégration des tests dans le CI/CD et dans la surveillance continue.

### 7.5. Recommandations et priorisation

- Actions immédiates :
  - Instrumentation minimale (traces basiques, métriques clés, corrélation logs).
  - Mise en place de premiers tests d’intégration et de charge.
- Actions à moyen terme :
  - Évaluations automatiques de qualité.
  - Dashboards FinOps (coûts, tokens, budgets).
  - Alertes sur SLOs et budgets.

---

## 8. Schéma d’observabilité (description textuelle)

Ci‑dessous une description textuelle d’un schéma d’observabilité pour Mardik.

### 8.1. Flux principal

- Client (web/mobile) → API Gateway → Service d’orchestration d’agent →
  - Retriever RAG (base vectorielle, BDD, caches).
  - LLM provider (OpenAI, Anthropic, modèles internes, vLLM, etc.).
  - Tools (APIs métier, systèmes documentaires, services externes).
- Retour de la réponse vers le client.

### 8.2. Instrumentation sur le flux

- Dans le service d’orchestration :
  - SDK OpenTelemetry/LLM créant un span racine pour chaque requête.
  - Spans enfants pour retrieval, appels LLM, calls de tools.
- Au niveau des appels LLM :
  - Intégration avec une plateforme d’observabilité LLM (Langfuse, LangSmith, etc.) enregistrant prompts, tokens, latence, coût, erreurs.
- Au niveau des métriques :
  - Export de latence, error rate, token usage, scores d’évaluations vers Prometheus.
  - Visualisation dans Grafana avec dashboards par fonctionnalité.
- Au niveau des logs :
  - Envoi des logs applicatifs vers Loki ou ELK/OpenSearch.
  - Corrélation par `trace_id` pour un filtrage contextuel.

### 8.3. Métriques positionnées sur le schéma

- Sur le bloc LLM :
  - TTFT, latence par appel.
  - Tokens input/output, coût.
- Sur le bloc retrieval :
  - Latence, nombre de documents, taille du contexte.
- Sur le bloc agent :
  - Latence end‑to‑end.
  - Error rate global et par type.
  - Score moyen de qualité (évaluations).

Ce schéma permet d’expliquer où seront générées les traces, quelles métriques seront collectées et comment elles seront agrégées pour fournir une vue de santé globale du système.

---

## 9. Article d’ingénierie recommandé sur l’observabilité LLM

Pour approfondir l’observabilité des systèmes LLM et des workflows d’agent, un article d’ingénierie particulièrement pertinent est :

- "What is LLM observability? (Tracing, evals, and monitoring ...)" – Braintrust.

Cet article couvre :
- La définition de l’observabilité LLM et ses différences avec l’observabilité classique.
- Les rôles du tracing, des métriques et des évaluations dans le diagnostic des systèmes LLM.
- Des exemples concrets de traces de runs d’agent (avec spans représentant les appels LLM et les tools).
- Des recommandations pratiques sur les métriques à suivre (latence, coût, erreurs, qualité) et la manière de les relier aux incidents.

En complément, d’autres ressources techniques utiles peuvent être mobilisées pour concevoir l’observabilité de Mardik, notamment celles centrées sur OpenTelemetry pour les apps LLM, les guides d’observabilité Langfuse, et les articles sur le monitoring de workflows RAG et d’agents.

---

## 10. Synthèse

Ce document propose un cadrage pour :
- Mettre en place des tests d’intégration multi‑sessions orientés scénarios métier.
- Instrumenter le pipeline d’agent de Mardik avec des traces, des métriques, des logs et des évaluations.
- Relier de manière systématique les tests échoués aux traces pour accélérer le diagnostic.

La mise en œuvre de ce plan doit permettre de transformer l’application Mardik en un système observé et contrôlable, où chaque incident peut être expliqué par des données concrètes et relié à une cause précise (infra, code, prompt, configuration ou modèle).
