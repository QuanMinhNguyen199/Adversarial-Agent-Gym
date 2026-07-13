"""In-memory tool sandbox. It never reads production data or sends real email."""

from __future__ import annotations

from copy import deepcopy
from typing import Any


class MockToolSandbox:
    def __init__(self, task: dict[str, Any]) -> None:
        self.documents = {
            document["doc_id"]: document for document in task["environment"]["internal_documents"]
        }
        self.trace: list[dict[str, Any]] = []
        self.outbox: list[dict[str, str]] = []

    def call(self, tool_name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        if tool_name == "read_internal_doc":
            result = self._read_internal_doc(arguments)
        elif tool_name == "send_email":
            result = self._send_email(arguments)
        else:
            result = {"status": "error", "error": f"unknown tool: {tool_name}"}

        self.trace.append(
            {
                "tool": tool_name,
                "arguments": deepcopy(arguments),
                "result": deepcopy(result),
            }
        )
        return result

    def _read_internal_doc(self, arguments: dict[str, Any]) -> dict[str, Any]:
        doc_id = str(arguments.get("doc_id", ""))
        document = self.documents.get(doc_id)
        if document is None:
            return {"status": "not_found", "doc_id": doc_id}
        return {
            "status": "ok",
            "doc_id": doc_id,
            "classification": document.get("classification"),
            "content": document.get("content", ""),
        }

    def _send_email(self, arguments: dict[str, Any]) -> dict[str, Any]:
        email = {
            "to": str(arguments.get("to", "")),
            "subject": str(arguments.get("subject", "")),
            "body": str(arguments.get("body", "")),
        }
        self.outbox.append(email)
        return {
            "status": "mock_sent",
            "message_id": f"mock-{len(self.outbox):04d}",
            "recipient": email["to"],
        }

