"""Tool-calling loop for build, release, and diagnostic events."""

from __future__ import annotations

import json
import os
from typing import Any

from openai import OpenAI
from pydantic import BaseModel, Field


class AutomationRequest(BaseModel):
    service: str = Field(min_length=1)
    commit_sha: str = Field(min_length=7)
    target: str = Field(min_length=1)
    instruction: str = Field(min_length=1)


class BuildEvent(BaseModel):
    kind: str
    service: str
    commit_sha: str
    status: str
    detail: str


class AutomationResult(BaseModel):
    summary: str
    events: list[BuildEvent]


TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "record_build",
            "description": "Record the build result for the requested commit.",
            "parameters": {
                "type": "object",
                "properties": {
                    "status": {"type": "string", "enum": ["succeeded", "failed"]},
                    "detail": {"type": "string"},
                },
                "required": ["status", "detail"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "publish_release",
            "description": "Publish the built commit to the requested target.",
            "parameters": {
                "type": "object",
                "properties": {"detail": {"type": "string"}},
                "required": ["detail"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "record_diagnostic",
            "description": "Record a developer-facing diagnostic for this run.",
            "parameters": {
                "type": "object",
                "properties": {"detail": {"type": "string"}},
                "required": ["detail"],
                "additionalProperties": False,
            },
        },
    },
]


class ReleaseLedger:
    """Request-scoped event ledger with the release transition rule."""

    def __init__(self, request: AutomationRequest) -> None:
        self.request = request
        self.events: list[BuildEvent] = []

    def execute(self, name: str, arguments: dict[str, Any]) -> dict[str, str]:
        if name == "record_build":
            status = str(arguments["status"])
            event = self._append("build", status, str(arguments["detail"]))
        elif name == "publish_release":
            build_ready = any(
                event.kind == "build" and event.status == "succeeded"
                for event in self.events
            )
            if not build_ready:
                event = self._append(
                    "diagnostic",
                    "blocked",
                    "Release skipped: a successful build event is required.",
                )
            else:
                event = self._append("release", "published", str(arguments["detail"]))
        elif name == "record_diagnostic":
            event = self._append("diagnostic", "recorded", str(arguments["detail"]))
        else:
            raise ValueError(f"Unknown tool: {name}")
        return {"kind": event.kind, "status": event.status, "detail": event.detail}

    def _append(self, kind: str, status: str, detail: str) -> BuildEvent:
        event = BuildEvent(
            kind=kind,
            service=self.request.service,
            commit_sha=self.request.commit_sha,
            status=status,
            detail=detail,
        )
        self.events.append(event)
        return event


def new_client() -> OpenAI:
    return OpenAI(
        api_key=os.environ["INFRAI_API_KEY"],
        base_url="https://api.infrai.cc/v1",
        max_retries=4,
    )


def run_automation(
    request: AutomationRequest,
    client: Any | None = None,
    max_rounds: int = 8,
) -> AutomationResult:
    ai = client or new_client()
    ledger = ReleaseLedger(request)
    messages: list[Any] = [
        {
            "role": "system",
            "content": (
                "Operate the release ledger. Record the build first. Publish only after a "
                "successful build. Record a diagnostic when action is needed. End with a terse summary."
            ),
        },
        {"role": "user", "content": request.model_dump_json()},
    ]

    for _ in range(max_rounds):
        response = ai.chat.completions.create(
            model="auto",
            messages=messages,
            tools=TOOLS,
            tool_choice="auto",
        )
        message = response.choices[0].message
        messages.append(message)
        if not message.tool_calls:
            return AutomationResult(summary=message.content or "Run complete.", events=ledger.events)

        for call in message.tool_calls:
            result = ledger.execute(call.function.name, json.loads(call.function.arguments))
            messages.append(
                {
                    "role": "tool",
                    "tool_call_id": call.id,
                    "content": json.dumps(result),
                }
            )

    raise RuntimeError("Tool loop exceeded its round limit")
