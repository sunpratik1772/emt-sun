import { useEffect, useMemo, useState } from 'react'
import SectionDrawer from '../SectionDrawer'
import { ArcIcon, Lightbulb } from '../../icons/arc'
import { useNodeRegistryStore } from '../../store/nodeRegistryStore'
import { ListRow, PanelEmpty, PanelError, PanelLoading } from './shared'

export function NodesDrawer({ open, onClose }: { open: boolean; onClose: () => void }) {
  const nodeUI = useNodeRegistryStore((s) => s.nodeUI)
  const nodeContracts = useNodeRegistryStore((s) => s.nodeContracts)
  const paletteSections = useNodeRegistryStore((s) => s.paletteSections)
  const registryLoading = useNodeRegistryStore((s) => s.loading)
  const registryError = useNodeRegistryStore((s) => s.error)
  const refreshNodeRegistry = useNodeRegistryStore((s) => s.refreshFromBackend)
  const [nodes, setNodes] = useState<any[] | null>(null)
  const [selectedCategory, setSelectedCategory] = useState<string | null>(null)

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
      if (!grouped[cat]) grouped[cat] = []
      grouped[cat].push(node)
    })
    return grouped
  }, [nodes])

  const sectionMeta = useMemo(() => {
    const out: Record<string, { label: string; order: number }> = {}
    for (const sec of paletteSections) {
      out[sec.id] = { label: sec.label, order: sec.order }
    }
    return out
  }, [paletteSections])

  const categories = useMemo(() => {
    return Object.keys(nodesByCategory).sort((a, b) => {
      const ao = sectionMeta[a]?.order ?? 999
      const bo = sectionMeta[b]?.order ?? 999
      if (ao !== bo) return ao - bo
      return a.localeCompare(b)
    })
  }, [nodesByCategory, sectionMeta])

  useEffect(() => {
    if (!categories.length) {
      setSelectedCategory(null)
      return
    }
    if (!selectedCategory || !categories.includes(selectedCategory)) {
      setSelectedCategory(categories[0])
    }
  }, [categories, selectedCategory])

  const activeCategory = selectedCategory || categories[0]
  const displayNodes = activeCategory ? nodesByCategory[activeCategory] || [] : []
  const loading = open && registryLoading && !nodes?.length

  return (
    <SectionDrawer
      open={open}
      onClose={onClose}
      title="Node Library"
      subtitle="Available workflow nodes you can use to build your automations"
      badge={nodes ? String(nodes.length) : undefined}
      width="100%"
    >
      <div className="flex h-full">
        <div className="shrink-0 overflow-y-auto studio-pane" style={{ width: 200 }}>
          {loading && <PanelLoading />}
          {registryError && !nodes?.length && (
            <PanelError
              message={registryError}
              onRetry={() => void refreshNodeRegistry({ force: true })}
            />
          )}
          {!loading && !registryError && categories.map((cat) => (
            <ListRow
              key={cat}
              selected={activeCategory === cat}
              onClick={() => setSelectedCategory(cat)}
            >
              <div className="min-w-0 flex-1">
                <div
                  className="display"
                  style={{ fontSize: 12.5, fontWeight: 530, color: 'var(--text-0)', letterSpacing: '-0.005em' }}
                >
                  {sectionMeta[cat]?.label ?? cat}
                </div>
                <div className="studio-meta" style={{ marginTop: 2 }}>
                  {nodesByCategory[cat]?.length || 0} nodes
                </div>
              </div>
            </ListRow>
          ))}
        </div>

        <div className="flex-1 min-w-0 overflow-y-auto studio-detail-pane">
          {loading && <PanelLoading />}
          {registryError && nodes?.length ? (
            <div className="studio-callout-warn">
              Showing cached node catalog — refresh failed: {registryError}
            </div>
          ) : null}
          {!loading && !registryError && displayNodes.length === 0 && (
            <PanelEmpty icon={<ArcIcon icon={Lightbulb} size={18} />}>No nodes in this category</PanelEmpty>
          )}
          <div
            style={{
              display: 'grid',
              gridTemplateColumns: 'repeat(auto-fill, minmax(240px, 1fr))',
              gap: 12,
            }}
          >
            {displayNodes.map((node) => {
              const Icon = node.Icon
              const contract = node.contract
              const inputs = contract ? Object.keys(contract.inputs ?? {}).length : 0
              const outputs = contract ? Object.keys(contract.outputs ?? {}).length : 0
              return (
                <div key={node.type} className="studio-node-card">
                  <div className="flex items-start gap-2.5 mb-2">
                    {Icon && (
                      <span
                        className="shrink-0 flex items-center justify-center rounded"
                        style={{
                          width: 28,
                          height: 28,
                          background: `${node.color}14`,
                          color: node.color,
                        }}
                      >
                        <Icon size={14} strokeWidth={2} />
                      </span>
                    )}
                    <div className="min-w-0 flex-1">
                      <div
                        className="display truncate"
                        style={{ fontSize: 13, fontWeight: 530, color: 'var(--text-0)' }}
                      >
                        {node.label ?? node.type}
                      </div>
                      <div className="studio-meta truncate" style={{ marginTop: 2 }}>
                        {node.type}
                      </div>
                    </div>
                  </div>
                  {node.description && (
                    <p style={{ fontSize: 11.5, color: 'var(--text-2)', lineHeight: 1.5, marginBottom: 8 }}>
                      {node.description}
                    </p>
                  )}
                  <div className="studio-meta flex items-center gap-3">
                    <span>{inputs} in</span>
                    <span>{outputs} out</span>
                  </div>
                </div>
              )
            })}
          </div>
        </div>
      </div>
    </SectionDrawer>
  )
}
