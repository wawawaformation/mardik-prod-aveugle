# Comprendre le code de Mardik Support Agent

> Note de lecture du code existant, avant toute correction. Objectif :
> comprendre ce que fait réellement l'application aujourd'hui.

## Vue d'ensemble

C'est un **agent conversationnel de support client**. Un utilisateur pose une
question ("où est ma commande #1042 ?"), l'agent interroge un LLM (hébergé sur
Azure), et si besoin appelle des « outils » métier (statut de commande, base
de connaissances) pour formuler sa réponse.

## Le flux d'un tour de conversation

Le cœur du système est `Agent.run_turn()` (`src/mardik/agent.py:63-80`). Voici
ce qui se passe, étape par étape, quand un message utilisateur arrive :

1. **Ouverture d'un span de trace** (`agent.turn`). Un span OpenTelemetry
   représente « une opération qui a duré un certain temps » — un peu comme un
   bloc qui enregistre automatiquement début/fin/durée dans un système
   d'observabilité (ici Jaeger).

2. **Stockage du message utilisateur** dans le `SessionStore` — un dict en
   mémoire `{session_id: [liste de messages]}` (`src/mardik/session.py`).

3. **Appel du LLM** (`_invoke_llm`), avec tout l'historique de la conversation
   pour ce `session_id`. L'appel au SDK Azure est **bloquant** (synchrone),
   donc pour ne pas geler le thread appelant, le code le lance dans un
   **thread worker** dédié puis attend qu'il finisse (`thread.join()`).

4. **Traitement de la réponse** : si le LLM a demandé d'appeler un ou
   plusieurs outils (`tool_calls`), le code les exécute via `_dispatch_tool`
   — un dict de fonctions Python (`self._tools[nom](**args)`).

5. **Stockage de la réponse** et retour du résultat (`TurnResult`).

## La télémétrie

`src/mardik/telemetry.py` définit une classe `Telemetry` qui regroupe trois
piliers de l'observabilité :

- **`tracer`** : pour créer des spans (traces distribuées) ;
- **`logger`** : structlog, pour des logs JSON structurés ;
- **`latency_ms` / `errors`** : des instruments de métriques OpenTelemetry
  (histogramme et compteur).

Il existe aussi une classe `NoOpTelemetry` — un objet à la même interface mais
qui ne fait rien (pattern *Null Object*). Plutôt que de semer des
`if telemetry:` dans le code métier, on injecte par défaut un objet
« silencieux ». Utile en test, ou quand l'observabilité n'est pas câblée.

## Le rejeu de sessions (`runner.py`)

Idée du brief : au lieu de mocker des scénarios artificiels, on **rejoue de
vraies conversations enregistrées** (fichiers JSON dans `sessions/`) à travers
l'agent, et on vérifie que la réponse finale est cohérente. C'est un test
d'intégration réaliste plutôt qu'un test unitaire isolé.

## Ce que les tests existants révèlent déjà

Les tests (`tests/`) ne sont pas de simples exemples : ils **spécifient le
comportement attendu** de chaque brique (span attendu, log attendu, métrique
attendue, comportement en cas de timeout, comportement sous charge
concurrente). En les faisant tourner (`pytest -v`), 9 tests sur 10 échouent —
ce qui donne un contraste net entre « ce que le code est censé faire » et
« ce qu'il fait vraiment ». Voir le schéma associé :
[`images/pipeline_run_turn_reel.drawio`](images/pipeline_run_turn_reel.drawio)
(export : [`images/pipeline_run_turn_reel.png`](images/pipeline_run_turn_reel.png)).
