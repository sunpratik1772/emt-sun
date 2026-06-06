# MCP bridge for Studio workflows

> **Full guide:** [docs/mcp-integrations.md](../../docs/mcp-integrations.md) — where credentials live (`backend/.env`), all HTTP endpoints, every tool (demo vs live), how to change behavior, **Teams** (webhook done) and **Outlook** (Graph not implemented).

Studio's **MCP Tool** node calls `POST {MCP_SERVER_URL}/tools/{tool}/run`. Hermes Agent and OpenClaw instead spawn stdio MCP servers or connect to remote HTTP MCP endpoints. This bridge exposes Confluence → tasks, Confluence → Jira, and Jira → GitHub flows over the Studio HTTP contract.

## Studio MCP node (UI tokens)

In the canvas, select an **MCP Tool** node:

1. **Integration** dropdown — `atlassian` or `github`.
2. Paste tokens in the inspector (**password** fields are masked).
3. **Tool** dropdown — filtered by integration preset.
4. Run the workflow — credentials are sent to the bridge on each tool call (node config overrides `.env`).

Optional `.env` in `backend/` supplies defaults so you do not re-paste tokens on every node.

## Quick start (demo, no tokens)

```bash
cd backend
MCP_BRIDGE_MODE=demo MCP_BRIDGE_PORT=8765 python -m mcp_bridge.server
```

In another terminal:

```bash
export MCP_SERVER_URL=http://127.0.0.1:8765
cd backend
python -m pytest tests/test_mcp_integration_workflows.py -q
```

## Tokens to create (live integrations)

| Integration | What to create | Where | Env var(s) |
|-------------|----------------|-------|------------|
| **Atlassian (Confluence + Jira)** | API token (Cloud) or PAT (Server/DC) | [id.atlassian.com/manage-profile/security/api-tokens](https://id.atlassian.com/manage-profile/security/api-tokens) | `ATLASSIAN_EMAIL`, `ATLASSIAN_API_TOKEN`, `ATLASSIAN_SITE_URL` (e.g. `https://yourco.atlassian.net`) |
| **Atlassian Rovo MCP** (official remote) | OAuth via Atlassian; site admin may need to allow MCP | [Atlassian Rovo MCP docs](https://support.atlassian.com/rovo/docs/getting-started-with-the-atlassian-remote-mcp-server) | Bearer from OAuth flow → `ATLASSIAN_MCP_TOKEN` |
| **GitHub** | Fine-grained or classic PAT with `repo`, `issues`, `pull_requests` | GitHub → Settings → Developer settings → Personal access tokens | `GITHUB_TOKEN` or `GITHUB_PERSONAL_ACCESS_TOKEN` |
| **Hermes native MCP** | Same tokens in `~/.hermes/config.yaml` under `mcp_servers.*.env` | [Hermes MCP docs](https://hermes-agent.nousresearch.com/docs/user-guide/features/mcp) | per-server in YAML |
| **OpenClaw native MCP** | Same in `~/.openclaw/openclaw.json` → `mcp.servers` | [OpenClaw MCP config](https://documentation.openclaw.ai/gateway/configuration-reference#mcp) | `env` block or `${GITHUB_TOKEN}` substitution |

### Recommended MCP servers (Hermes / OpenClaw CLI)

```bash
# GitHub (stdio)
npx -y @modelcontextprotocol/server-github
# env: GITHUB_PERSONAL_ACCESS_TOKEN

# Atlassian (community Docker — used by OpenClaw atlassian-mcp skill)
docker run -i --rm \
  -e JIRA_URL=https://yourco.atlassian.net \
  -e JIRA_USERNAME=you@company.com \
  -e JIRA_API_TOKEN=*** \
  ghcr.io/sooperset/mcp-atlassian:latest
```

Studio does not spawn these processes today; point `MCP_SERVER_URL` at this bridge (demo tools) or at a gateway you run that wraps the same stdio servers.

## Tools exposed

| Tool | Purpose |
|------|---------|
| `confluence_search_pages` | List pages (demo: ENG/PROD fixtures) |
| `confluence_extract_action_items` | Parse `- [ ]` / `Action:` lines into task rows |
| `tasks_bulk_create` | Persist task rows (in-memory in demo) |
| `jira_create_issue` | Create issues from upstream rows |
| `jira_list_issues` | List issues (`project`, `status`, `max`) |
| `github_implement_fixes` | Branch + test file + PR metadata per issue |
| `github_list_commits` | Recent commits for repo activity briefings |

## Example workflows

- `backend/workflows/mcp_integrations/01_confluence_to_tasks.json`
- `backend/workflows/mcp_integrations/02_confluence_to_jira.json`
- `backend/workflows/mcp_integrations/03_jira_to_github_fixes.json`
