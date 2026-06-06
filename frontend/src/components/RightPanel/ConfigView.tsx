/**
 * Right-panel inspector for the selected node (`rightPanelMode === 'config'`).
 *
 * It renders wiring, editable config fields, and node documentation from the
 * live NodeSpec registry. `classifyField` is the legacy fallback for
 * `contract.configSchema`; typed params from `/node-manifest` should be the
 * preferred path as the backend specs mature.
 */
import { useEffect, useMemo, useState } from 'react'
import {
  ArcIcon,
  Settings2,
  ChevronDown,
  ChevronRight,
  ArrowRight,
  ArrowLeftRight,
  Sliders,
  AlertTriangle,
  Eye,
} from '../../icons/arc'
import { Lock } from 'lucide-react'
import { api } from '../../services/api'
import type { WorkflowNode, WorkflowEdge, ValidationIssue } from '../../types'
import Shell, { Empty, SectionHeader } from './Shell'
import { useWorkflowStore } from '../../store/workflowStore'
import { useNodeRegistryStore, UNKNOWN_NODE_UI, type NodeType, type NodeContract, type NodeTypedSpec } from '../../nodes'
import { NODE_UI } from '../../nodes/generated'
import { issueForField, issuesForNode, nodeLevelIssues } from './configValidationUtils'

const EMPTY_CONFIG_CONTRACT: NodeContract = {
  description: '',
  inputs: {},
  outputs: {},
  configSchema: {},
  constraints: [],
}

/* -------------------------------------------------------------------------- */
/* Field inference — legacy fallback for older string-only contracts.         */
/* -------------------------------------------------------------------------- */
type FieldKind =
  | 'input-ref'
  | 'output-name'
  | 'boolean'
  | 'number'
  | 'string'
  | 'password'
  | 'textarea'
  | 'starlark'
  | 'stringEnum'
  | 'stringArray'
  | 'json'

interface FieldDescriptor {
  key: string
  hint: string
  kind: FieldKind
  enumValues?: readonly string[]
  /** From NodeSpec param `default`; used to populate the inspector when config omits the key. */
  defaultValue?: unknown
  /** Per output column — when include_in_tab is false, label as context-only (spreadsheet tab hint). */
  columnIncludeInTab?: Record<string, boolean>
  visibleIf?: Record<string, string | readonly string[]>
  lockedFromEnv?: boolean
  envKey?: string
}

/** MCP tools shown per integration preset (Studio inspector dropdown). */
const MCP_TOOLS_BY_INTEGRATION: Record<string, readonly string[]> = {
  jira: [
    'jira_create_issue',
    'jira_list_issues',
    'jira_create_epics_from_confluence',
    'tasks_bulk_create',
  ],
  confluence: [
    'confluence_publish_report',
    'studio_publish_architecture_doc',
    'confluence_search_pages',
    'confluence_extract_action_items',
  ],
  atlassian: [
    'confluence_publish_report',
    'studio_publish_architecture_doc',
    'jira_create_epics_from_confluence',
    'jira_list_issues',
    'jira_create_issue',
    'confluence_search_pages',
    'confluence_extract_action_items',
  ],
  github: ['github_list_commits', 'github_fix_jira_and_update', 'github_implement_fixes'],
  git: ['github_list_commits', 'github_fix_jira_and_update', 'github_implement_fixes'],
}

function paramVisible(
  visibleIf: Record<string, string | readonly string[]> | undefined,
  cfg: Record<string, unknown>,
): boolean {
  if (!visibleIf) return true
  for (const [key, expected] of Object.entries(visibleIf)) {
    const actual = cfg[key]
    if (Array.isArray(expected)) {
      if (!expected.includes(String(actual))) return false
    } else if (String(actual) !== String(expected)) {
      return false
    }
  }
  return true
}

type ParamSpec = NodeTypedSpec['params'][number]
interface DataSourceColumn { name: string; type?: string; description?: string; semantic?: string; include_in_tab?: boolean }
interface DataSourceMeta { id: string; columns: DataSourceColumn[] }

function classifyField(key: string, hint: string): FieldDescriptor {
  const h = hint.toLowerCase()
  if (key === 'input_name' || key.endsWith('_input_name') || key === 'input') return { key, hint, kind: 'input-ref' }
  if (key === 'output_name' || key.endsWith('_output_name')) return { key, hint, kind: 'output-name' }
  if (key === 'system_prompt' || key === 'prompt_template' || key === 'llm_prompt_template') return { key, hint, kind: 'textarea' }
  if (h.startsWith('boolean')) return { key, hint, kind: 'boolean' }
  if (h.startsWith('number') || h.startsWith('integer') || h.startsWith('int')) return { key, hint, kind: 'number' }
  if (h.startsWith('array of strings') || h.startsWith('list of strings') || h.startsWith('list[str]')) return { key, hint, kind: 'stringArray' }
  if (h.startsWith('object') || h.startsWith('array') || h.startsWith('list')) return { key, hint, kind: 'json' }
  const enums = Array.from(hint.matchAll(/'([^']+)'/g)).map((m) => m[1])
  if (h.startsWith('string') && enums.length >= 2) return { key, hint, kind: 'stringEnum', enumValues: enums }
  return { key, hint, kind: 'string' }
}

