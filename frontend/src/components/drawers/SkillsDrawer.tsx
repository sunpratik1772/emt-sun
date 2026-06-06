import { useEffect, useMemo, useState } from 'react'
import StudioOverlay from '../StudioOverlay'
import {
  ArcIcon,
  Lightbulb,
  ChevronRight,
  Search,
  X,
  Box,
  ArrowUpRight,
  Pencil,
  Copy,
  Trash2,
  Eye,
  EyeOff,
  Target,
  FileText,
  AlertTriangle,
  Ticket,
  Shield,
} from '../../icons/arc'
import { useLibrarySkillDetail, useLibrarySkills } from '../../hooks/useLibraryQueries'
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
import { PlaybookMarkdown } from './PlaybookMarkdown'
import { toast } from '../../store/toastStore'

export function SkillsDrawer({ open, onClose }: { open: boolean; onClose: () => void }) {
  const { data: skills = [], isLoading: loading, isError, error, refetch } = useLibrarySkills(open)
  const [activeId, setActiveId] = useState<string | null>(null)
  const { data: detailData } = useLibrarySkillDetail(activeId, open)
  const detail = detailData ? { id: detailData.id, markdown: detailData.markdown } : null

  const [searchQuery, setSearchQuery] = useState('')
  const [disabledSkills, setDisabledSkills] = useState<Record<string, boolean>>({})

  useEffect(() => {
    if (!open) {
      setActiveId(null)
      return
    }
  }, [open])

  const isEnabled = (id: string) => !disabledSkills[id]

  const toggleEnabled = (id: string) => {
    setDisabledSkills((prev) => ({ ...prev, [id]: !prev[id] }))
  }

  // Filter skills based on search query
  const filteredSkills = useMemo(() => {
    const query = searchQuery.trim().toLowerCase()
    if (!query) return skills
    return skills.filter((s) => {
      const cat = SKILL_DETAILS_CATALOG[s.id]
      const title = (cat?.name || s.title || '').toLowerCase()
      const overview = (cat?.desc || s.overview || '').toLowerCase()
      const sources = (s.sources || []).join(' ').toLowerCase()
      const sections = (s.sections || []).join(' ').toLowerCase()
      return (
        title.includes(query) ||
        overview.includes(query) ||
        sources.includes(query) ||
        sections.includes(query)
      )
    })
  }, [skills, searchQuery])

  // Stats calculation
  const stats = useMemo(() => {
    const total = skills.length
    const enabledCount = skills.filter((s) => isEnabled(s.id)).length
    
    // Unique backends/sources
    const sourcesSet = new Set<string>()
    skills.forEach((s) => {
      const cat = SKILL_DETAILS_CATALOG[s.id]
      if (cat) {
        cat.tools.forEach((t) => sourcesSet.add(t))
      } else {
        s.sources.forEach((src) => sourcesSet.add(src))
      }
    })
    
    // Total runs
    let totalRuns = 0
    skills.forEach((s) => {
      totalRuns += SKILL_DETAILS_CATALOG[s.id]?.runs ?? 0
    })

    // In workflows count
    const inUse = skills.filter((s) => (SKILL_DETAILS_CATALOG[s.id]?.usedBy || []).length > 0).length

    return {
      total,
      enabled: enabledCount,
      sourcesCount: sourcesSet.size,
      totalRuns,
      inUse,
    }
  }, [skills, disabledSkills])

  const active = skills.find((s) => s.id === activeId) ?? null

  const handleNewSkillClick = () => {
    toast.success('Describe your new capability to Sherpa in the chat panel!')
  }

  const detailOverlay =
    activeId !== null && active ? (
      <>
        <div className="studio-detail-drawer-scrim" onClick={() => setActiveId(null)} />
        <aside className="studio-detail-drawer">
          {(() => {
            const cat = SKILL_DETAILS_CATALOG[active.id] || {
              name: active.title,
              icon: 'lightbulb',
              color: 'var(--accent)',
              desc: active.overview || 'No overview available.',
              instructions: detail?.markdown || active.overview || 'No playbook instructions loaded.',
              tools: active.sources.length ? active.sources : ['AI Agent'],
              inputs: [{ name: 'input', type: 'dataframe' }],
              outputs: [{ name: 'output', type: 'dataframe' }],
              usedBy: active.sections.slice(0, 2),
              example: 'process_data(input) → output',
            }
            const iconObj = getSkillIcon(cat.icon)
            const enabled = isEnabled(active.id)

            return (
              <>
                <div className="drawer__head">
                  <span
                    className="drawer__ico"
                    style={{
                      background: `color-mix(in srgb, ${cat.color} 15%, transparent)`,
                      color: cat.color,
                    }}
                  >
                    <ArcIcon icon={iconObj} size={20} />
                  </span>
                  <div className="drawer__titlewrap">
                    <div className="drawer__eyebrow">SKILL</div>
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
                  <DSection label="What it does">
                    <div className="dbody">{cat.desc}</div>
                  </DSection>

                  <DSection label="Instructions">
                    <div className="dbody">
                      {detail ? <PlaybookMarkdown content={detail.markdown} /> : cat.instructions}
                    </div>
                  </DSection>

                  <DSection label="Tools used">
                    <div className="dtags">
                      {cat.tools.map((t) => (
                        <span className="dchip" key={t}>
                          <ArcIcon icon={Box} size={12} style={{ marginRight: 4 }} />
                          {t}
                        </span>
                      ))}
                    </div>
                  </DSection>

                  <DSection label="Signature">
                    <div className="dgrid">
                      {cat.inputs.map((p) => (
                        <DCell key={'i' + p.name} k={'in · ' + p.name} v={p.type} mono />
                      ))}
                      {cat.outputs.map((p) => (
                        <DCell key={'o' + p.name} k={'out · ' + p.name} v={p.type} mono />
                      ))}
                    </div>
                  </DSection>

                  <DSection label="Example">
                    <div className="dbody" style={{ fontFamily: 'var(--font-sans)' }}>
                      <code>{cat.example}</code>
                    </div>
                  </DSection>

                  <DSection label={`Used by (${cat.usedBy.length})`}>
                    {cat.usedBy.length ? (
                      <div className="dtable">
                        {cat.usedBy.map((w) => (
                          <div className="dtable__row" key={w}>
                            <span className="dtable__name">{w}</span>
                            <ArcIcon icon={ArrowUpRight} size={14} />
                          </div>
                        ))}
                      </div>
                    ) : (
                      <div className="dbody" style={{ color: 'var(--text-3)' }}>
                        Not used by any workflow yet.
                      </div>
                    )}
                  </DSection>
                </div>

                <div className="drawer__foot">
                  <button
                    type="button"
                    className="ov-bbtn ov-bbtn--primary"
                    onClick={() => toast.success(`Editing ${cat.name}`)}
                  >
                    <ArcIcon icon={Pencil} size={14} strokeWidth={2.2} />
                    <span>Edit skill</span>
                  </button>
                  <button type="button" className="ov-bbtn" onClick={() => toast.success(`Duplicated ${cat.name}`)}>
                    <ArcIcon icon={Copy} size={14} strokeWidth={2.2} />
                    <span>Duplicate</span>
                  </button>
                  <div className="drawer__foot-spacer" />
                  <button
                    className="icon-btn"
                    title={enabled ? 'Disable' : 'Enable'}
                    onClick={() => {
                      toggleEnabled(active.id)
                      toast.success(`${cat.name} ${enabled ? 'disabled' : 'enabled'}`)
                    }}
                  >
                    <ArcIcon icon={enabled ? EyeOff : Eye} size={14} />
                  </button>
                  <button
                    className="icon-btn"
                    title="Delete"
                    style={{ color: 'var(--danger)' }}
                    onClick={() => toast.error('Delete not allowed in preview')}
                  >
                    <ArcIcon icon={Trash2} size={14} />
                  </button>
                </div>
              </>
            )
          })()}
        </aside>
      </>
    ) : null

  return (
    <StudioOverlay
      open={open}
      onClose={onClose}
      eyebrow="Reusable building blocks"
      title="Skills"
      subtitle="Packaged capabilities Sherpa can drop into any workflow — define the logic once, reuse everywhere."
      ariaLabel="Skills"
      bodyClass="ov__body--wide ov__body--mng"
      titleAfter={
        <button type="button" className="ov-bbtn ov-bbtn--primary" onClick={handleNewSkillClick}>
          <ArcIcon icon={Lightbulb} size={14} strokeWidth={2.2} />
          New skill
        </button>
      }
      footRight={
        <span className="ov__foot-meta">
          {skills.length} skill{skills.length === 1 ? '' : 's'}
        </span>
      }
      overlay={detailOverlay}
    >
      <div className="screen__inner h-full flex flex-col" style={{ minHeight: '100%' }}>
        {/* Stats summary strip */}
        <div className="mng-summary">
          <div className="mng-sum">
            <div className="mng-sum__val">{stats.total}</div>
            <div className="mng-sum__label">Skills</div>
            <div className="mng-sum__sub">{stats.enabled} enabled</div>
          </div>
          <div className="mng-sum">
            <div className="mng-sum__val mng-sum__val--ok">{stats.enabled}</div>
            <div className="mng-sum__label">Enabled</div>
            <div className="mng-sum__sub">available to Sherpa</div>
          </div>
          <div className="mng-sum">
            <div className="mng-sum__val">{stats.totalRuns.toLocaleString()}</div>
            <div className="mng-sum__label">Invocations</div>
            <div className="mng-sum__sub">all time</div>
          </div>
          <div className="mng-sum">
            <div className="mng-sum__val">{stats.inUse}</div>
            <div className="mng-sum__label">In Workflows</div>
            <div className="mng-sum__sub">actively wired</div>
          </div>
        </div>

        {/* Toolbar with Search */}
        <div className="mng-toolbar" style={{ marginBottom: 20 }}>
          <SearchInput
            value={searchQuery}
            onChange={setSearchQuery}
            placeholder="Search skills…"
            icon={<Search size={13} />}
            style={{ width: 260 }}
          />
        </div>

        {loading && skills.length === 0 && <PanelLoading />}
        {isError && (
          <PanelError
            message={(error as Error)?.message ?? 'Failed to load skills'}
            onRetry={() => void refetch()}
          />
        )}

        {!loading && !isError && filteredSkills.length === 0 && (
          <PanelEmpty icon={<ArcIcon icon={Lightbulb} size={18} />}>
            {searchQuery ? `No skills match "${searchQuery}"` : 'No skills configured.'}
          </PanelEmpty>
        )}

        {!loading && !isError && filteredSkills.length > 0 && (
          <div className="skill-grid">
            {filteredSkills.map((s) => {
              const cat = SKILL_DETAILS_CATALOG[s.id]
              const title = cat?.name || s.title
              const enabled = isEnabled(s.id)
              const iconObj = getSkillIcon(cat?.icon || '')
              const usedText = cat?.usedBy.length
                ? `Used by ${cat.usedBy.length} workflow${cat.usedBy.length > 1 ? 's' : ''}`
                : 'Not yet used'

              return (
                <article
                  className={`skill-card${activeId === s.id ? ' border-[var(--accent)] shadow-md' : ''}${enabled ? '' : ' skill-card--off'}`}
                  key={s.id}
                  onClick={() => setActiveId(s.id)}
                >
                  <div className="skill-card__head">
                    <span
                      className="skill-card__ico"
                      style={{
                        background: `color-mix(in srgb, ${cat?.color || 'var(--accent)'} 15%, transparent)`,
                        color: cat?.color || 'var(--accent)',
                      }}
                    >
                      <ArcIcon icon={iconObj} size={19} />
                    </span>
                    <div style={{ flex: 1, minWidth: 0 }}>
                      <div className="skill-card__name">{title}</div>
                      <div className="skill-card__type">{usedText}</div>
                    </div>
                  </div>
                  <div className="skill-card__desc">{cat?.desc || s.overview || 'No overview available.'}</div>
                  <div className="skill-card__tags">
                    {(cat?.tools || s.sources || []).map((t) => (
                      <span className="chip" key={t}>
                        {t}
                      </span>
                    ))}
                  </div>
                  <div className="skill-card__foot">
                    <span className="skill-card__used">
                      {(cat?.runs ?? 0).toLocaleString()} runs · {cat?.updated || '3d ago'}
                    </span>
                    <button
                      type="button"
                      className={`sw-toggle sw-toggle--sm${enabled ? ' sw-toggle--on' : ''}`}
                      aria-pressed={enabled}
                      title={enabled ? 'Enabled' : 'Disabled'}
                      onClick={(e) => {
                        e.stopPropagation()
                        toggleEnabled(s.id)
                        toast.success(`${title} ${enabled ? 'disabled' : 'enabled'}`)
                      }}
                    >
                      <span className="sw-toggle__knob" />
                    </button>
                  </div>
                </article>
              )
            })}
          </div>
        )}
      </div>
    </StudioOverlay>
  )
}

