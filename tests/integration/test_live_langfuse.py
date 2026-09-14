"""Vérifie que Langfuse (self-hébergé) reçoit bien les traces, en plus de
Jaeger. Suppose Langfuse démarré (``make up``) et configuré dans ``.env``
(LANGFUSE_PUBLIC_KEY / LANGFUSE_SECRET_KEY, voir .env.example).
"""
from __future__ import annotations

import base64
import json
import time
import urllib.error
import urllib.request

from mardik.agent import Reply
from mardik.app import build_agent
from mardik.config import load_settings
from mardik.session import SessionStore


class _StaticLLM:
    def invoke(self, messages: list[dict]) -> Reply:
        # tool_calls non vide pour que le tour émette les 3 spans imbriqués
        # (agent.turn → llm.invoke → tool.call), cf. docs/script_demo_10min.md.
        return Reply(
            content="Un instant, je vérifie votre commande.",
            tool_calls=[{"name": "lookup_order", "args": {"order_id": "1042"}}],
        )


def _fetch_langfuse_traces(
    host: str, public_key: str, secret_key: str, limit: int = 5
) -> list[dict]:
    auth = base64.b64encode(f"{public_key}:{secret_key}".encode()).decode()
    request = urllib.request.Request(
        f"{host}/api/public/traces?limit={limit}",
        headers={"Authorization": f"Basic {auth}"},
    )
    with urllib.request.urlopen(request, timeout=5) as response:
        return json.load(response)["data"]


def test_default_telemetry_reaches_langfuse():
    settings = load_settings()
    assert settings.langfuse_public_key and settings.langfuse_secret_key, (
        "LANGFUSE_PUBLIC_KEY / LANGFUSE_SECRET_KEY doivent être renseignées "
        "dans .env pour ce test (voir .env.example)"
    )

    agent = build_agent(llm=_StaticLLM())
    try:
        store = SessionStore()
        agent.run_turn(store, "live-langfuse-001", "Bonjour, comment allez-vous ?")

        # Contrairement à Jaeger (indexation immédiate en mémoire), Langfuse
        # persiste via son worker : on laisse un peu plus de marge.
        deadline = time.monotonic() + 15
        traces: list[dict] = []
        while time.monotonic() < deadline:
            try:
                traces = _fetch_langfuse_traces(
                    settings.langfuse_host,
                    settings.langfuse_public_key,
                    settings.langfuse_secret_key,
                )
            except urllib.error.URLError:
                traces = []
            if any(trace["name"] == "agent.turn" for trace in traces):
                break
            time.sleep(1)

        assert any(trace["name"] == "agent.turn" for trace in traces), (
            "expected an 'agent.turn' trace in Langfuse"
        )
    finally:
        agent.telemetry.shutdown()
