"""The Mardik agent: turns a user message into a reply, calling tools as needed."""
from __future__ import annotations

import threading
import time
from dataclasses import dataclass
from typing import Any, Callable, Protocol

from opentelemetry import context as otel_context

from .errors import LLMTimeoutError
from .session import SessionStore
from .telemetry import NoOpTelemetry


@dataclass
class Reply:
    content: str
    tool_calls: list[dict[str, Any]]


@dataclass
class TurnResult:
    session_id: str
    reply: str


class LLM(Protocol):
    def invoke(self, messages: list[dict[str, Any]]) -> Reply: ...


class Agent:
    def __init__(
        self,
        llm: LLM,
        tools: dict[str, Callable[..., str]],
        telemetry: Any | None = None,
    ) -> None:
        self.llm = llm
        self._tools = tools
        self.telemetry = telemetry if telemetry is not None else NoOpTelemetry()

    def _invoke_llm_sync(self, messages: list[dict[str, Any]]) -> Reply:
        with self.telemetry.tracer.start_as_current_span("llm.invoke"):
            try:
                return self.llm.invoke(messages)
            except TimeoutError as exc:
                raise LLMTimeoutError("upstream deadline exceeded") from exc

    def _invoke_llm(self, messages: list[dict[str, Any]]) -> Reply:
        # The Azure SDK call is blocking, so run it on a worker thread.
        # Le contexte OTel est propagé manuellement : un thread démarre par
        # défaut sans le contexte courant, ce qui casserait le lien entre
        # le span llm.invoke et le span agent.turn qui l'englobe.
        box: dict[str, Any] = {}
        parent_ctx = otel_context.get_current()

        def worker() -> None:
            token = otel_context.attach(parent_ctx)
            try:
                box["reply"] = self._invoke_llm_sync(messages)
            except Exception as exc:  # noqa: BLE001 - relevée dans le thread appelant
                box["error"] = exc
            finally:
                otel_context.detach(token)

        thread = threading.Thread(target=worker)
        thread.start()
        thread.join()
        if "error" in box:
            raise box["error"]
        return box["reply"]

    def _dispatch_tool(self, call: dict[str, Any]) -> str:
        with self.telemetry.tracer.start_as_current_span("tool.call"):
            tool = self._tools[call["name"]]
            return tool(**call["args"])

    def run_turn(
        self, store: SessionStore, session_id: str, user_message: str
    ) -> TurnResult:
        with self.telemetry.tracer.start_as_current_span("agent.turn"):
            start = time.perf_counter()
            store.append(session_id, {"role": "user", "content": user_message})
            store.record_turn(session_id)

            try:
                reply = self._invoke_llm(store.history(session_id))

                text = reply.content
                for call in reply.tool_calls:
                    text = self._dispatch_tool(call)

                store.append(session_id, {"role": "assistant", "content": text})
            except Exception as exc:
                elapsed_ms = (time.perf_counter() - start) * 1000.0
                self.telemetry.errors.add(
                    1, attributes={"session_id": session_id, "error.type": type(exc).__name__}
                )
                self.telemetry.logger.error(
                    "turn.failed",
                    session_id=session_id,
                    elapsed_ms=elapsed_ms,
                    error_type=type(exc).__name__,
                    error=str(exc),
                )
                raise

            elapsed_ms = (time.perf_counter() - start) * 1000.0
            self.telemetry.record_latency(elapsed_ms, session_id=session_id)
            self.telemetry.logger.info(
                "turn.completed", session_id=session_id, elapsed_ms=elapsed_ms
            )
            return TurnResult(session_id=session_id, reply=text)