function fieldFromParam(param: ParamSpec): FieldDescriptor {
  const key = param.name
  const hint = param.description
  const dv = param.default
  const visibleIf = param.visible_if as Record<string, string | readonly string[]> | undefined
  const base = {
    visibleIf,
    lockedFromEnv: Boolean(param.locked_from_env),
    envKey: param.env_key,
  }
  if (param.widget === 'input_ref' || param.type === 'input_ref') {
    return { key, hint, kind: 'input-ref', defaultValue: dv, ...base }
  }
  if (key === 'output_name' || key.endsWith('_output_name')) {
    return { key, hint, kind: 'output-name', defaultValue: dv, ...base }
  }
  if (param.widget === 'password') return { key, hint, kind: 'password', defaultValue: dv, ...base }
  if (param.widget === 'checkbox' || param.type === 'boolean') {
    return { key, hint, kind: 'boolean', defaultValue: dv, ...base }
  }
  if (param.widget === 'number' || param.type === 'number' || param.type === 'integer') {
    return { key, hint, kind: 'number', defaultValue: dv, ...base }
  }
  if (param.widget === 'select' || param.type === 'enum') {
    return { key, hint, kind: 'stringEnum', enumValues: param.enum ?? [], defaultValue: dv, ...base }
  }
  if (Array.isArray(param.enum) && param.enum.length > 0) {
    return { key, hint, kind: 'stringEnum', enumValues: param.enum, defaultValue: dv, ...base }
  }
  if (param.widget === 'chips' || param.type === 'string_list') {
    return { key, hint, kind: 'stringArray', defaultValue: dv, ...base }
  }
  if (param.widget === 'starlark' || param.widget === 'starlark_editor') {
    return { key, hint, kind: 'starlark', defaultValue: dv, ...base }
  }
  if (param.type === 'code' && param.widget !== 'textarea') {
    return { key, hint, kind: 'starlark', defaultValue: dv, ...base }
  }
  if (param.widget === 'textarea' || param.widget === 'code') {
    return { key, hint, kind: 'textarea', defaultValue: dv, ...base }
  }
  if (param.widget === 'json' || param.type === 'object' || param.type === 'array') {
    return { key, hint, kind: 'json', defaultValue: dv, ...base }
  }
  return { key, hint, kind: 'string', defaultValue: dv, ...base }
}

interface UpstreamOutput { producerId: string; producerType: string; name: string }

function computeUpstream(node: WorkflowNode, nodes: WorkflowNode[], edges: WorkflowEdge[]): UpstreamOutput[] {
  const byId = new Map(nodes.map((n) => [n.id, n]))
  const seen = new Set<string>()
  const order: string[] = []
  const queue = edges.filter((e) => e.to === node.id).map((e) => e.from)
  while (queue.length) {
    const id = queue.shift()!
    if (seen.has(id)) continue
    seen.add(id)
    order.push(id)
    for (const e of edges) if (e.to === id && !seen.has(e.from)) queue.push(e.from)
  }
  const out: UpstreamOutput[] = []
  for (const id of order) {
    const n = byId.get(id)
    if (!n) continue
    const name = (n.config as Record<string, unknown>)?.output_name
    if (typeof name === 'string' && name.trim()) {
      out.push({ producerId: n.id, producerType: n.type, name })
    }
  }
  return out
}

function sourceIdsForNode(type: string, cfg: Record<string, unknown>): string[] {
  if (type === 'DB_SOLR_CONNECTOR') {
    return [typeof cfg.table === 'string' && cfg.table ? cfg.table : 'hs_alerts']
  }
  if (type === 'DB_MARKET_CONNECTOR') return ['market_ticks']
  if (type === 'MARKET_API_CONNECTOR') {
    const raw = cfg.datasets
    if (Array.isArray(raw) && raw.length) return raw.map(String)
    if (typeof raw === 'string' && raw.trim()) return raw.split(',').map((s) => s.trim()).filter(Boolean)
    return ['comms_messages']
  }
  return []
}

function columnMetaForNode(
  type: string,
  cfg: Record<string, unknown>,
  dataSources: DataSourceMeta[],
): { names: string[]; includeTab: Record<string, boolean> } {
  const byId = new Map(dataSources.map((source) => [source.id, source]))
  const seen = new Set<string>()
  const names: string[] = []
  const includeTab: Record<string, boolean> = {}
  for (const id of sourceIdsForNode(type, cfg)) {
    const source = byId.get(id)
    for (const column of source?.columns ?? []) {
      if (!column.name || seen.has(column.name)) continue
      seen.add(column.name)
      names.push(column.name)
      const incl = column.include_in_tab !== false
      includeTab[column.name] = includeTab[column.name] === undefined ? incl : includeTab[column.name] && incl
    }
  }
  return { names, includeTab }
}

/* -------------------------------------------------------------------------- */
/* Group — collapsible labelled section inside the Config view.               */
/* -------------------------------------------------------------------------- */
function Group({
  title, count, defaultOpen = true, children,
}: { title: string; count?: number; defaultOpen?: boolean; children: React.ReactNode }) {
  const [open, setOpen] = useState(defaultOpen)
  return (
    <div style={{ borderBottom: '1px solid var(--border-soft)' }}>
      <button
        onClick={() => setOpen((v) => !v)}
        className="w-full flex items-center gap-2 px-4 py-2.5 text-left"
        style={{ background: 'transparent', cursor: 'pointer' }}
      >
        {open ? <ArcIcon icon={ChevronDown} size={12} style={{ color: 'var(--text-3)' }} /> : <ArcIcon icon={ChevronRight} size={12} style={{ color: 'var(--text-3)' }} />}
        <span
          className="font-mono"
          style={{ fontSize: 10, letterSpacing: '0.12em', textTransform: 'uppercase', color: 'var(--text-2)' }}
        >
          {title}
        </span>
        {count != null && (
          <span className="num" style={{ fontSize: 10, color: 'var(--text-3)' }}>
            {count}
          </span>
        )}
      </button>
      {open && <div className="px-4 pb-3">{children}</div>}
    </div>
  )
}

/* -------------------------------------------------------------------------- */
/* Port row — uniform layout for both inputs (←) and outputs (→).             */
/* -------------------------------------------------------------------------- */
function PortRow({
  name, dir, hint, wireName, wireColor,
}: {
  name: string
  dir: 'in' | 'out'
  hint: string
  wireName?: string | null
  wireColor: string
}) {
  return (
    <div
      className="rounded-md p-2 mb-1.5"
      style={{ background: 'var(--bg-0)', border: '1px solid var(--border-soft)' }}
    >
      <div className="flex items-center gap-1.5" style={{ fontSize: 11 }}>
        <span style={{ color: 'var(--text-3)' }}>{dir === 'in' ? '←' : '→'}</span>
        <span className="num" style={{ color: 'var(--text-1)', fontWeight: 500 }}>{name}</span>
        {wireName && (
          <>
            <ArcIcon icon={ArrowRight} size={10} strokeWidth={2} style={{ color: 'var(--text-3)' }} />
            <span
              className="num"
              style={{
                fontSize: 10.5, padding: '1px 6px', borderRadius: 4,
                color: 'var(--text-0)',
                background: `color-mix(in srgb, ${wireColor} 12%, transparent)`,
                border: `1px solid color-mix(in srgb, ${wireColor} 30%, transparent)`,
              }}
            >
              {wireName}
            </span>
          </>
        )}
      </div>
      {hint && (
        <div className="mt-1" style={{ fontSize: 10.5, color: 'var(--text-2)', lineHeight: 1.5 }}>
          {hint}
        </div>
      )}
    </div>
  )
}

