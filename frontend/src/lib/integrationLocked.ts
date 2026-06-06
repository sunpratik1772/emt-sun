import type { Workflow } from '../types'

/** MCP node types — credentials live in backend/.env. */
export const MCP_NODE_TYPES = new Set([
  'mcp',
  'jira_mcp',
  'confluence_mcp',
  'github_mcp',
])

/** MCP config keys stripped from saved workflows — credentials live in backend/.env. */
export const MCP_LOCKED_CONFIG_KEYS = new Set([
  'jiraSiteUrl',
  'jiraEmail',
  'jiraApiToken',
  'jiraProjectKey',
  'confluenceSiteUrl',
  'confluenceEmail',
  'confluenceApiToken',
  'confluenceSpaceKey',
  'githubToken',
  'githubRepo',
  'atlassianSiteUrl',
  'atlassianEmail',
  'atlassianApiToken',
])

export function isMcpNodeType(nodeType: string): boolean {
  return MCP_NODE_TYPES.has(nodeType)
}

export function stripLockedMcpConfig(workflow: Workflow): Workflow {
  return {
    ...workflow,
    nodes: workflow.nodes.map((n) => {
      if (!isMcpNodeType(n.type)) return n
      const cfg = { ...(n.config ?? {}) }
      for (const key of MCP_LOCKED_CONFIG_KEYS) {
        delete cfg[key]
      }
      return { ...n, config: cfg }
    }),
  }
}

export function filterLockedPatch(
  nodeType: string,
  patch: Record<string, unknown>,
): Record<string, unknown> {
  if (!isMcpNodeType(nodeType)) return patch
  const out = { ...patch }
  for (const key of MCP_LOCKED_CONFIG_KEYS) {
    delete out[key]
  }
  return out
}
