# Script de démo — 10 minutes — « L'application qui ment sur sa santé »

> Conducteur de présentation. Chaque bloc indique : le minutage, ce qu'on
> **dit** (🎤) et ce qu'on **fait à l'écran** (💻). Répéter au moins une fois
> en conditions réelles (terminal + navigateur déjà ouverts) avant le jour J
> — le minutage suppose que rien ne rame.
>
> Le diagnostic préliminaire (questions, note de diagnostic, cas réel
> transposé) a déjà été présenté ailleurs — on ne revient pas dessus ici,
> on enchaîne directement sur le développement et ses résultats.

## Vue d'ensemble (conducteur)

| # | Bloc | Durée | Cumul |
|---|---|---|---|
| 1 | Ouverture & contexte | 0:30 | 0:30 |
| 2 | Incidents trouvés et corrigés | 2:30 | 3:00 |
| 3 | Tests d'intégration — démo live | 1:30 | 4:30 |
| 4 | Observabilité — Jaeger + Langfuse côte à côte | 2:45 | 7:15 |
| 5 | **[Camarade]** Le vrai LLM en action | 1:30 | 8:45 |
| 6 | Bilan & conclusion | 1:00 | 9:45 |
| — | Marge / questions | 0:15 | 10:00 |

**Prérequis avant de commencer :** `make up` déjà lancé (Jaeger sur `:16686`,
Langfuse sur `:3000`), deux onglets navigateur ouverts et connectés
(Langfuse : `dev@mardik.local` / `mardik-dev-password`), un terminal dans
`mardik-prod-aveugle/`.

---

## 1. Ouverture & contexte — 0:30

🎤 **À dire :**
> « Vous avez déjà vu le diagnostic initial et le cas réel qu'on a étudié
> pour s'en inspirer. On enchaîne directement sur ce qu'on en a fait :
> rendre Mardik diagnosticable, pour de vrai, en développement. »

💻 **À l'écran :** rien encore — juste le titre du brief ou un slide de
présentation, si vous en avez un.

---

## 2. Incidents trouvés et corrigés — 2:30 (3:00)

🎤 **À dire :**
> « On a écrit des tests qui rejouent de vraies sessions de conversation
> et instrumenté l'application. Résultat : 11 incidents diagnostiqués et
> corrigés, tous documentés cause par cause. »

💻 **À l'écran :** ouvrir `livrables/journal_incidents.md`,
faire défiler le tableau.

🎤 **Zoomer sur 3 exemples parlants :**
> « Par exemple : l'application **perdait le contexte** à chaque rejeu de
> session — elle répondait comme si elle découvrait la conversation, alors
> que le client venait de donner son numéro de commande trois messages
> plus tôt. Ou encore une **race condition** classique : sous plusieurs
> appels concurrents, le compteur de tours perdait des incréments — un
> grand classique de la concurrence mal gérée. Et le plus révélateur :
> un **nom de service jamais câblé** dans OpenTelemetry — l'app envoyait
> bien ses traces à Jaeger, mais sous le nom `unknown_service`. Invisible.
> On ne l'a trouvé qu'en testant contre un vrai Jaeger, pas avec des mocks
> en mémoire — la preuve que tester contre un vrai backend a une valeur
> que les tests hermétiques n'ont pas. »

💻 **À l'écran (garanti, 10 sec) :** ouvrir
`docs/images/pipeline_run_turn_reel/pipeline_run_turn_reel.png`
— le pipeline annoté avec les points de défaillance, en appui visuel des
3 exemples qu'on vient de citer.

---

## 3. Tests d'intégration — démo live — 1:30 (4:30)

🎤 **À dire :**
> « Ces incidents ne sont pas juste corrigés une fois : ils sont vérifiés
> en continu. La CI fait tourner ces tests à chaque push. Je vous montre
> en direct. »

💻 **À l'écran — schéma (garanti, 10 sec) :** ouvrir
`docs/images/tests_integration_composants/tests_integration_composants.png`
— les 4 familles de tests (succès, échec, concurrence, backend réel) et
leurs composants, avant que le terminal ne défile trop vite pour les lire.

💻 **À l'écran — terminal :**