/* -------------------------------------------------------------------------- */
/* Param row — label + control + hint.                                        */
/* -------------------------------------------------------------------------- */
const inputStyle: React.CSSProperties = {
  width: '100%',
  fontSize: 11.5,
  color: 'var(--text-0)',
  background: 'var(--bg-0)',
  border: '1px solid var(--border)',
  borderRadius: 7,
  padding: '6px 8px',
  fontFamily: 'inherit',
}

function LockedParamRow({
  field,
  displayValue,
  envKey,
}: {
  field: FieldDescriptor
  displayValue: string
  envKey?: string
}) {
  return (
    <div className="mb-2.5 config-locked-field">
      <div className="flex items-center justify-between mb-1 gap-2">
        <span className="num flex items-center gap-1" style={{ fontSize: 10.5, color: 'var(--text-1)', fontWeight: 600 }}>
          <Lock size={10} style={{ color: 'var(--text-3)' }} aria-hidden />
          {field.key}
        </span>
        <span
          className="font-mono config-locked-field__badge"
          style={{ fontSize: 9, letterSpacing: '0.08em', textTransform: 'uppercase' }}
        >
          locked · .env
        </span>
      </div>
      <div
        className="config-locked-field__value rounded-md px-2 py-1.5 font-mono"
        title={envKey ? `Set in backend/.env as ${envKey}` : 'Set in backend/.env'}
      >
        {displayValue || '(not set in backend/.env)'}
      </div>
      {field.hint && (
        <p className="mt-1" style={{ fontSize: 10.5, color: 'var(--text-2)', lineHeight: 1.5 }}>
          {field.hint}
        </p>
      )}
    </div>
  )
}

function ParamRow({
  field, value, upstream, onChange, nodeIssues = [],
}: {
  field: FieldDescriptor
  value: unknown
  upstream: UpstreamOutput[]
  onChange: (v: unknown) => void
  nodeIssues?: ValidationIssue[]
}) {
  const fieldIssue = issueForField(nodeIssues, field.key)
  const isError = fieldIssue?.severity === 'error'
  const isWarning = fieldIssue?.severity === 'warning'
  const ringColor = isError ? 'var(--danger)' : isWarning ? 'var(--warning)' : 'transparent'

  return (
    <div className="mb-2.5">
      <div className="flex items-center justify-between mb-1">
        <span className="num" style={{ fontSize: 10.5, color: 'var(--text-1)', fontWeight: 600, letterSpacing: 0 }}>
          {field.key}
        </span>
        <span
          className="font-mono"
          style={{ fontSize: 9, letterSpacing: '0.1em', textTransform: 'uppercase', color: 'var(--text-3)' }}
        >
          {field.kind === 'input-ref' ? 'wire' : field.kind}
        </span>
      </div>
      <div
        className="rounded-md"
        style={{
          padding: ringColor === 'transparent' ? 0 : 2,
          border: `1px solid ${ringColor}`,
          background: isError
            ? 'color-mix(in srgb, var(--danger) 6%, transparent)'
            : isWarning
              ? 'color-mix(in srgb, var(--warning) 6%, transparent)'
              : 'transparent',
        }}
      >
        <ParamInput field={field} value={value} upstream={upstream} onChange={onChange} />
      </div>
      {fieldIssue && (
        <p
          className="mt-1 flex items-start gap-1.5"
          style={{
            fontSize: 10.5,
            color: isError ? 'var(--danger)' : 'var(--warning)',
            lineHeight: 1.45,
          }}
        >
          <AlertTriangle size={11} className="shrink-0 mt-0.5" />
          <span>{fieldIssue.message}</span>
        </p>
      )}
      {!fieldIssue && field.hint && (
        <p className="mt-1" style={{ fontSize: 10.5, color: 'var(--text-2)', lineHeight: 1.5 }}>{field.hint}</p>
      )}
    </div>
  )
}

function resolveDisplayValue(field: FieldDescriptor, raw: unknown): unknown {
  if (raw !== undefined && raw !== null) {
    if (field.kind === 'stringEnum' && raw === '') {
      return field.defaultValue !== undefined ? field.defaultValue : raw
    }
    return raw
  }
  return field.defaultValue !== undefined ? field.defaultValue : raw
}

function formatStarlarkCode(raw: string): string {
  const normalized = raw.replace(/\r\n?/g, '\n')
  const lines = normalized.split('\n').map((line) => line.replace(/\t/g, '    ').replace(/[ \t]+$/g, ''))
  const compacted: string[] = []
  let blankRun = 0
  for (const line of lines) {
    if (line.trim() === '') {
      blankRun += 1
      if (blankRun <= 2) compacted.push('')
      continue
    }
    blankRun = 0
    compacted.push(line)
  }
  return compacted.join('\n').trimEnd()
}

function formatPythonCode(raw: string): string {
  return formatStarlarkCode(raw)
}