function getSkillIcon(iconName: string) {
  switch (iconName) {
    case 'target':
      return Target
    case 'file-text':
      return FileText
    case 'alert-triangle':
      return AlertTriangle
    case 'ticket':
      return Ticket
    case 'shield':
      return Shield
    default:
      return Lightbulb
  }
}

const SKILL_DETAILS_CATALOG: Record<string, {
  name: string
  icon: string
  color: string
  desc: string
  instructions: string
  tools: string[]
  inputs: { name: string; type: string }[]
  outputs: { name: string; type: string }[]
  usedBy: string[]
  example: string
  runs: number
  updated: string
}> = {
  'skills-agentic-workflow-builder': {
    name: 'Lead scorer',
    icon: 'target',
    color: '#8b5cf6',
    desc: 'Scores inbound leads 0–100 from firmographic and engagement signals, with a one-line reason.',
    instructions: 'Given a row of lead data, return a numeric score 0–100 weighing company size (30%), engagement (40%), and product fit (30%). Add a score_reason column naming the top driver.',
    tools: ['AI Agent', 'DB Query'],
    inputs: [{ name: 'leads', type: 'dataframe' }],
    outputs: [{ name: 'scored', type: 'dataframe' }],
    usedBy: ['Lead scoring pipeline', 'Hourly lead refresh'],
    runs: 142,
    updated: '3d ago',
    example: 'score_leads(leads) → adds score, score_reason'
  },
  'skills-fi-layering': {
    name: 'Exec summary writer',
    icon: 'file-text',
    color: '#0ea5e9',
    desc: 'Turns a dataset and metric deltas into a tight 3-paragraph executive narrative.',
    instructions: 'Summarize the input rows into 3 short paragraphs: what changed, why it matters, and the recommended action. Keep it under 180 words, no bullet lists.',
    tools: ['AI Agent'],
    inputs: [{ name: 'rows', type: 'dataframe' }, { name: 'context', type: 'string' }],
    outputs: [{ name: 'summary', type: 'string' }],
    usedBy: ['Quarterly report generator'],
    runs: 38,
    updated: '1w ago',
    example: 'write_summary(rows, context) → markdown string'
  },
  'skills-fi-spoofing': {
    name: 'Anomaly flagger',
    icon: 'alert-triangle',
    color: '#f59e0b',
    desc: 'Flags statistical outliers in trade rows using z-score and rolling thresholds.',
    instructions: 'Compute a rolling 30-row mean/stddev per symbol. Flag any row beyond 3σ. Return rows with an is_anomaly boolean and z_score column.',
    tools: ['Transform (Starlark)', 'Filter'],
    inputs: [{ name: 'trades', type: 'dataframe' }],
    outputs: [{ name: 'flagged', type: 'dataframe' }],
    usedBy: ['Trade anomaly detection'],
    runs: 906,
    updated: '2d ago',
    example: 'flag_anomalies(trades) → adds is_anomaly, z_score'
  },
  'skills-fx-fro': {
    name: 'Jira filer',
    icon: 'ticket',
    color: '#0052CC',
    desc: 'Creates well-formed Jira issues from flagged rows, de-duplicating against open tickets.',
    instructions: 'For each input row, draft a Jira issue (summary, description, priority). Skip rows that match an existing open ticket by key. Return created issue keys.',
    tools: ['Jira MCP', 'Deduplicate'],
    inputs: [{ name: 'items', type: 'dataframe' }],
    outputs: [{ name: 'tickets', type: 'string_list' }],
    usedBy: [],
    runs: 0,
    updated: '5d ago',
    example: 'file_jira(items) → list of issue keys'
  },
  'skills-fx-wash': {
    name: 'FX Wash Trade Detector',
    icon: 'shield',
    color: '#10b981',
    desc: 'Identifies wash trading patterns across counterparty profiles and order logs.',
    instructions: 'Compare buyer and seller accounts on recent trade entries. Flag pairs with matching tax IDs or shared address prefixes trading identical symbols within 10 seconds.',
    tools: ['AI Agent', 'Filter'],
    inputs: [{ name: 'orders', type: 'dataframe' }],
    outputs: [{ name: 'wash_trades', type: 'dataframe' }],
    usedBy: ['FX Surveillance E2E'],
    runs: 0,
    updated: '5d ago',
    example: 'find_wash_trades(orders) → dataframe of suspect accounts'
  }
}
