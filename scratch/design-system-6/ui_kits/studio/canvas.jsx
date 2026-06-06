/* dbSherpa Studio — Workflow Canvas (DAG editor) components.
   Faithful to WorkflowCanvas/CustomNode.tsx, NodePanel, WorkspaceToolbar. */

const NODE_W = 240;
function nodeHeight(n) { return 64 + (n.tags && n.tags.length ? 28 : 0); }

function WorkspaceToolbar({ view, onView, running, onRun, flash }) {
  return (
    <div className="wt">
      <div className="wt__left">
        <div className="wt-seg">
          <button className={'wt-seg__btn' + (view === 'canvas' ? ' wt-seg__btn--on' : '')} onClick={() => onView('canvas')}>
            <Icon name="workflow" /> Canvas
          </button>
          <button className={'wt-seg__btn' + (view === 'code' ? ' wt-seg__btn--on' : '')} onClick={() => onView('code')}>
            <Icon name="code-2" /> Code
          </button>
        </div>
        <span className="wt__sep">/</span>
        <div className="wt-seg">
          <button className="wt-seg__btn wt-seg__btn--on">View</button>
          <button className="wt-seg__btn" onClick={() => flash('Edit mode')}>Edit</button>
        </div>
      </div>
      <div className="wt__right">
        <button className="wt-ico" title="Import" onClick={() => flash('Import workflow')}><Icon name="upload" /></button>
        <button className="wt-ico" title="Export" onClick={() => flash('Export workflow')}><Icon name="download" /></button>
        <button className="wt-ico" title="Clear" onClick={() => flash('Clear run state')}><Icon name="trash-2" /></button>
        <button className="wt-ico" title="Save" onClick={() => flash('Workflow saved')}><Icon name="save" /></button>
        <button className="wt-run" title={running ? 'Stop' : 'Run workflow'} onClick={onRun}>
          <Icon name={running ? 'square' : 'play'} />
        </button>
        <span className="wt-divider" />
        <button className="wt-ico" title="New workflow" onClick={() => flash('New workflow')}><Icon name="plus" /></button>
      </div>
    </div>
  );
}

function NodePalette({ onAdd }) {
  const sections = window.PALETTE_SECTIONS.map((sec) => ({
    ...sec,
    types: Object.entries(window.NODE_UI).filter(([, m]) => m[3] === sec.id),
  })).filter((s) => s.types.length);
  return (
    <aside className="pal">
      <div className="pal__head"><span className="pal__title">Palette</span>
        <button className="wt-ico" style={{ width: 22, height: 22 }} title="Collapse"><Icon name="panel-left-close" /></button>
      </div>
      <div className="pal__search"><Icon name="search" /><span>Search nodes…</span></div>
      <div className="pal__scroll">
        {sections.map((sec) => (
          <div className="pal-sec" key={sec.id}>
            <div className="pal-sec__head">
              <span className="pal-accent" style={{ background: sec.color }} />
              <span className="pal-sec__label">{sec.label}</span>
              <span className="pal-sec__count">{sec.types.length}</span>
            </div>
            <div className="pal-items">
              {sec.types.map(([type, m]) => (
                <div className="pal-item" key={type} title={m[4]} onClick={() => onAdd(m[0])}>
                  <span className="pal-item__accent" style={{ background: sec.color }} />
                  <span className="pal-item__ico"><Icon name={m[2]} /></span>
                  <span className="pal-item__name">{m[0]}</span>
                </div>
              ))}
            </div>
          </div>
        ))}
      </div>
      <div className="pal__foot">drag · double-click to add</div>
    </aside>
  );
}

function statusLabel(s) { return s === 'running' ? 'Running' : s === 'ok' ? 'Complete' : s === 'error' ? 'Error' : 'Idle'; }
function statusColor(s) { return s === 'running' ? 'var(--running)' : s === 'ok' ? 'var(--success)' : s === 'error' ? 'var(--danger)' : 'var(--border-strong)'; }

function CanvasNode({ node, selected, onSelect }) {
  const m = window.NODE_UI[node.type];
  const [name, color, icon, group] = m;
  const cls = 'cnode'
    + (node.status === 'running' ? ' cnode--running' : node.status === 'ok' ? ' cnode--ok' : node.status === 'error' ? ' cnode--error' : '')
    + (selected ? ' cnode--selected' : '');
  const accent = node.status === 'ok' ? 'var(--success)' : node.status === 'error' ? 'var(--danger)' : node.status === 'running' ? 'var(--running)' : color;
  const hasRun = node.status === 'ok' || node.status === 'error' || node.status === 'running';
  return (
    <div className={cls} style={{ left: node.x, top: node.y }} onClick={(e) => { e.stopPropagation(); onSelect(node.id); }}>
      <span className="cnode__accent" style={{ background: accent, opacity: selected || hasRun ? 0.95 : 0.55 }} />
      <span className="cnode__handle cnode__handle--in" style={{ background: selected ? color : 'var(--text-3)' }} />
      <span className="cnode__handle cnode__handle--out" style={{ background: node.status === 'ok' ? 'var(--success)' : selected ? color : 'var(--text-3)' }} />
      <span className="cnode__cat">{node.type}</span>
      <div className="cnode__head">
        <span className="cnode__ico" style={{ color }}><Icon name={icon} /></span>
        <span className="cnode__label">{node.label}</span>
      </div>
      <div className="cnode__status">
        <div className="cnode__st-left">
          <span className={'cnode__dot' + (node.status === 'running' ? ' cnode__dot--running' : '')} style={{ background: statusColor(node.status) }} />
          <span className="cnode__st-label" style={{ color: statusColor(node.status) }}>{statusLabel(node.status)}</span>
          {node.status === 'running' && node.idx != null && <span className="cnode__st-idx">· {node.idx}/{node.total}</span>}
        </div>
        {hasRun && node.ms != null && (
          <span className="cnode__ms" style={{ color: node.status === 'error' ? 'var(--danger)' : node.status === 'running' ? 'var(--running)' : 'var(--text-1)' }}>
            {(node.ms / 1000).toFixed(node.ms < 1000 ? 1 : 2)} s
          </span>
        )}
      </div>
      {node.tags && node.tags.length > 0 && (
        <div className="cnode__tags">{node.tags.map((t, i) => <span className="cnode__tag" key={i}>{t}</span>)}</div>
      )}
    </div>
  );
}

