# Travail préliminaire de conception — Notes de recherche

> Réponses aux 4 questions du brief (§ Modalités pédagogiques). Base de travail pour la future **note de diagnostic + schéma d'observabilité**.

---

## 1. Qu'est-ce qu'un test d'intégration pour un agent (vs unitaire) ? Que veut dire observer une application IA ?

### Test unitaire vs test d'intégration

| | Test unitaire | Test d'intégration |
|---|---|---|
| **Cible** | Une fonction/logique isolée (validation de schéma, format d'appel d'outil, retry) | Le pipeline complet : enchaînement d'appels LLM, outils, mémoire, API externes |
| **LLM réel ?** | Non — provider mocké, réponses en dur | Souvent oui, mais via **enregistrement/rejeu** (record & replay) |
| **Objectif** | Vérifier une logique déterministe | Vérifier que les composants coopèrent dans un scénario réaliste |
| **Coût** | Rapide, nombreux (base de la pyramide) | Plus lent, moins nombreux (milieu de la pyramide) |

Le [Block Engineering Blog](https://engineering.block.xyz/blog/testing-pyramid-for-ai-agents) formalise ça avec une **pyramide de tests adaptée aux agents** :
- Les tests unitaires mockent le LLM (« *most of these tests use mock providers that return canned responses* »).
- Les tests d'intégration **enregistrent une session réelle une fois** (prompts, réponses, appels d'outils/MCP) dans une fixture JSON, puis la **rejouent** de façon déterministe. C'est le principe du `TestProvider` en deux modes : *recording* (capture les vraies réponses, indexées par hash de l'entrée) et *playback* (réutilise les fixtures sans rappeler le modèle).

**Pourquoi c'est différent d'un test classique** : le LLM est **non-déterministe** — un même prompt peut produire des réponses différentes, toutes valides. On ne peut donc pas comparer une sortie à une valeur figée. Le rejeu fige le comportement à un instant T, ce qui permet de détecter des **régressions dans le code applicatif** (parsing, gestion d'erreur, enchaînement d'étapes) sans dépendre de la variabilité du modèle ni de la disponibilité des services externes — exactement ce que demande le brief : « tests d'intégration rejouant des sessions réelles ».

### Observer une application IA

D'après [Langfuse](https://langfuse.com/docs/observability/overview) et [Braintrust](https://www.braintrust.dev/articles/llm-observability-guide), observer ≠ savoir que l'appli tourne (monitoring « uptime » classique). Il s'agit de **tracer le cheminement complet d'une requête** :

```
entrée utilisateur → construction du prompt → appel(s) LLM → appels d'outils/RAG → sortie finale
```

Pour chaque étape (« span ») : entrée, sortie, latence, tokens consommés, métadonnées. Les spans sont **imbriqués** pour reconstituer la causalité (quelle étape a produit quel résultat).

Sans ça, déboguer une appli IA relève du « *guesswork* » (Langfuse) : on voit qu'elle a planté, mais pas pourquoi, ni à quelle étape du raisonnement.

---

## 2. Quelles métriques révèlent la santé d'une application IA ?

