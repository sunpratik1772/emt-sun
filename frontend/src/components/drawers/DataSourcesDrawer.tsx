import { useEffect, useMemo, useState } from 'react'
import StudioOverlay from '../StudioOverlay'
import {
  ArcIcon,
  Database,
  ChevronRight,
  Search,
  X,
  Pencil,
  Trash2,
  RefreshCw,
  Plug,
  Table2,
  Globe,
  Snowflake,
} from '../../icons/arc'
import { useDataSources } from '../../hooks/useLibraryQueries'
import {
  BackendChip,
  ListRow,
  PanelEmpty,
  PanelError,
  PanelLoading,
  SectionLabel,
  SearchInput,
  StatusBadge,
  DSection,
  DCell,
} from './shared'
import { toast } from '../../store/toastStore'

export function DataSourcesDrawer({ open, onClose }: { open: boolean; onClose: () => void }) {
  const { data: sources = [], isLoading: loading, isError, error, refetch } = useDataSources(open)
  const [activeId, setActiveId] = useState<string | null>(null)
  const [searchQuery, setSearchQuery] = useState('')

  useEffect(() => {
    if (!open) {
      setActiveId(null)
      return
    }
  }, [open])

  // Filter sources based on search query
  const filteredSources = useMemo(() => {
    const query = searchQuery.trim().toLowerCase()
    if (!query) return sources
    return sources.filter((s) => {
      const cat = DATA_SOURCES_CATALOG[s.id.toLowerCase()]
      const id = (cat?.name || s.id || '').toLowerCase()
      const desc = (s.description || '').toLowerCase()
      const backends = (s.backend_labels || []).join(' ').toLowerCase()
      const cols = (s.columns || []).map(c => c.name).join(' ').toLowerCase()
      return (
        id.includes(query) ||
        desc.includes(query) ||
        backends.includes(query) ||
        cols.includes(query)
      )
    })
  }, [sources, searchQuery])

  // Stats calculation
  const stats = useMemo(() => {
    const total = sources.length
    let connectedCount = 0
    let errorCount = 0
    let totalRows = 0

    sources.forEach((s) => {
      const cat = DATA_SOURCES_CATALOG[s.id.toLowerCase()]
      const status = cat?.status || 'connected'
      if (status === 'connected') connectedCount++
      if (status === 'error') errorCount++
      totalRows += cat?.rows ?? s.column_count * 100
    })

    const formatTotalRows = (n: number) => {
      if (n >= 1_000_000) {
        return (n / 1_000_000).toFixed(1).replace(/\.0$/, '') + 'M'
      }
      if (n >= 1_000) {
        return (n / 1_000).toFixed(1).replace(/\.0$/, '') + 'K'
      }
      return n.toString()
    }

    return {
      total,
      connected: connectedCount,
      errors: errorCount,
      totalRows: formatTotalRows(totalRows)
    }
  }, [sources])

  const active = sources.find((s) => s.id === activeId) ?? null

  const handleAddSourceClick = () => {
    toast.success('Add source connection via the dev config or tell Sherpa!')
  }

  return (
    <StudioOverlay
      open={open}
      onClose={onClose}
      eyebrow="Connected data"
      title="Data Sources"
      subtitle="Databases and files your workflows read from — test, sync, edit credentials, or remove."
      ariaLabel="Data Sources"
      bodyClass="ov__body--wide ov__body--mng"
      titleAfter={
        <button type="button" className="ov-bbtn ov-bbtn--primary" onClick={handleAddSourceClick}>
          <ArcIcon icon={Database} size={14} strokeWidth={2.2} />
          Add source
        </button>
      }
      footRight={
        <span className="ov__foot-meta">
          {sources.length} source{sources.length === 1 ? '' : 's'}
        </span>
      }
    >
      <div className="screen__inner h-full flex flex-col" style={{ minHeight: '100%' }}>
        {/* Stats summary strip */}
        <div className="mng-summary">
          <div className="mng-sum">
            <div className="mng-sum__val">{stats.total}</div>
            <div className="mng-sum__label">Sources</div>
            <div className="mng-sum__sub">configured</div>
          </div>
          <div className="mng-sum">
            <div className="mng-sum__val mng-sum__val--ok">{stats.connected}</div>
            <div className="mng-sum__label">Connected</div>
            <div className="mng-sum__sub">healthy</div>
          </div>
          <div className="mng-sum">
            <div className="mng-sum__val mng-sum__val--err">{stats.errors}</div>
            <div className="mng-sum__label">Errors</div>
            <div className="mng-sum__sub">{stats.errors ? 'needs attention' : 'all clear'}</div>
          </div>
          <div className="mng-sum">
            <div className="mng-sum__val">{stats.totalRows}</div>
            <div className="mng-sum__label">Total rows</div>
            <div className="mng-sum__sub">across sources</div>
          </div>
        </div>

        {/* Search bar */}
        <div className="mng-toolbar" style={{ marginBottom: 20 }}>
          <SearchInput
            value={searchQuery}
            onChange={setSearchQuery}
            placeholder="Search data sources…"
            icon={<Search size={13} />}
            style={{ width: 260 }}
          />
        </div>

        {loading && sources.length === 0 && <PanelLoading />}
        {isError && (
          <PanelError
            message={(error as Error)?.message ?? 'Failed to load data sources'}
            onRetry={() => void refetch()}
          />
        )}

        {!loading && !isError && filteredSources.length === 0 && (
          <PanelEmpty icon={<ArcIcon icon={Database} size={18} />}>
            {searchQuery ? `No data sources match "${searchQuery}"` : 'No data sources configured.'}
          </PanelEmpty>
        )}

        {!loading && !isError && filteredSources.length > 0 && (
          <div className="mng-list">
            {filteredSources.map((d) => {
              const cat = DATA_SOURCES_CATALOG[d.id.toLowerCase()]
              const k = SOURCE_KINDS[cat?.kind || 'csv']
              const status = cat?.status || 'connected'
              const name = cat?.name || d.id
              const summaryText = cat?.summary || d.raw_path
              const rowsText = cat?.rows ? cat.rows.toLocaleString() + ' rows' : '—'
              const tablesText = `${cat?.tableCount || d.source_count} table${(cat?.tableCount || d.source_count) > 1 ? 's' : ''} · ${cat?.lastSync || 'updated'}`

              return (
                <div
                  className={`mng-row${d.id === activeId ? ' bg-color-mix' : ''}`}
                  key={d.id}
                  onClick={() => setActiveId(d.id)}
                  style={d.id === activeId ? { background: 'color-mix(in srgb, var(--bg-2) 65%, transparent)' } : undefined}
                >
                  <span
                    className="mng-row__ico"
                    style={{
                      background: `color-mix(in srgb, ${k.color} 15%, transparent)`,
                      color: k.color,
                    }}
                  >
                    <ArcIcon icon={k.icon} size={19} />
                  </span>
                  <div className="mng-row__main">
                    <div className="mng-row__name">
                      {name}
                      <span className="chip" style={{ fontSize: 9.5, padding: '1px 5px', textTransform: 'none', marginLeft: 8 }}>
                        {k.label}
                      </span>
                    </div>
                    <div className="mng-row__sub">
                      <code>{summaryText}</code>
                    </div>
                  </div>
                  <div className="mng-row__meta">
                    <div className="mng-row__meta-1">{rowsText}</div>
                    <div className="mng-row__meta-2">{tablesText}</div>
                  </div>
                  <div className="mng-row__actions">
                    <StatusBadge status={status} />
                    <ArcIcon icon={ChevronRight} size={11} strokeWidth={2} style={{ color: 'var(--text-3)' }} />
                  </div>
                </div>
              )
            })}
          </div>
        )}

        {/* Floating Right Detail Panel */}
        {activeId !== null && active && (
          <>
            <div className="studio-detail-drawer-scrim" onClick={() => setActiveId(null)} />
            <aside className="studio-detail-drawer">
              {(() => {
                const cat = DATA_SOURCES_CATALOG[active.id.toLowerCase()] || {
                  name: active.id,
                  kind: 'csv',
                  status: 'connected',
                  schema: '—',
                  tableCount: active.source_count,
                  rows: active.column_count * 100,
                  lastSync: 'updated',
                  owner: 'Growth Team',
                  tables: active.columns.length ? [{ name: active.id, rows: active.column_count * 100 }] : [],
                  syncs: [{ when: 'updated', status: 'success', rows: active.column_count * 100, dur: '0.3s' }],
                  summary: active.raw_path,
                  err: undefined
                }
                const k = SOURCE_KINDS[cat.kind]

                return (
                  <>
                    <div className="drawer__head">
                      <span
                        className="drawer__ico"
                        style={{
                          background: `color-mix(in srgb, ${k.color} 15%, transparent)`,
                          color: k.color,
                        }}
                      >
                        <ArcIcon icon={k.icon} size={20} />
                      </span>
                      <div className="drawer__titlewrap">
                        <div className="drawer__eyebrow">{k.label.toUpperCase()} SOURCE</div>
                        <div className="drawer__title">{cat.name}</div>
                      </div>
                      <button
                        type="button"
                        className="drawer__close"
                        onClick={() => setActiveId(null)}
                        aria-label="Close"
                      >
                        <ArcIcon icon={X} size={15} />
                      </button>
                    </div>

                    <div className="drawer__body">
                      {cat.err && (
                        <div
                          className="dbody"
                          style={{
                            color: 'var(--danger)',
                            background: 'color-mix(in srgb, var(--danger) 8%, transparent)',
                            borderColor: 'color-mix(in srgb, var(--danger) 28%, transparent)',
                            marginBottom: 20
                          }}
                        >
                          {cat.err}
                        </div>
                      )}

                      <DSection label="Connection">
                        <div className="dgrid">
                          <DCell k="Type" v={k.label} />
                          <DCell k="Status" v={<StatusBadge status={cat.status} />} />
                          <DCell k="Schema" v={cat.schema} />
                          <DCell k="Owner" v={cat.owner} />
                          <DCell k="Tables" v={cat.tableCount} />
                          <DCell k="Rows" v={cat.rows ? cat.rows.toLocaleString() : '—'} />
                        </div>
                      </DSection>

                      <DSection label="Endpoint">
                        <div className="dbody">
                          <code>{cat.summary}</code>
                        </div>
                      </DSection>

                      <DSection label="Columns schema">
                        {active.columns && active.columns.length ? (
                          <div className="dtable">
                            <div
                              className="dtable__row"
                              style={{
                                background: 'var(--bg-2)',
                                fontSize: '11px',
                                fontWeight: 600,
                                color: 'var(--text-2)',
                                textTransform: 'uppercase',
                                letterSpacing: '0.04em',
                                borderBottom: '1px solid var(--border-soft)',
                              }}
                            >
                              <span style={{ flex: 1.5, minWidth: 0 }}>Column</span>
                              <span style={{ flex: 1, minWidth: 0, paddingLeft: 8 }}>Type</span>
                              <span style={{ flex: 2.5, minWidth: 0, paddingLeft: 8 }}>Description</span>
                            </div>
                            {active.columns.map((c) => (
                              <div className="dtable__row" key={c.name}>
                                <span className="dtable__name" style={{ flex: 1.5, minWidth: 0, fontWeight: 550 }}>
                                  {c.name}
                                </span>
                                <span className="dtable__rows num" style={{ flex: 1, minWidth: 0, paddingLeft: 8, textAlign: 'left', color: 'var(--accent)' }}>
                                  {c.type}
                                </span>
                                <span className="dtable__rows" style={{ flex: 2.5, minWidth: 0, paddingLeft: 8, textAlign: 'left' }}>
                                  {c.description || '—'}
                                </span>
                              </div>
                            ))}
                          </div>
                        ) : (
                          <div className="dbody" style={{ color: 'var(--text-3)' }}>
                            No columns defined.
                          </div>
                        )}
                      </DSection>

                      <DSection label="Recent syncs">
                        <div>
                          {cat.syncs.map((s, i) => (
                            <div className="drun" key={i}>
                              <StatusBadge status={s.status} />
                              <span className="drun__when">{s.when}</span>
                              <span className="drun__meta">
                                {s.rows == null ? '—' : s.rows.toLocaleString() + ' rows'} · {s.dur}
                              </span>
                            </div>
                          ))}
                        </div>
                      </DSection>
                    </div>

                    <div className="drawer__foot">
                      <button type="button" className="ov-bbtn ov-bbtn--primary" onClick={() => toast.success(`Syncing ${cat.name}…`)}>
                        <ArcIcon icon={RefreshCw} size={14} strokeWidth={2.2} />
                        <span>Sync now</span>
                      </button>
                      <button type="button" className="ov-bbtn" onClick={() => toast.success(`Testing ${cat.name}…`)}>
                        <ArcIcon icon={Plug} size={14} strokeWidth={2.2} />
                        <span>Test</span>
                      </button>
                      <div className="drawer__foot-spacer" />
                      <button className="icon-btn" title="Edit" onClick={() => toast.success(`Editing ${cat.name}`)}>
                        <ArcIcon icon={Pencil} size={14} />
                      </button>
                      <button
                        className="icon-btn"
                        title="Remove"
                        style={{ color: 'var(--danger)' }}
                        onClick={() => toast.error('Remove not allowed in preview')}
                      >
                        <ArcIcon icon={Trash2} size={14} />
                      </button>
                    </div>
                  </>
                )
              })()}
            </aside>
          </>
        )}
      </div>
    </StudioOverlay>
  )
}