```bash
cd mardik-prod-aveugle
uv run pytest tests/unit tests/integration --ignore=tests/integration/test_live_telemetry.py --ignore=tests/integration/test_live_langfuse.py -v
```

🎤 **Pendant que ça défile :**
> « 27 tests, zéro dépendance à Docker pour la plupart — 9 des 10 tests
> d'intégration rejouent une session complète et détectent l'incident via
> le chemin réel, pas en appelant une fonction isolée. »

💻 Laisser le résultat final (`27 passed`) visible à l'écran 2-3 secondes.

---

## 4. Observabilité — Jaeger + Langfuse côte à côte — 2:45 (7:15)

🎤 **À dire :**
> « Pour la partie diagnostic en production, on a câblé deux backends en
> parallèle : Jaeger, généraliste, et Langfuse, self-hébergé, pensé
> spécifiquement pour observer des applications LLM. Le même span part
> vers les deux, indépendamment — si l'un tombe, l'autre continue de
> fonctionner. »

💻 **À l'écran — schéma (avant le live, pas en filet de secours) :**
ouvrir `docs/images/traces_jaeger_langfuse_parallele/traces_jaeger_langfuse_parallele.png`
— montrer le fan-out (un span, deux exportateurs) 10-15 secondes.

💻 **À l'écran — schéma (garanti, 15 sec) :** ouvrir
`docs/images/pipeline_observabilite_mardik/pipeline_observabilite_mardik.png`
— la hiérarchie des 3 spans jusqu'à leurs métriques et logs, pour situer
ce qu'on va voir dans le code puis dans les deux UI.

💻 **À l'écran — code source (garanti, 15 sec) :** ouvrir `src/mardik/agent.py`
autour de la ligne 97 (`_dispatch_tool`) — montrer concrètement comment un
span se crée :

```python
def _dispatch_tool(self, session_id: str, call: dict[str, Any]) -> str:
    with self.telemetry.tracer.start_as_current_span("tool.call") as span:
        span.set_attribute("langfuse.observation.type", "tool")
        span.set_attribute("session.id", session_id)
        span.set_attribute("tool.name", call["name"])
```

🎤 :
> « Concrètement, dans le code, un span c'est juste ce bloc `with` : on
> l'ouvre, on pose quelques attributs, et OpenTelemetry se charge du
> reste — mesurer la durée, propager le contexte, l'exporter vers les
> deux backends en même temps. »

💻 **À l'écran — terminal (génère une vraie trace sur les deux backends) :**

```bash
uv run pytest tests/integration/test_live_telemetry.py tests/integration/test_live_langfuse.py -v
```

🎤 **Pendant que ça tourne :**
> « Ces deux tests-là ne mockent rien : ils envoient un vrai tour de
> conversation, en HTTP et en gRPC, vers les deux backends réels, puis
> vérifient que la trace y est bien arrivée. »

💻 **Basculer navigateur — onglet Jaeger (`localhost:16686`) :**
- Sélectionner le service `mardik`, cliquer sur la dernière trace.
- Montrer les 3 spans imbriqués (`agent.turn` → `llm.invoke` → `tool.call`).

🎤 :
> « Ici, un waterfall générique — utile pour voir l'enchaînement et la
> latence, mais aucune notion de prompt, de modèle ou de coût. »

💻 **Basculer navigateur — onglet Langfuse (`localhost:3000`, projet Mardik) :**
- Ouvrir la même trace.

🎤 :
> « Même trace, pensée pour un usage LLM. Elle porte maintenant des
> attributs métier — `session.id` sur les 3 spans, et un type
> d'observation qui route chaque span vers la bonne vue Langfuse : agent,
> génération, ou outil. Ce qu'on ne voit pas encore ici, c'est le détail
> modèle et tokens : ce test-là utilise un LLM simulé pour rester rapide.
> Avec un vrai appel, ces champs se remplissent — [Prénom du camarade] va
> vous le montrer dans un instant. »

💻 **À l'écran — schéma (guaranti, pas optionnel) :** ouvrir
`docs/images/langfuse_composants_dependances/langfuse_composants_dependances.png`
10 secondes — juste pour montrer que ce qu'on vient de voir dans l'UI
repose sur 6 conteneurs (web, worker, postgres, clickhouse, redis, minio),
pas de rentrer dans le détail.

