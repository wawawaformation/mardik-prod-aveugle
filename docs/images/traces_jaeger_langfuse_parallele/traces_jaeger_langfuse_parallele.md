# Fiche de lecture — Export des traces en parallèle (Jaeger / Langfuse)

**Schéma :** [`traces_jaeger_langfuse_parallele.drawio`](traces_jaeger_langfuse_parallele.drawio) / [`.png`](traces_jaeger_langfuse_parallele.png)

## Objectif de lecture

Comprendre comment le même span part vers deux backends indépendants — un
échec sur l'un n'affecte pas l'autre.

## Ce qu'on voit

Après le `TracerProvider`, le flux se scinde en deux `SpanProcessor`
distincts, un par exportateur : Jaeger (gauche) et Langfuse (droite).

## Points clés à retenir

- **Protocoles différents** : Jaeger reçoit en gRPC (`:4317`), Langfuse
  **uniquement en HTTP** — gRPC n'est pas supporté côté Langfuse.
- **Authentification différente** : Jaeger local n'exige rien ; Langfuse
  exige du Basic Auth (`base64(public_key:secret_key)`), transmis en header.
- **Activation conditionnelle** : la branche Langfuse n'existe que si
  `LANGFUSE_PUBLIC_KEY`/`LANGFUSE_SECRET_KEY` sont renseignées dans `.env`.
  Sans elles, comportement strictement identique à avant (Jaeger seul) —
  tests et CI non affectés.
- Les deux backends ont des vocations différentes : Jaeger est généraliste
  (pas de notion de prompt/coût), Langfuse est pensé pour l'observabilité
  LLM (prompts, tokens, coûts, sessions, scores).

## Voir aussi

- `docs/superpowers/specs/2026-09-14-langfuse-self-hosted-design.md`
- [`langfuse_composants_dependances.md`](../langfuse_composants_dependances/langfuse_composants_dependances.md)
- `src/mardik/telemetry.py`