function ParamInput({ field, value, upstream, onChange }: {
  field: FieldDescriptor
  value: unknown
  upstream: UpstreamOutput[]
  onChange: (v: unknown) => void
}) {
  const v = resolveDisplayValue(field, value)
  if (field.kind === 'input-ref') {
    const current = typeof v === 'string' ? v : ''
    return (
      <div className="space-y-1.5">
        {upstream.length > 0 ? (
          <select
            value={upstream.some((u) => u.name === current) ? current : ''}
            onChange={(e) => onChange(e.target.value || null)}
            style={inputStyle}
          >
            <option value="">— upstream output —</option>
            {upstream.map((u) => (
              <option key={`${u.producerId}:${u.name}`} value={u.name}>
                {u.name} · {u.producerId}
              </option>
            ))}
          </select>
        ) : null}
        <input
          type="text"
          value={current}
          onChange={(e) => onChange(e.target.value)}
          placeholder="dataset name…"
          style={{ ...inputStyle, fontSize: 11 }}
        />
      </div>
    )
  }
  if (field.kind === 'boolean') {
    return (
      <label className="flex items-center gap-2 cursor-pointer" style={{ fontSize: 11.5, color: 'var(--text-1)' }}>
        <input type="checkbox" checked={v === true} onChange={(e) => onChange(e.target.checked)} style={{ width: 14, height: 14 }} />
        <span>{v === true ? 'true' : 'false'}</span>
      </label>
    )
  }
  if (field.kind === 'number') {
    const num = typeof v === 'number' ? v : v == null || v === '' ? '' : Number(v)
    return (
      <input
        type="number"
        value={num === '' || Number.isNaN(num) ? '' : num}
        onChange={(e) => onChange(e.target.value === '' ? null : Number(e.target.value))}
        style={inputStyle}
      />
    )
  }
  if (field.kind === 'stringEnum' && field.enumValues) {
    return (
      <select value={typeof v === 'string' ? v : ''} onChange={(e) => onChange(e.target.value || null)} style={inputStyle}>
        <option value="">— choose —</option>
        {field.enumValues.map((opt) => <option key={opt} value={opt}>{opt}</option>)}
      </select>
    )
  }
  if (field.kind === 'stringArray') {
    const arr = Array.isArray(v) ? v : []
    if (field.enumValues?.length) {
      const selected = arr.length ? new Set(arr.map(String)) : new Set(field.enumValues)
      const allSelected = field.enumValues.every((option) => selected.has(option))
      const tabMap = field.columnIncludeInTab
      return (
        <div className="space-y-1.5">
          <label className="flex items-center gap-2 cursor-pointer" style={{ fontSize: 11, color: 'var(--text-1)' }}>
            <input
              type="checkbox"
              checked={allSelected}
              onChange={(e) => {
                if (e.target.checked) onChange([...(field.enumValues ?? [])])
                else onChange([])
              }}
              style={{ width: 13, height: 13 }}
            />
            <span>{allSelected ? 'All columns selected' : 'Use all columns (default)'}</span>
          </label>
          <div
            className="rounded-md"
            style={{
              maxHeight: 180,
              overflow: 'auto',
              background: 'var(--bg-0)',
              border: '1px solid var(--border-soft)',
              padding: 6,
            }}
          >
            {field.enumValues.map((option) => {
              const inTab = tabMap ? tabMap[option] !== false : true
              return (
              <label key={option} className="flex items-center gap-2 cursor-pointer py-1" style={{ fontSize: 11, color: 'var(--text-1)' }}>
                <input
                  type="checkbox"
                  checked={selected.has(option)}
                  onChange={(e) => {
                    const next = new Set(arr.length ? arr.map(String) : field.enumValues)
                    if (e.target.checked) next.add(option)
                    else next.delete(option)
                    onChange(Array.from(next))
                  }}
                  style={{ width: 13, height: 13 }}
                />
                <span className="num">{option}</span>
                {!inTab && (
                  <span style={{ fontSize: 9, color: 'var(--text-3)' }}>· context-only</span>
                )}
              </label>
              )
            })}
          </div>
          <div style={{ fontSize: 10, color: 'var(--text-3)' }}>
            Empty selection returns all schema columns at runtime. Columns marked context-only are typically omitted from Excel-style tabs.
          </div>
        </div>
      )
    }
    return (
      <input
        type="text"
        value={arr.join(', ')}
        onChange={(e) => onChange(e.target.value.split(',').map((s) => s.trim()).filter(Boolean))}
        placeholder="comma-separated"
        style={inputStyle}
      />
    )
  }
  if (field.kind === 'starlark') {
    const textValue = typeof v === 'string' ? v : ''
    return (
      <div className="space-y-1.5">
        <div
          className="flex items-center justify-between gap-2 px-2 py-1 rounded"
          style={{
            background: 'color-mix(in srgb, #06b6d4 12%, var(--bg-0))',
            border: '1px solid color-mix(in srgb, #06b6d4 35%, var(--border-soft))',
          }}
        >
          <span className="font-mono" style={{ fontSize: 9.5, letterSpacing: '0.12em', color: '#06b6d4', textTransform: 'uppercase' }}>
            Starlark · sandboxed
          </span>
          <button
            type="button"
            onClick={() => {
              const formatted = formatStarlarkCode(textValue)
              if (formatted !== textValue) onChange(formatted)
            }}
            style={{
              fontSize: 10,
              color: 'var(--text-1)',
              background: 'var(--bg-0)',
              border: '1px solid var(--border-soft)',
              borderRadius: 6,
              padding: '3px 8px',
              cursor: 'pointer',
            }}
          >
            Format
          </button>
        </div>
        <textarea
          value={textValue}
          onChange={(e) => onChange(e.target.value)}
          rows={Math.min(28, Math.max(12, String(textValue ?? '').split('\n').length + 2))}
          spellCheck={false}
          style={{
            ...inputStyle,
            resize: 'vertical',
            minHeight: 240,
            lineHeight: 1.65,
            tabSize: 4,
            whiteSpace: 'pre',
            overflowWrap: 'normal',
            fontFamily: 'inherit',
            fontSize: 12,
            color: '#e0f2fe',
            background: 'linear-gradient(180deg, #0c1929 0%, #071018 100%)',
            border: '2px solid color-mix(in srgb, #06b6d4 55%, var(--border))',
            boxShadow: '0 0 0 1px color-mix(in srgb, #06b6d4 20%, transparent), inset 0 1px 0 color-mix(in srgb, #fff 4%, transparent)',
            letterSpacing: 0.15,
          }}
        />
      </div>
    )
  }
  if (field.kind === 'textarea') {
    const isCode = field.key === 'pythonCode'
    const textValue = typeof v === 'string' ? v : ''
    return (
      <div className="space-y-1.5">
        {isCode && (
          <div className="flex items-center justify-end">
            <button
              type="button"
              onClick={() => {
                const formatted = formatPythonCode(textValue)
                if (formatted !== textValue) onChange(formatted)
              }}
              style={{
                fontSize: 10,
                color: 'var(--text-1)',
                background: 'var(--bg-0)',
                border: '1px solid var(--border-soft)',
                borderRadius: 6,
                padding: '3px 8px',
                cursor: 'pointer',
              }}
            >
              Format Python
            </button>
          </div>
        )}
        <textarea
          value={textValue}
          onChange={(e) => onChange(e.target.value)}
          rows={Math.min(isCode ? 24 : 14, Math.max(isCode ? 10 : 5, String(textValue ?? '').split('\n').length))}
          spellCheck={false}
          style={{
            ...inputStyle,
            resize: 'vertical',
            minHeight: isCode ? 220 : 120,
            lineHeight: 1.6,
            tabSize: 4,
            whiteSpace: 'pre',
            overflowWrap: 'normal',
            letterSpacing: isCode ? 0.1 : 0,
          }}
        />
      </div>
    )
  }
  if (field.kind === 'password') {
    return (
      <input
        type="password"
        value={typeof v === 'string' ? v : ''}
        onChange={(e) => onChange(e.target.value)}
        placeholder="Paste API token…"
        autoComplete="off"
        style={inputStyle}
      />
    )
  }
  if (field.kind === 'output-name' || field.kind === 'string') {
    return (
      <input
        type="text"
        value={typeof v === 'string' ? v : ''}
        onChange={(e) => onChange(e.target.value)}
        style={inputStyle}
      />
    )
  }
  // JSON fallback
  const text = v === undefined ? '' : JSON.stringify(v, null, 2)
  return (
    <textarea
      value={text}
      onChange={(e) => {
        const trimmed = e.target.value.trim()
        if (trimmed === '') { onChange(null); return }
        try { onChange(JSON.parse(trimmed)) } catch { /* ignore until valid */ }
      }}
      rows={Math.min(8, Math.max(3, text.split('\n').length))}
      spellCheck={false}
      style={{ ...inputStyle, resize: 'vertical', minHeight: 60 }}
    />
  )
}