const SOURCE_KINDS: Record<string, { label: string; icon: any; color: string }> = {
  oracle:    { label: 'Oracle', icon: Database, color: '#C74634' },
  postgres:  { label: 'PostgreSQL', icon: Database, color: '#336791' },
  snowflake: { label: 'Snowflake', icon: Snowflake, color: '#29B5E8' },
  csv:       { label: 'CSV / File', icon: Table2, color: '#16a34a' },
  http:      { label: 'HTTP / API', icon: Globe, color: '#0ea5e9' },
}

interface MockDataSourceDetail {
  name: string
  kind: 'oracle' | 'postgres' | 'snowflake' | 'csv' | 'http'
  status: 'connected' | 'syncing' | 'error'
  schema: string
  owner: string
  tableCount: number
  rows: number
  lastSync: string
  summary: string
  err?: string
  tables: { name: string; rows: number }[]
  syncs: { when: string; status: 'success' | 'running' | 'error'; rows: number | null; dur: string }[]
}

const DATA_SOURCES_CATALOG: Record<string, MockDataSourceDetail> = {
  'finance oracle': {
    name: 'Finance Oracle',
    kind: 'oracle',
    status: 'connected',
    schema: 'FINANCE',
    tableCount: 24,
    rows: 248000,
    lastSync: '12m ago',
    owner: 'Data Platform',
    summary: 'oracle://prod-fin-01:1521/FINANCE',
    tables: [{ name: 'GL_ENTRIES', rows: 182400 }, { name: 'TRADES', rows: 61480 }, { name: 'ACCOUNTS', rows: 4120 }],
    syncs: [{ when: '12m ago', status: 'success', rows: 248000, dur: '4.2s' }, { when: '1h ago', status: 'success', rows: 247600, dur: '4.0s' }]
  },
  'leads.csv': {
    name: 'leads.csv',
    kind: 'csv',
    status: 'connected',
    schema: '—',
    tableCount: 1,
    rows: 248,
    lastSync: '2h ago',
    owner: 'Growth Team',
    summary: 'uploads/leads.csv · 248 rows · 9 cols',
    tables: [{ name: 'leads', rows: 248 }],
    syncs: [{ when: '2h ago', status: 'success', rows: 248, dur: '0.3s' }]
  },
  'hubspot crm': {
    name: 'HubSpot CRM',
    kind: 'http',
    status: 'syncing',
    schema: 'contacts, deals',
    tableCount: 4,
    rows: 51200,
    lastSync: 'syncing now…',
    owner: 'Growth Team',
    summary: 'https://api.hubapi.com/crm/v3',
    tables: [{ name: 'contacts', rows: 41200 }, { name: 'deals', rows: 9800 }, { name: 'companies', rows: 200 }],
    syncs: [{ when: 'now', status: 'running', rows: null, dur: '—' }, { when: '6h ago', status: 'success', rows: 50900, dur: '12.1s' }]
  },
  'analytics postgres': {
    name: 'Analytics Postgres',
    kind: 'postgres',
    status: 'error',
    schema: 'public',
    tableCount: 12,
    rows: 0,
    lastSync: 'failed 25m ago',
    owner: 'Data Platform',
    summary: 'postgres://analytics-ro:5432/events',
    err: 'Connection timed out after 30s — host unreachable.',
    tables: [{ name: 'events', rows: 0 }, { name: 'sessions', rows: 0 }],
    syncs: [{ when: '25m ago', status: 'error', rows: 0, dur: '30.0s' }, { when: '6h ago', status: 'success', rows: 1840000, dur: '41.2s' }]
  },
  'warehouse': {
    name: 'Warehouse',
    kind: 'snowflake',
    status: 'connected',
    schema: 'MARTS',
    tableCount: 38,
    rows: 4120000,
    lastSync: '40m ago',
    owner: 'Analytics',
    summary: 'snowflake://acme.us-east-1/WAREHOUSE',
    tables: [{ name: 'FCT_ORDERS', rows: 2840000 }, { name: 'DIM_CUSTOMERS', rows: 612000 }, { name: 'FCT_SESSIONS', rows: 668000 }],
    syncs: [{ when: '40m ago', status: 'success', rows: 4120000, dur: '18.4s' }]
  }
}
