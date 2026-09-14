"""Vérifie que le câblage télémétrie par défaut (``build_agent``) atteint
réellement Jaeger. Suppose Jaeger démarré (``make up``).
"""
from __future__ import annotations

import json
import time
import urllib.error
import urllib.request

from mardik.agent import Reply
from mardik.app import build_agent
from mardik.session import SessionStore


class _StaticLLM:
    def invoke(self, messages: list[dict]) -> Reply:
        return Reply(content="Bonjour, comment puis-je vous aider ?", tool_calls=[])


def _fetch_traces(service: str, limit: int = 1) -> list[dict]:
    url = f"http://localhost:16686/api/traces?service={service}&limit={limit}"
    with urllib.request.urlopen(url, timeout=5) as response:
        return json.load(response)["data"]


def test_default_telemetry_reaches_jaeger():
    agent = build_agent(llm=_StaticLLM())
    try:
        store = SessionStore()
        agent.run_turn(store, "live-telemetry-001", "Bonjour, comment allez-vous ?")

        # Jaeger indexe rapidement en mémoire, mais pas instantanément : on
        # poll plutôt que de fixer un sleep arbitraire.
        deadline = time.monotonic() + 10
        traces: list[dict] = []
        while time.monotonic() < deadline:
            try:
                traces = _fetch_traces("mardik")
            except urllib.error.URLError:
                traces = []
            if traces:
                break
            time.sleep(0.5)

        assert traces, "expected at least one trace for service 'mardik' in Jaeger"
    finally:
        # Sans cet arrêt explicite, le thread d'export périodique des
        # métriques (build_default_telemetry) survit à la fin du test et
        # tente d'écrire sur stdout une fois pytest terminé.
        agent.telemetry.shutdown()
