"""RepoPilot MCP server.

Exposes triage state and the approval queue as MCP tools for Claude
Desktop / IDEs. All tools call the RepoPilot REST API — the MCP server
holds no database access, so it inherits the API's guardrails and audit
trail (approvals made from Claude Desktop record feedback like any other
reviewer).

Run (stdio, for Claude Desktop):
    uv run repopilot-mcp

Run (streamable HTTP):
    REPOPILOT_MCP_TRANSPORT=http uv run repopilot-mcp

Env:
    REPOPILOT_API_URL   default http://localhost:8000
    REPOPILOT_API_KEY   sent as X-API-Key (enforced once deployed)
"""

import os
from typing import Any

import httpx
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("repopilot")


def _client() -> httpx.Client:
    headers = {}
    if api_key := os.environ.get("REPOPILOT_API_KEY"):
        headers["X-API-Key"] = api_key
    return httpx.Client(
        base_url=os.environ.get("REPOPILOT_API_URL", "http://localhost:8000"),
        headers=headers,
        timeout=30,
    )


@mcp.tool()
def list_pending_actions(repo: str | None = None) -> list[dict[str, Any]]:
    """List proposed triage actions awaiting human review, optionally
    filtered to one repository (owner/name)."""
    with _client() as client:
        response = client.get("/api/v1/actions/pending", params={"repo": repo} if repo else None)
        response.raise_for_status()
        return response.json()  # type: ignore[no-any-return]


@mcp.tool()
def approve_action(action_id: int) -> dict[str, Any]:
    """Approve a pending action; it executes against GitHub immediately."""
    with _client() as client:
        response = client.post(f"/api/v1/actions/{action_id}/approve", json={"reviewer": "mcp"})
        response.raise_for_status()
        return response.json()  # type: ignore[no-any-return]


@mcp.tool()
def reject_action(action_id: int, reason: str = "") -> dict[str, Any]:
    """Reject a pending action. The rejection is stored as labeled
    feedback for the eval dataset."""
    with _client() as client:
        response = client.post(
            f"/api/v1/actions/{action_id}/reject",
            json={"reviewer": f"mcp{f' ({reason})' if reason else ''}"},
        )
        response.raise_for_status()
        return response.json()  # type: ignore[no-any-return]


@mcp.tool()
def triage_status(repo: str, issue_number: int) -> dict[str, Any]:
    """Latest triage run for an issue: classification, duplicates,
    related files, cost."""
    with _client() as client:
        response = client.get("/api/v1/runs", params={"repo": repo, "limit": 100})
        response.raise_for_status()
        for item in response.json()["items"]:
            if item["issue_number"] == issue_number:
                detail = client.get(f"/api/v1/runs/{item['id']}")
                detail.raise_for_status()
                return detail.json()  # type: ignore[no-any-return]
    return {"error": f"no triage run found for {repo}#{issue_number}"}


@mcp.tool()
def search_repo_knowledge(repo: str, query: str, k: int = 8) -> list[dict[str, Any]]:
    """Hybrid search (dense + full-text + rerank) over a repo's indexed
    issues, PRs, docs, and code."""
    with _client() as client:
        response = client.get("/api/v1/search", params={"repo": repo, "query": query, "k": k})
        response.raise_for_status()
        return response.json()  # type: ignore[no-any-return]


@mcp.tool()
def get_triage_analytics() -> dict[str, Any]:
    """Aggregate triage analytics: run counts, costs, latency,
    approval rates by action type, classification distribution."""
    with _client() as client:
        response = client.get("/api/v1/analytics/overview")
        response.raise_for_status()
        return response.json()  # type: ignore[no-any-return]


def main() -> None:
    transport = os.environ.get("REPOPILOT_MCP_TRANSPORT", "stdio")
    mcp.run(transport="streamable-http" if transport == "http" else "stdio")


if __name__ == "__main__":
    main()