💻 **Si le temps le permet en plus :** montrer aussi la vue "Sessions" ou
la liste des traces dans Langfuse, pour illustrer le regroupement par
conversation.

---

## 5. [Camarade] Le vrai LLM en action — 1:30 (8:30)

> ✅ **Corrigé (2026-09-14) — le vrai LLM fonctionne.** `get_llm` utilisait
> le mauvais client (`AzureAIChatCompletionsModel`, protocole natif Azure AI
> Inference) alors que l'endpoint (`.../openai/v1`) est compatible OpenAI —
> d'où l'erreur `BadRequest: API version not supported`. Remplacé par
> `langchain_openai.ChatOpenAI` (`base_url=` override). Vérifié de bout en
> bout : `uv run python -m mardik.app` répond réellement, `latency_ms` et
> `turn.completed` sont émis, la trace remonte dans Jaeger. C'est le 12ᵉ
> incident du journal (`livrables/journal_incidents.md`).
>
> ✅ **Bonus (2026-09-14, Sofiane) — les spans sont enrichis.** `agent.turn`,
> `llm.invoke`, `tool.call` portent désormais `session.id` et
> `langfuse.observation.type`. Sur `llm.invoke` avec un vrai appel, on a en
> plus `gen_ai.request.model` et `gen_ai.usage.{input,output}_tokens` —
> vérifié en direct : `Kimi-K2.6`, 10 tokens en entrée, 179 en sortie. C'est
> précisément la vue "coût/tokens" de Langfuse, vide jusqu'ici (section 4),
> qui s'active maintenant avec un vrai appel.
>
> 🔧 **Reste à préparer par le binôme :** un scénario de démo concret avec
> le vrai LLM (ex. rejouer une des sessions de `sessions/` avec le vrai
> modèle au lieu du LLM factice), et montrer dans Langfuse la vue
> tokens/coût qui se remplit enfin — c'est le point d'orgue naturel de la
> comparaison Jaeger/Langfuse amorcée en section 4.

🎤 **À dire (transition) :**
> « Jusqu'ici, toutes ces démos tournaient avec un modèle simulé, pour
> rester rapides et déterministes. [Prénom du camarade] va vous montrer ce
> que ça donne avec un vrai LLM branché — qui, accessoirement, ne
> fonctionnait pas du tout il y a encore une heure. »

---

## 6. Bilan & conclusion — 1:00 (9:30)

🎤 **À dire :**
> « En résumé : 11 incidents diagnostiqués et corrigés, une suite de 27
> tests qui les détectent tous via le chemin réel plutôt que des mocks
> isolés, une CI qui les rejoue à chaque push avec un vrai Jaeger, et deux
> backends d'observabilité en parallèle pour comparer une vue générique et
> une vue spécifique LLM. L'application ne ment plus sur sa santé — et
> surtout, si elle recommence, on a maintenant les moyens de le savoir. »

💻 **À l'écran :** revenir sur `livrables/journal_incidents.md` ou un slide
de synthèse, laisser la parole aux questions.

---

## Notes de préparation

- **Répétition obligatoire** : lancer une fois `make up` à froid pour
  mesurer le temps de démarrage réel de Langfuse (6 conteneurs) — s'il
  n'est pas déjà chaud le jour J, le prévoir *avant* le début du chrono.
- **Plan B si Docker ne coopère pas** : garder les captures d'écran
  `docs/images/*/*.png` en secours pour la section 4, et sauter
  directement au bilan si le temps presse.
- **Fichiers de référence pendant la préparation** : `CHANGELOG.md`
  (détail cause/correctif de chaque incident), `docs/comprendre_le_code.md`
  (vue d'ensemble du code), `docs/images/*/*.md` (fiches de lecture des
  schémas).
- **Les 5 schémas du projet** (tous dans `docs/images/<nom>/<nom>.png`) sont
  désormais tous placés dans ce script (`pipeline_run_turn_reel`,
  `tests_integration_composants`, `traces_jaeger_langfuse_parallele`,
  `pipeline_observabilite_mardik`, `langfuse_composants_dependances`).
- **Éditeur de code prêt** : pour la section 4, avoir `src/mardik/agent.py`
  déjà ouvert avec la ligne 97 visible (pas de temps perdu à chercher/scroller
  en direct).
