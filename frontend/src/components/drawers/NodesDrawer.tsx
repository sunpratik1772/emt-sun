import { useEffect, useMemo, useState } from 'react'
import StudioOverlay from '../StudioOverlay'
import { ArcIcon, Lightbulb, Search } from '../../icons/arc'
import { useNodeRegistryStore } from '../../store/nodeRegistryStore'
import { ListRow, PanelEmpty, PanelError, PanelLoading, SearchInput } from './shared'

export function NodesDrawer({ open, onClose }: { open: boolean; onClose: () => void }) {
  const nodeUI = useNodeRegistryStore((s) => s.nodeUI)
  const nodeContracts = useNodeRegistryStore((s) => s.nodeContracts)
  const paletteSections = useNodeRegistryStore((s) => s.paletteSections)
  const registryLoading = useNodeRegistryStore((s) => s.loading)
  const registryError = useNodeRegistryStore((s) => s.error)
  const refreshNodeRegistry = useNodeRegistryStore((s) => s.refreshFromBackend)
  const [nodes, setNodes] = useState<any[] | null>(null)
  const [selectedCategory, setSelectedCategory] = useState<string | null>(null)
  const [searchQuery, setSearchQuery] = useState('')

  useEffect(() => {
    if (!open) return
    void refreshNodeRegistry({ silent: true })
  }, [open, refreshNodeRegistry])

  useEffect(() => {
    if (!open) return
    const nodeTypes = Object.keys(nodeUI)
    const nodeData = nodeTypes.map((type) => ({
      type,
      ...nodeUI[type],
      contract: nodeContracts[type],
    }))
    setNodes(nodeData)
  }, [open, nodeUI, nodeContracts])

  const nodesByCategory = useMemo<Record<string, any[]>>(() => {
    if (!nodes) return {}
    const grouped: Record<string, any[]> = {}
    nodes.forEach(node => {
      const cat = node.paletteGroup || 'other'
      const label = (node.label || '').toLowerCase()
      const type = (node.type || '').toLowerCase()
      const desc = (node.description || '').toLowerCase()
      const query = searchQuery.toLowerCase()
      
      if (label.includes(query) || type.includes(query) || desc.includes(query)) {
        if (!grouped[cat]) grouped[cat] = []
        grouped[cat].push(node)
      }
    })
    return grouped
  }, [nodes, searchQuery])

  const sectionMeta = useMemo(() => {
    const out: Record<string, { label: string; order: number; color: string }> = {}
    for (const sec of paletteSections) {
      out[sec.id] = { label: sec.label, order: sec.order, color: sec.color }
    }
    return out
  }, [paletteSections])

  const categories = useMemo(() => {
    return Object.keys(nodesByCategory).filter(cat => nodesByCategory[cat].length > 0).sort((a, b) => {
      const ao = sectionMeta[a]?.order ?? 999
      const bo = sectionMeta[b]?.order ?? 999
      if (ao !== bo) return ao - bo
      return a.localeCompare(b)
    })
  }, [nodesByCategory, sectionMeta])

  const loading = open && registryLoading && !nodes?.length

  const nodeCount = nodes?.length ?? 0

  return (
    <StudioOverlay
      open={open}
      onClose={onClose}
      eyebrow="Building blocks"
      title="Node Library"
      subtitle={
        nodes
          ? `${nodeCount} nodes across ${categories.length} categories — drag onto the canvas or ask Sherpa.`
          : 'Available workflow nodes you can use to build your automations'
      }
      ariaLabel="Node Library"
      bodyClass="ov__body--wide ov__body--mng"
      titleAfter={
        <SearchInput
          value={searchQuery}
          onChange={setSearchQuery}
          placeholder="Search nodes…"
          icon={<Search size={13} />}
          style={{ width: 220 }}
        />
      }
      footRight={
        <span className="ov__foot-meta">
          {nodeCount} node{nodeCount === 1 ? '' : 's'}
        </span>
      }
    >
      <div className="screen__inner">
        {loading && <PanelLoading />}
        {registryError && !nodes?.length && (
          <PanelError
            message={registryError}
            onRetry={() => void refreshNodeRegistry({ force: true })}
          />
        )}
        {registryError && nodes?.length ? (
          <div className="studio-callout-warn">
            Showing cached node catalog — refresh failed: {registryError}
          </div>
        ) : null}
        {!loading && !registryError && categories.length === 0 && (
          <PanelEmpty icon={<ArcIcon icon={Lightbulb} size={18} />}>
            {searchQuery ? `No nodes found matching "${searchQuery}"` : 'No nodes available.'}
          </PanelEmpty>
        )}
        {!loading && !registryError && categories.map((cat) => {
          const displayNodes = nodesByCategory[cat] || []
          return (
            <section className="nlib-sec" key={cat}>
              <div className="nlib-sec__head">
                <span
                  className="nlib-sec__accent"
                  style={{ background: sectionMeta[cat]?.color ?? 'var(--text-3)' }}
                />
                <span className="nlib-sec__label">{sectionMeta[cat]?.label ?? cat}</span>
                <span className="pal-sec__count">{displayNodes.length}</span>
              </div>
              <div className="nlib-grid">
                {displayNodes.map((node) => {
                  const Icon = node.Icon
                  const inputs = node.contract ? Object.keys(node.contract.inputs ?? {}).length : 0
                  const outputs = node.contract ? Object.keys(node.contract.outputs ?? {}).length : 0
                  return (
                    <article key={node.type} className="nlib-card" style={{ cursor: 'default' }}>
                      {Icon && (
                        <span
                          className="nlib-card__ico"
                          style={{
                            background: `color-mix(in srgb, ${node.color} 16%, transparent)`,
                            color: node.color,
                          }}
                        >
                          <Icon size={18} />
                        </span>
                      )}
                      <div style={{ minWidth: 0, flex: 1 }}>
                        <div className="nlib-card__name">{node.label ?? node.type}</div>
                        <div className="nlib-card__type">{node.type}</div>
                        {node.description && (
                          <div className="nlib-card__desc">{node.description}</div>
                        )}
                        <div className="studio-meta flex items-center gap-3 mt-2">
                          <span>{inputs} in</span>
                          <span>{outputs} out</span>
                        </div>
                      </div>
                    </article>
                  )
                })}
              </div>
            </section>
          )
        })}
      </div>
    </StudioOverlay>
  )
}
