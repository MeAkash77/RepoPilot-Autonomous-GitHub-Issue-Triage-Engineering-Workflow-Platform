# MCP server setup (Claude Desktop / IDEs)

The MCP server exposes RepoPilot's triage state and approval queue as tools. It talks to the REST API only — approvals made from Claude Desktop go through the same guardrails and are recorded as feedback like any dashboard review.

## Tools

| Tool | Purpose |
| --- | --- |
| `list_pending_actions(repo?)` | Actions awaiting review |
| `approve_action(action_id)` | Approve → executes on GitHub |
| `reject_action(action_id, reason?)` | Reject, recorded as labeled feedback |
| `triage_status(repo, issue_number)` | Latest run: classification, duplicates, cost |
| `search_repo_knowledge(repo, query, k?)` | Hybrid search over the indexed corpus |
| `get_triage_analytics()` | Aggregate run/cost/approval stats |

## Claude Desktop

Add to `~/Library/Application Support/Claude/claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "repopilot": {
      "command": "uv",
      "args": ["run", "--project", "/path/to/RepoPilot", "repopilot-mcp"],
      "env": {
        "REPOPILOT_API_URL": "http://localhost:8000",
        "REPOPILOT_API_KEY": "<your key once deployed>"
      }
    }
  }
}
```

Restart Claude Desktop; the six tools appear under the `repopilot` server. Try: *"What triage actions are pending on my repos?"*

## Streamable HTTP (remote)

```bash
REPOPILOT_MCP_TRANSPORT=http uv run repopilot-mcp   # serves on :8000/mcp by default
```

`REPOPILOT_API_KEY` is sent as `X-API-Key`; enforcement happens at the API layer once deployed.