Les 4 "golden signals" classiques (latence, trafic, erreurs, saturation) ne suffisent pas : un appel LLM qui répond avec succès (HTTP 200) ne dit rien sur la **qualité** de la réponse. Trois familles de défis se combinent ([Comet](https://www.comet.com/site/blog/llm-observability/)) :

| Catégorie | Métriques |
|---|---|
| **Opérationnel** | Taux de requêtes, taux d'erreur, *time to first token* (TTFT), latence totale de génération, débit (tokens/s) |
| **Économique** | Tokens en entrée/sortie, coût par requête, coût par session utilisateur |
| **Qualité (proxy)** | Taux de feedback utilisateur (👍/👎), taux de retry (l'utilisateur régénère), taux de refus du modèle |
| **Qualité (évaluée)** | *Faithfulness* (la réponse est-elle ancrée dans le contexte fourni ?), *relevance* (répond-elle à la question ?), sécurité (toxicité, biais) |

Point clé : « l'erreur » n'est plus binaire — c'est une distribution à échantillonner et scorer dans le temps, car la sortie est probabiliste (même prompt → réponses différentes, toutes syntaxiquement valides).

**Pour Mardik**, à minima instrumenter : taux d'échec par type d'incident, latence par étape (pas seulement bout-en-bout), coût/tokens par session, et un score de qualité (même basique, ex. LLM-as-judge ou règle métier) pour détecter les réponses "fausses mais bien formées".

---

## 3. Quels points instrumenter pour rendre une trace exploitable ?

Principe directeur ([groundcover](https://www.groundcover.com/learn/observability/ai-agent-observability), [FutureAGI](https://futureagi.com/blog/trace-debug-multi-agent-systems-observability-guide/)) : **tracer séparément** les appels LLM, les appels d'outils et les transitions d'état, avec un **contexte de trace propagé** de bout en bout (un `trace_id` unique par requête utilisateur, du premier au dernier span).

| Type de span | À capturer |
|---|---|
| **Span racine (run agent)** | ID agent, entrée utilisateur, phase de planification, sortie finale |
| **Appel LLM** | Modèle, provider, tokens entrée/sortie/cache, latence, TTFT, statut, erreur |
| **Appel d'outil** | Nom de l'outil, arguments, réponse, latence, succès/échec |
| **Récupération (RAG)** | Source de données, nombre de chunks, signaux de pertinence |
| **Décision/routing** | Route sélectionnée, score de décision |
| **État/mémoire** | Transitions d'état entre étapes (si l'agent a une mémoire) |

Bonnes pratiques mentionnées :
- **Nommer les spans explicitement** (`research_agent:web_search` plutôt que `tool_call`).
- **Instrumenter dès le départ**, pas après un incident en prod — ajouter du tracing a posteriori est beaucoup plus coûteux.
- Conserver le **prompt exact envoyé** (pas juste le template) pour pouvoir rejouer/comparer.

---

## 4. Comment relier un test d'intégration échoué à une cause via les traces ?

Méthode en 4 étapes décrite par [Braintrust](https://www.braintrust.dev/articles/how-to-trace-llm-failure-root-cause) :

1. **Localiser la trace** — filtrer par ID utilisateur/session, statut d'erreur, extrait de sortie ou horodatage pour retrouver la requête en échec.
2. **Parcourir l'arbre de spans** dans l'ordre chronologique, en comparant la sortie de chaque étape à ce qu'elle *aurait dû* produire.
3. **Isoler la couche fautive** en inspectant les métadonnées de chaque span : récupération (contexte incomplet/faux ?), prompt (mal rendu ?), outil (mauvais arguments/réponse ?), modèle (version/config ?).
4. **Confirmer et transformer en test** — rejouer avec le correctif proposé, puis **promouvoir la trace en échec comme cas de régression** dans le jeu de tests d'intégration (CI).

C'est le pont direct entre debug et le livrable attendu : *« vérifier que les tests d'intégration détectent désormais ces incidents »* — chaque incident diagnostiqué via les traces devient un test de non-régression rejouable.

---

## Sources

- [Testing Pyramid for AI Agents — Block Engineering Blog](https://engineering.block.xyz/blog/testing-pyramid-for-ai-agents)
- [Building realistic multi-turn tests for AI agents — Zendesk](https://zendesk.com/blog/zip1-building-realistic-multi-turn-tests-for-ai-agents)
- [LLM Observability & Application Tracing — Langfuse](https://langfuse.com/docs/observability/overview)
- [What is LLM observability? — Braintrust](https://www.braintrust.dev/articles/llm-observability-guide)
- [LLM Tracing and Agent Observability — MLflow](https://mlflow.org/docs/latest/genai/tracing/)
- [What is LLM Observability? — Comet](https://www.comet.com/site/blog/llm-observability/)
- [AI Agent Observability Guide — groundcover](https://www.groundcover.com/learn/observability/ai-agent-observability)
- [Multi-Agent Tracing 2026 — FutureAGI](https://futureagi.com/blog/trace-debug-multi-agent-systems-observability-guide/)
- [How to trace an LLM failure back to its root cause — Braintrust](https://www.braintrust.dev/articles/how-to-trace-llm-failure-root-cause)

## Article d'ingénierie à retenir pour le livrable "article trouvé"

**[Testing Pyramid for AI Agents — Block Engineering Blog](https://engineering.block.xyz/blog/testing-pyramid-for-ai-agents)** : couvre à la fois l'observabilité et les tests d'intégration par rejeu, directement alignés avec la mission (répond à 2 exigences du brief avec un seul article).
