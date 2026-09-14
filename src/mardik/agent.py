"""The Mardik agent: turns a user message into a reply, calling tools as needed."""
from __future__ import annotations

import json
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

    def _invoke_llm_sync(self, session_id: str, messages: list[dict[str, Any]]) -> Reply:
        with self.telemetry.tracer.start_as_current_span("llm.invoke") as span:
            span.set_attribute("langfuse.observation.type", "generation")
            span.set_attribute("gen_ai.system", "openai")
            span.set_attribute("session.id", session_id)
            span.set_attribute(
                "langfuse.observation.input", json.dumps(messages, ensure_ascii=False)
            )
            try:
                reply = self.llm.invoke(messages)
            except TimeoutError as exc:
                raise LLMTimeoutError("upstream deadline exceeded") from exc
            self._annotate_llm_span(span, reply)
            return reply

    @staticmethod
    def _annotate_llm_span(span: Any, reply: Reply) -> None:
        # Real ChatOpenAI replies (AIMessage) carry response_metadata/usage_metadata;
        # the dataclass Reply used by tests does not, hence the getattr defaults.
        model = getattr(reply, "response_metadata", {}).get("model_name")
        if model:
            span.set_attribute("gen_ai.request.model", model)
        usage = getattr(reply, "usage_metadata", None) or {}
        if usage.get("input_tokens") is not None:
            span.set_attribute("gen_ai.usage.input_tokens", usage["input_tokens"])
        if usage.get("output_tokens") is not None:
            span.set_attribute("gen_ai.usage.output_tokens", usage["output_tokens"])
        span.set_attribute("langfuse.observation.output", reply.content)

    def _invoke_llm(self, session_id: str, messages: list[dict[str, Any]]) -> Reply:
        # The Azure SDK call is blocking, so run it on a worker thread.
        # Le contexte OTel est propagé manuellement : un thread démarre par
        # défaut sans le contexte courant, ce qui casserait le lien entre
        # le span llm.invoke et le span agent.turn qui l'englobe.
        box: dict[str, Any] = {}
        parent_ctx = otel_context.get_current()

        def worker() -> None:
            token = otel_context.attach(parent_ctx)
            try:
                box["reply"] = self._invoke_llm_sync(session_id, messages)
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

    def _dispatch_tool(self, session_id: str, call: dict[str, Any]) -> str:
        with self.telemetry.tracer.start_as_current_span("tool.call") as span:
            span.set_attribute("langfuse.observation.type", "tool")
            span.set_attribute("session.id", session_id)
            span.set_attribute("tool.name", call["name"])
            span.set_attribute(
                "langfuse.observation.input", json.dumps(call["args"], ensure_ascii=False)
            )
            tool = self._tools[call["name"]]
            result = tool(**call["args"])
            span.set_attribute("langfuse.observation.output", result)
            return result

    def run_turn(
        self, store: SessionStore, session_id: str, user_message: str
    ) -> TurnResult:
        with self.telemetry.tracer.start_as_current_span("agent.turn") as span:
            span.set_attribute("langfuse.observation.type", "agent")
            span.set_attribute("session.id", session_id)
            span.set_attribute("langfuse.observation.input", user_message)
            start = time.perf_counter()
            store.append(session_id, {"role": "user", "content": user_message})
            store.record_turn(session_id)

            try:
                reply = self._invoke_llm(session_id, store.history(session_id))

                text = reply.content
                for call in reply.tool_calls:
                    text = self._dispatch_tool(session_id, call)

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

            span.set_attribute("langfuse.observation.output", text)
            elapsed_ms = (time.perf_counter() - start) * 1000.0
            self.telemetry.record_latency(elapsed_ms, session_id=session_id)
            self.telemetry.logger.info(
                "turn.completed", session_id=session_id, elapsed_ms=elapsed_ms
            )
            return TurnResult(session_id=session_id, reply=text)
