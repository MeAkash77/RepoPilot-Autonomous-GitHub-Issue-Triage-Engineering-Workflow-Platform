"""Tool contract tests with a mocked RepoPilot API (httpx MockTransport
is overkill here — we monkeypatch the client factory)."""

from typing import Any

import httpx
import pytest

from repopilot_mcp import server


class _MockClient:
    def __init__(self, routes: dict[str, Any]) -> None:
        self.routes = routes

    def __enter__(self) -> "_MockClient":
        return self

    def __exit__(self, *args: object) -> None:
        return None

    def _respond(self, path: str) -> httpx.Response:
        for prefix, payload in self.routes.items():
            if path.startswith(prefix):
                return httpx.Response(200, json=payload, request=httpx.Request("GET", path))
        return httpx.Response(404, json={}, request=httpx.Request("GET", path))

    def get(self, path: str, params: Any = None) -> httpx.Response:
        return self._respond(path)

    def post(self, path: str, json: Any = None) -> httpx.Response:
        return self._respond(path)


@pytest.fixture
def mock_api(monkeypatch: pytest.MonkeyPatch) -> dict[str, Any]:
    routes: dict[str, Any] = {}
    monkeypatch.setattr(server, "_client", lambda: _MockClient(routes))
    return routes


def test_list_pending_actions(mock_api: dict[str, Any]) -> None:
    mock_api["/api/v1/actions/pending"] = [{"id": 1, "action_type": "add_labels"}]
    assert server.list_pending_actions() == [{"id": 1, "action_type": "add_labels"}]


def test_approve_action(mock_api: dict[str, Any]) -> None:
    mock_api["/api/v1/actions/5/approve"] = {"id": 5, "status": "approved"}
    assert server.approve_action(5)["status"] == "approved"


def test_triage_status_finds_issue(mock_api: dict[str, Any]) -> None:
    mock_api["/api/v1/runs/9"] = {"id": 9, "issue_number": 42, "status": "completed"}
    mock_api["/api/v1/runs"] = {"items": [{"id": 9, "issue_number": 42}]}
    assert server.triage_status("a/b", 42)["status"] == "completed"


def test_triage_status_missing_issue(mock_api: dict[str, Any]) -> None:
    mock_api["/api/v1/runs"] = {"items": []}
    assert "error" in server.triage_status("a/b", 1)


def test_all_six_tools_registered() -> None:
    import asyncio

    tools = asyncio.run(server.mcp.list_tools())
    names = {tool.name for tool in tools}
    assert names == {
        "list_pending_actions",
        "approve_action",
        "reject_action",
        "triage_status",
        "search_repo_knowledge",
        "get_triage_analytics",
    }