function edgePath(a, b) {
  const x1 = a.x + NODE_W, y1 = a.y + nodeHeight(a) / 2;
  const x2 = b.x, y2 = b.y + nodeHeight(b) / 2;
  const dx = Math.max(40, (x2 - x1) / 2);
  return `M ${x1} ${y1} C ${x1 + dx} ${y1}, ${x2 - dx} ${y2}, ${x2} ${y2}`;
}

function WorkflowCanvasScreen({ flash }) {
  const wf = window.WORKFLOW;
  const [nodes, setNodes] = React.useState(wf.nodes);
  const [sel, setSel] = React.useState('n4');
  const [zoom, setZoom] = React.useState(0.82);
  const [grid, setGrid] = React.useState(true);
  const [minimap, setMinimap] = React.useState(true);
  const [view, setView] = React.useState('canvas');
  const [running, setRunning] = React.useState(true);
  const byId = Object.fromEntries(nodes.map((n) => [n.id, n]));

  const bounds = nodes.reduce((b, n) => ({
    maxX: Math.max(b.maxX, n.x + NODE_W), maxY: Math.max(b.maxY, n.y + nodeHeight(n)),
  }), { maxX: 0, maxY: 0 });

  return (
    <div className="canvas-wrap">
      <WorkspaceToolbar view={view} onView={setView} running={running}
        onRun={() => { setRunning((r) => !r); flash(running ? 'Run stopped' : 'Running workflow…'); }} flash={flash} />
      <div className="canvas" onClick={() => setSel(null)}>
        {grid && <div className="canvas__dots" />}
        <span className="run-pill"><span className="run-pill__dot" />Running · {wf.name}</span>
        <div className="canvas__stage" style={{ transform: `scale(${zoom})`, transformOrigin: '0 0', left: 28, top: 24 }}>
          <svg className="canvas__edges" style={{ width: bounds.maxX + 80, height: bounds.maxY + 80 }}>
            {wf.edges.map((e, i) => {
              const a = byId[e.from], b = byId[e.to];
              if (!a || !b) return null;
              const cls = 'edge-path' + (e.state === 'done' ? ' edge-path--done' : e.state === 'running' ? ' edge-path--running' : '');
              return <path key={i} className={cls} d={edgePath(a, b)} markerEnd={`url(#arrow-${e.state})`} />;
            })}
            <defs>
              {['idle', 'done', 'running'].map((s) => (
                <marker key={s} id={`arrow-${s}`} markerWidth="9" markerHeight="9" refX="7" refY="4.5" orient="auto">
                  <path d="M0,0 L9,4.5 L0,9 z" fill={s === 'done' ? 'var(--success)' : s === 'running' ? 'var(--running)' : 'var(--canvas-edge)'} />
                </marker>
              ))}
            </defs>
          </svg>
          {nodes.map((n) => <CanvasNode key={n.id} node={n} selected={sel === n.id} onSelect={setSel} />)}
        </div>

        <div className="cc">
          <button className={'cc__btn' + (grid ? ' cc__btn--on' : '')} title="Toggle grid" onClick={() => setGrid((g) => !g)}><Icon name="grid-3x3" /></button>
          <div className="cc__sep" />
          <button className="cc__btn" title="Zoom in" onClick={() => setZoom((z) => Math.min(1.5, z + 0.12))}><Icon name="plus" /></button>
          <button className="cc__btn" title="Zoom out" onClick={() => setZoom((z) => Math.max(0.4, z - 0.12))}><Icon name="minus" /></button>
          <button className="cc__btn" title="Fit view" onClick={() => setZoom(0.82)}><Icon name="maximize" /></button>
          <div className="cc__sep" />
          <button className={'cc__btn' + (minimap ? ' cc__btn--on' : '')} title="Toggle minimap" onClick={() => setMinimap((m) => !m)}><Icon name="layers" /></button>
        </div>

        {minimap && (
          <div className="mmap">
            <svg viewBox={`-20 -20 ${bounds.maxX + 80} ${bounds.maxY + 80}`} preserveAspectRatio="xMidYMid meet">
              {wf.edges.map((e, i) => {
                const a = byId[e.from], b = byId[e.to]; if (!a || !b) return null;
                return <line key={i} x1={a.x + NODE_W} y1={a.y + nodeHeight(a) / 2} x2={b.x} y2={b.y + nodeHeight(b) / 2}
                  stroke="var(--canvas-edge)" strokeWidth="2" opacity="0.5" />;
              })}
              {nodes.map((n) => (
                <rect key={n.id} x={n.x} y={n.y} width={NODE_W} height={nodeHeight(n)} rx="8"
                  fill={window.NODE_UI[n.type][1]} opacity={n.status === 'idle' ? 0.5 : 0.9} />
              ))}
            </svg>
          </div>
        )}
      </div>
    </div>
  );
}

Object.assign(window, { WorkspaceToolbar, NodePalette, CanvasNode, WorkflowCanvasScreen, nodeHeight });