/* -------------------------------------------------------------------------- */
/* Main view                                                                  */
/* -------------------------------------------------------------------------- */
export default function ConfigView() {
  const workflow = useWorkflowStore((s) => s.workflow)
  const selectedId = useWorkflowStore((s) => s.selectedNodeId)
  const updateNodeConfig = useWorkflowStore((s) => s.updateNodeConfig)
  const renameNode = useWorkflowStore((s) => s.renameNode)
  const runLog = useWorkflowStore((s) => s.runLog)
  const validationIssues = useWorkflowStore((s) => s.validationIssues)
  const runWarnings = useWorkflowStore((s) => s.runWarnings)
  const [dataSources, setDataSources] = useState<DataSourceMeta[]>([])
  const [integrationEnv, setIntegrationEnv] = useState<Record<string, string>>({})

  useEffect(() => {
    let alive = true
    api
      .getIntegrationEnv()
      .then((payload) => {
        if (alive) setIntegrationEnv(payload.mcp ?? {})
      })
      .catch(() => {
        if (alive) setIntegrationEnv({})
      })
    return () => {
      alive = false
    }
  }, [])

  const node = useMemo(
    () => workflow?.nodes.find((n) => n.id === selectedId) ?? null,
    [workflow, selectedId],
  )

  const meta = useNodeRegistryStore((s) =>
    node ? (s.nodeUI[node.type as NodeType] ?? UNKNOWN_NODE_UI) : UNKNOWN_NODE_UI,
  )
  const contract = useNodeRegistryStore((s) =>
    node ? (s.nodeContracts[node.type as NodeType] ?? EMPTY_CONFIG_CONTRACT) : EMPTY_CONFIG_CONTRACT,
  )
  const typedSpec = useNodeRegistryStore((s) =>
    node ? s.nodeTyped[node.type as NodeType] : undefined,
  )

  const nodeIssues = useMemo(
    () => (node ? issuesForNode(node.id, validationIssues, runWarnings) : []),
    [node, validationIssues, runWarnings],
  )
  const generalIssues = useMemo(() => nodeLevelIssues(nodeIssues), [nodeIssues])

  useEffect(() => {
    let alive = true
    fetch('/api/data-sources')
      .then((res) => (res.ok ? res.json() : { data_sources: [] }))
      .then((payload) => {
        if (alive) setDataSources(Array.isArray(payload.data_sources) ? payload.data_sources : [])
      })
      .catch(() => {
        if (alive) setDataSources([])
      })
    return () => {
      alive = false
    }
  }, [])

  if (!node) {
    return (
      <Shell icon={Settings2} title="Config" eyebrow="INSPECTOR" accent="var(--text-1)">
        <Empty>
          <ArcIcon icon={Settings2} size={20} strokeWidth={1.6} style={{ color: 'var(--text-3)', marginBottom: 8 }} />
          <div style={{ color: 'var(--text-1)', fontWeight: 500, marginBottom: 4 }}>No node selected</div>
          <div>Click a node on the canvas to edit its config.</div>
        </Empty>
      </Shell>
    )
  }
  const upstream = workflow ? computeUpstream(node, workflow.nodes, workflow.edges) : []
  const cfg = (node.config ?? {}) as Record<string, unknown>
  const rawFields = typedSpec?.params.length
    ? typedSpec.params
        .map(fieldFromParam)
        .filter((field) => paramVisible(field.visibleIf, cfg))
    : Object.entries(contract.configSchema).map(([k, v]) => classifyField(k, v))

  const columnMeta = columnMetaForNode(node.type, cfg, dataSources)
  const rawIntegration = String(cfg.integration ?? 'atlassian')
  const integration =
    rawIntegration === 'studio_bridge'
      ? 'atlassian'
      : rawIntegration === 'git'
        ? 'github'
        : rawIntegration
  const fields = rawFields.map((field) => {
    if (field.key === 'output_columns' && columnMeta.names.length) {
      return {
        ...field,
        enumValues: columnMeta.names,
        kind: 'stringArray' as const,
        columnIncludeInTab: columnMeta.includeTab,
      }
    }
    if (node.type === 'mcp' && field.key === 'tool') {
      const tools = MCP_TOOLS_BY_INTEGRATION[integration] ?? field.enumValues ?? []
      return { ...field, enumValues: tools }
    }
    return field
  })
  const promptFields = fields.filter((f) => f.key === 'system_prompt' || f.key === 'prompt_template' || f.key === 'llm_prompt_template')
  const llmSettingFields = fields.filter((f) => ['use_llm', 'model', 'temperature', 'max_output_tokens'].includes(f.key))
  const codePythonField = fields.find((f) => f.key === 'pythonCode')
  const codeStarlarkField = fields.find((f) => f.key === 'code' && (f.kind === 'starlark' || node.type === 'code'))
  const codeSummaryField =
    fields.find((f) => f.key === 'code_summary') ??
    (node.type === 'code'
      ? {
          key: 'code_summary',
          hint: 'Plain-language explanation for non-technical readers.',
          kind: 'textarea' as const,
        }
      : undefined)
  const starlarkCodeFieldKeys = new Set(
    [codeStarlarkField, codeSummaryField].filter((f): f is FieldDescriptor => Boolean(f)).map((f) => f.key),
  )
  const specialFieldKeys = new Set([
    ...promptFields.map((f) => f.key),
    ...llmSettingFields.map((f) => f.key),
    ...starlarkCodeFieldKeys,
  ])
  const nonPromptFields = fields.filter((f) => !specialFieldKeys.has(f.key))
  const lockedEnvFields = nonPromptFields.filter((f) => f.lockedFromEnv)
  const editableNonPromptFields = nonPromptFields.filter((f) => !f.lockedFromEnv)
  const codeReturnField = fields.find((f) => f.key === 'return_type')
  const codeParamsField = fields.find((f) => f.key === 'params')
  const codeCommentField = fields.find((f) => f.key === 'comment')
  const codeModeField = fields.find((f) => f.key === 'mode')
  const responsePrimaryFields = ['summary_input_key', 'order_tab_prefix', 'overall_tab_name']
    .map((k) => fields.find((f) => f.key === k))
    .filter((f): f is FieldDescriptor => Boolean(f))
  const responseEnvelopeField = fields.find((f) => f.key === 'envelope_key')
  const responseAdvancedFields = [
    'summary_tab_field',
    'summary_text_field',
    'artifact_path',
    'alert_id',
    'artifact_key',
    'alert_id_key',
    'order_summary_key',
    'overall_summary_key',
    'llm_summary_key',
    'static_fields',
  ]
    .map((k) => fields.find((f) => f.key === k))
    .filter((f): f is FieldDescriptor => Boolean(f))
  const inputName = typeof cfg.input_name === 'string' ? cfg.input_name : null
  const outputName = typeof cfg.output_name === 'string' ? cfg.output_name : null
  const inputs = Object.entries(contract.inputs)
  const outputs = Object.entries(contract.outputs)

  const lastRun = [...runLog].reverse().find((e) => e.node_id === node.id)
  const accent = meta?.color ?? 'var(--text-1)'

  const contractDescription = contract.description || meta?.description || '—'
  const inspectorDescription =
    node.type === 'code'
      ? (NODE_UI.code?.description ??
        'Run sandboxed Starlark on incoming rows. Assign results to `output` (or legacy `result`).')
      : node.type === 'CODE' && /javascript/i.test(contractDescription)
        ? (NODE_UI.code?.description ??
          'Write custom Python executed against workflow items. Use `return_type` and `params` to describe output shape and sandbox inputs; optional `comment` for a short note.')
        : contractDescription

  const subtitle = (
    <div className="flex items-center gap-2 flex-wrap">
      <span
        className="num rounded px-1.5"
        style={{
          fontSize: 10.5, color: 'var(--text-1)',
          background: 'var(--bg-0)', border: '1px solid var(--border-soft)',
        }}
      >
        {node.id}
      </span>
      <span style={{ color: 'var(--text-3)' }}>·</span>
      <span className="font-mono" style={{ fontSize: 10, letterSpacing: '0.14em', textTransform: 'uppercase', color: accent }}>
        {node.type.replace(/_/g, ' ')}
      </span>
    </div>
  )

  return (
    <Shell
      icon={meta?.Icon ?? Settings2}
      title={node.label}
      eyebrow="CONFIG"
      accent={accent}
      subtitle={subtitle}
    >
      <div className="px-4 py-3" style={{ borderBottom: '1px solid var(--border-soft)' }}>
        <SectionHeader>Description</SectionHeader>
        <p style={{ fontSize: 11.5, color: 'var(--text-1)', lineHeight: 1.55 }}>
          {inspectorDescription}
        </p>
        <input
          type="text"
          value={node.label}
          onChange={(e) => renameNode(node.id, e.target.value)}
          placeholder="Label"
          className="mt-2"
          style={inputStyle}
        />
      </div>

      {nodeIssues.length > 0 && (
        <div
          className="px-4 py-3"
          style={{
            borderBottom: '1px solid var(--border-soft)',
            background: 'color-mix(in srgb, var(--danger) 8%, var(--bg-1))',
          }}
        >
          <SectionHeader accent="var(--danger)">Validation</SectionHeader>
          <ul className="space-y-1.5" style={{ fontSize: 11, color: 'var(--text-1)', lineHeight: 1.45 }}>
            {generalIssues.map((issue, idx) => (
              <li key={`${issue.code}-${idx}`} className="flex items-start gap-1.5">
                <AlertTriangle size={11} className="shrink-0 mt-0.5" style={{ color: 'var(--danger)' }} />
                <span>{issue.message}</span>
              </li>
            ))}
            {nodeIssues
              .filter((issue) => issue.field)
              .map((issue, idx) => (
                <li key={`${issue.field}-${idx}`} className="flex items-start gap-1.5">
                  <AlertTriangle
                    size={11}
                    className="shrink-0 mt-0.5"
                    style={{ color: issue.severity === 'error' ? 'var(--danger)' : 'var(--warning)' }}
                  />
                  <span>
                    <span className="num" style={{ color: 'var(--text-2)' }}>{issue.field}: </span>
                    {issue.message}
                  </span>
                </li>
              ))}
          </ul>
        </div>
      )}

      <Group title="Ports" count={inputs.length + outputs.length}>
        <div className="flex items-center gap-1.5 mb-2" style={{ fontSize: 10, color: 'var(--text-3)' }}>
          <ArcIcon icon={ArrowLeftRight} size={11} />
          <span className="font-mono" style={{ letterSpacing: '0.18em', textTransform: 'uppercase' }}>Inputs</span>
        </div>
        {inputs.length === 0
          ? <div style={{ fontSize: 11, color: 'var(--text-3)', marginBottom: 8 }}>None</div>
          : inputs.map(([k, v]) => (
              <PortRow
                key={k}
                name={k}
                dir="in"
                hint={v}
                wireName={k.startsWith('datasets[') ? inputName : null}
                wireColor="var(--info)"
              />
            ))}
        <div className="flex items-center gap-1.5 mb-2 mt-3" style={{ fontSize: 10, color: 'var(--text-3)' }}>
          <ArcIcon icon={ArrowLeftRight} size={11} />
          <span className="font-mono" style={{ letterSpacing: '0.18em', textTransform: 'uppercase' }}>Outputs</span>
        </div>
        {outputs.length === 0
          ? <div style={{ fontSize: 11, color: 'var(--text-3)' }}>None</div>
          : outputs.map(([k, v]) => (
              <PortRow
                key={k}
                name={k}
                dir="out"
                hint={v}
                wireName={k.startsWith('datasets[') ? outputName : null}
                wireColor="var(--success)"
              />
            ))}
      </Group>

      {node.type === 'code' && codeSummaryField && (
            <Group title="Code summary" count={1} defaultOpen>
              <div className="mb-2" style={{ fontSize: 10.5, color: 'var(--text-2)', lineHeight: 1.5 }}>
                Plain-language explanation of what the Starlark script does — for business readers who will not read the code.
              </div>
              <div
                className="rounded-md px-3 py-2.5 mb-3"
                style={{
                  fontSize: 12,
                  lineHeight: 1.65,
                  color: 'var(--text-0)',
                  background: 'color-mix(in srgb, #06b6d4 10%, var(--bg-0))',
                  border: '1px solid color-mix(in srgb, #06b6d4 32%, var(--border-soft))',
                  boxShadow: 'inset 0 1px 0 color-mix(in srgb, #fff 5%, transparent)',
                }}
              >
                {typeof cfg.code_summary === 'string' && cfg.code_summary.trim() ? (
                  cfg.code_summary.trim()
                ) : (
                  <span style={{ color: 'var(--text-3)', fontStyle: 'italic' }}>
                    No plain-language summary yet. When the AI generates Starlark, it will explain the step here for non-technical readers.
                  </span>
                )}
              </div>
              <ParamRow nodeIssues={nodeIssues}
                field={codeSummaryField}
                value={cfg[codeSummaryField.key]}
                upstream={upstream}
                onChange={(v) => updateNodeConfig(node.id, { [codeSummaryField.key]: v })}
              />
            </Group>
      )}

      {node.type === 'code' && codeStarlarkField && (
            <Group title="Starlark" count={1} defaultOpen>
              <div className="mb-2" style={{ fontSize: 10.5, color: 'var(--text-2)', lineHeight: 1.5 }}>
                Hermetic transform: assign your result to <span className="num">output</span>.
                Rows arrive as <span className="num">input_data[&quot;rows&quot;]</span> (or legacy <span className="num">rows</span>).
                No imports, <span className="num">while</span> loops, or network access.
              </div>
              <ParamRow nodeIssues={nodeIssues}
                field={codeStarlarkField}
                value={cfg[codeStarlarkField.key]}
                upstream={upstream}
                onChange={(v) => updateNodeConfig(node.id, { [codeStarlarkField.key]: v })}
              />
            </Group>
      )}

      {node.type === 'CODE' && codePythonField && (
        <>
          <Group title="Python" count={1}>
            <div className="mb-2" style={{ fontSize: 10.5, color: 'var(--text-2)', lineHeight: 1.5 }}>
              Use short comments (<span className="num"># ...</span>) above key steps so non-technical users can follow the logic.
              Keep one clear step per block and preserve indentation.
            </div>
            <ParamRow nodeIssues={nodeIssues}
              field={codePythonField}
              value={cfg[codePythonField.key]}
              upstream={upstream}
              onChange={(v) => updateNodeConfig(node.id, { [codePythonField.key]: v })}
            />
          </Group>
          {codeModeField && (
            <Group title="Mode" count={1}>
              <ParamRow nodeIssues={nodeIssues}
                field={codeModeField}
                value={cfg[codeModeField.key]}
                upstream={upstream}
                onChange={(v) => updateNodeConfig(node.id, { [codeModeField.key]: v })}
              />
            </Group>
          )}
          {codeReturnField && (
            <Group title="Return Type" count={1}>
              <div className="mb-2" style={{ fontSize: 10.5, color: 'var(--text-2)', lineHeight: 1.5 }}>
                Describes exactly what the Python block assigns to <span className="num">result</span>.
              </div>
              <ParamRow nodeIssues={nodeIssues}
                field={codeReturnField}
                value={cfg[codeReturnField.key]}
                upstream={upstream}
                onChange={(v) => updateNodeConfig(node.id, { [codeReturnField.key]: v })}
              />
            </Group>
          )}
          {codeParamsField && (
            <Group title="Params" count={1}>
              <div className="mb-2" style={{ fontSize: 10.5, color: 'var(--text-2)', lineHeight: 1.5 }}>
                Function-style values available inside Python as <span className="num">params</span>.
              </div>
              <ParamRow nodeIssues={nodeIssues}
                field={codeParamsField}
                value={cfg[codeParamsField.key]}
                upstream={upstream}
                onChange={(v) => updateNodeConfig(node.id, { [codeParamsField.key]: v })}
              />
            </Group>
          )}
          {codeCommentField && (
            <Group title="Comment" count={1}>
              <div className="mb-2" style={{ fontSize: 10.5, color: 'var(--text-2)', lineHeight: 1.5 }}>
                Optional note explaining intent, edge cases, or how <span className="num">params</span> keys are used.
              </div>
              <ParamRow nodeIssues={nodeIssues}
                field={codeCommentField}
                value={cfg[codeCommentField.key]}
                upstream={upstream}
                onChange={(v) => updateNodeConfig(node.id, { [codeCommentField.key]: v })}
              />
            </Group>
          )}
        </>
      )}

      {node.type === 'RESPONSE' && (
        <>
          <Group title="Response Preset" count={responsePrimaryFields.length + (responseEnvelopeField ? 1 : 0)}>
            <div className="mb-2" style={{ fontSize: 10.5, color: 'var(--text-2)', lineHeight: 1.5 }}>
              Minimal setup for structured outputs: order summaries + overall summary + full llm summary map.
            </div>
            {responseEnvelopeField && (
              <ParamRow nodeIssues={nodeIssues}
                field={responseEnvelopeField}
                value={cfg[responseEnvelopeField.key]}
                upstream={upstream}
                onChange={(v) => updateNodeConfig(node.id, { [responseEnvelopeField.key]: v })}
              />
            )}
            {responsePrimaryFields.map((f) => (
              <ParamRow nodeIssues={nodeIssues}
                key={f.key}
                field={f}
                value={cfg[f.key]}
                upstream={upstream}
                onChange={(v) => updateNodeConfig(node.id, { [f.key]: v })}
              />
            ))}
          </Group>
          {responseAdvancedFields.length > 0 && (
            <Group title="Advanced Keys" count={responseAdvancedFields.length} defaultOpen={false}>
              <div className="mb-2" style={{ fontSize: 10.5, color: 'var(--text-2)', lineHeight: 1.5 }}>
                Optional key renaming and overrides. Defaults are already suitable for surveillance response payloads.
              </div>
              {responseAdvancedFields.map((f) => (
                <ParamRow nodeIssues={nodeIssues}
                  key={f.key}
                  field={f}
                  value={cfg[f.key]}
                  upstream={upstream}
                  onChange={(v) => updateNodeConfig(node.id, { [f.key]: v })}
                />
              ))}
            </Group>
          )}
        </>
      )}

      {promptFields.length > 0 && (
        <Group title="Prompts" count={promptFields.length}>
          <div className="mb-2" style={{ fontSize: 10.5, color: 'var(--text-2)', lineHeight: 1.5 }}>
            sherpa writes these per-node prompt templates. Runtime values such as
            <span className="num" style={{ color: 'var(--text-1)' }}> {'{context.trader_id}'} </span>
            are filled when the node executes.
          </div>
          {promptFields.map((f) => (
            <ParamRow nodeIssues={nodeIssues}
              key={f.key}
              field={f}
              value={cfg[f.key]}
              upstream={upstream}
              onChange={(v) => updateNodeConfig(node.id, { [f.key]: v })}
            />
          ))}
        </Group>
      )}

      {llmSettingFields.length > 0 && (
        <Group title="LLM Settings" count={llmSettingFields.length}>
          <div className="mb-2" style={{ fontSize: 10.5, color: 'var(--text-2)', lineHeight: 1.5 }}>
            Gemini runtime controls for this node. `temperature` controls response variability.
          </div>
          {llmSettingFields.map((f) => (
            <ParamRow nodeIssues={nodeIssues}
              key={f.key}
              field={f}
              value={cfg[f.key]}
              upstream={upstream}
              onChange={(v) => updateNodeConfig(node.id, { [f.key]: v })}
            />
          ))}
        </Group>
      )}

      {node.type !== 'CODE' && node.type !== 'code' && node.type !== 'RESPONSE' && (
      <Group title="Params" count={lockedEnvFields.length + editableNonPromptFields.length}>
        {lockedEnvFields.length === 0 && editableNonPromptFields.length === 0 ? (
          <div style={{ fontSize: 11, color: 'var(--text-3)' }}>No configurable fields.</div>
        ) : (
          <>
            {lockedEnvFields.length > 0 && (
              <>
                <div className="flex items-center gap-1.5 mb-2" style={{ fontSize: 10, color: 'var(--text-3)' }}>
                  <Lock size={11} aria-hidden />
                  <span className="font-mono" style={{ letterSpacing: '0.18em', textTransform: 'uppercase' }}>
                    From backend/.env
                  </span>
                </div>
                {lockedEnvFields.map((f) => (
                  <LockedParamRow
                    key={f.key}
                    field={f}
                    displayValue={String(integrationEnv[f.key] ?? '')}
                    envKey={f.envKey}
                  />
                ))}
              </>
            )}
            {editableNonPromptFields.length > 0 && (
              <>
                <div
                  className="flex items-center gap-1.5 mb-2"
                  style={{
                    fontSize: 10,
                    color: 'var(--text-3)',
                    marginTop: lockedEnvFields.length > 0 ? 10 : 0,
                  }}
                >
                  <ArcIcon icon={Sliders} size={11} />
                  <span className="font-mono" style={{ letterSpacing: '0.18em', textTransform: 'uppercase' }}>Editable</span>
                </div>
                {editableNonPromptFields.map((f) => (
                  <ParamRow
                    nodeIssues={nodeIssues}
                    key={f.key}
                    field={f}
                    value={cfg[f.key]}
                    upstream={upstream}
                    onChange={(v) => updateNodeConfig(node.id, { [f.key]: v })}
                  />
                ))}
              </>
            )}
          </>
        )}
      </Group>
      )}

      <Group title="Last Run" defaultOpen={!!lastRun}>
        <div className="flex items-center gap-1.5 mb-2" style={{ fontSize: 10, color: 'var(--text-3)' }}>
          <ArcIcon icon={Eye} size={11} />
          <span className="font-mono" style={{ letterSpacing: '0.18em', textTransform: 'uppercase' }}>Output</span>
        </div>
        {!lastRun ? (
          <div style={{ fontSize: 11, color: 'var(--text-3)' }}>Run the workflow to see live output.</div>
        ) : lastRun.error ? (
          <div
            className="p-2 rounded"
            style={{
              fontSize: 11, color: 'var(--danger)', lineHeight: 1.5,
              background: 'color-mix(in srgb, var(--danger) 8%, transparent)',
              border: '1px solid color-mix(in srgb, var(--danger) 30%, transparent)',
            }}
          >
            {lastRun.error}
          </div>
        ) : lastRun.output ? (
          <pre
            className="num p-2 rounded overflow-x-auto"
            style={{
              fontSize: 10, color: 'var(--text-1)', maxHeight: 200,
              background: 'var(--bg-0)', border: '1px solid var(--border-soft)',
            }}
          >
            {JSON.stringify(lastRun.output, null, 2)}
          </pre>
        ) : (
          <div style={{ fontSize: 11, color: 'var(--text-3)' }}>No output recorded.</div>
        )}
      </Group>

      {contract.constraints.length > 0 && (
        <Group title="Constraints" count={contract.constraints.length} defaultOpen={false}>
          <ul className="space-y-1" style={{ fontSize: 11, color: 'var(--text-1)', lineHeight: 1.5 }}>
            {contract.constraints.map((c, i) => <li key={i}>· {c}</li>)}
          </ul>
        </Group>
      )}
    </Shell>
  )
}
