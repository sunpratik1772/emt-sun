# MCP integrations (live REST)

Provider-split code: **connectivity** (REST clients) + **tools** (workflow handlers).

**Full documentation:** [docs/mcp-integrations.md](../../../docs/mcp-integrations.md) — credentials in `backend/.env`, bridge endpoints, tool catalog (demo vs live), how to add tools, Teams/Outlook (non-MCP).

## Layout

```
integrations/mcp/
  github/     connectivity.py, tools.py  → GITHUB_TOOLS
  jira/       connectivity.py, tools.py  → JIRA_TOOLS
  confluence/ connectivity.py, tools.py → CONFLUENCE_TOOLS
  credentials.py
  registry.py
```

## Add a Jira tool

1. REST method in `jira/connectivity.py` if needed.
2. Handler in `jira/tools.py` → register in `JIRA_TOOLS`.
3. Optional demo handler in `mcp_bridge/tools.py` + `TOOL_REGISTRY` for offline mode.
4. Update `engine/mcp_nodes.py` and `engine/nodes/jira_mcp.yaml` enum.

## Environment (summary)

| Variable | Provider |
|----------|----------|
| `ATLASSIAN_SITE_URL`, `ATLASSIAN_EMAIL`, `ATLASSIAN_API_TOKEN` | Jira + Confluence |
| `CONFLUENCE_SPACE_KEY`, `JIRA_PROJECT_KEY` | Defaults |
| `GITHUB_TOKEN`, `GITHUB_REPO` | GitHub live tools |

HTTP bridge: `mcp_bridge/server.py` — `POST /tools/{name}/run`.
