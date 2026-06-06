/* dbSherpa Studio — Node Library, Run History, Automations screens.
   Node data from nodes/generated.ts; runs/automations from RunHistoryDrawer +
   AutomationsDrawer mock shapes. */

function ScreenHeader({ eyebrow, title, sub, children }) {
  return (
    <div className="screen__head">
      <div>
        {eyebrow && <div className="screen__eyebrow">{eyebrow}</div>}
        <div className="screen__title">{title}</div>
        {sub && <div className="screen__sub">{sub}</div>}
      </div>
      {children}
    </div>
  );
}

function NodeLibraryScreen({ flash }) {
  const sections = window.PALETTE_SECTIONS.map((sec) => ({
    ...sec, types: Object.entries(window.NODE_UI).filter(([, m]) => m[3] === sec.id),
  })).filter((s) => s.types.length);
  const total = Object.keys(window.NODE_UI).length;
  return (
    <div className="screen">
      <div className="screen__inner">
        <ScreenHeader eyebrow="Building blocks" title="Node Library"
          sub={`${total} nodes across ${sections.length} categories — drag onto the canvas or ask Sherpa.`}>
          <button className="btn btn--ghost" onClick={() => flash('Search nodes')}><Icon name="search" /> Search</button>
        </ScreenHeader>
        {sections.map((sec) => (
          <section className="nlib-sec" key={sec.id}>
            <div className="nlib-sec__head">
              <span className="nlib-sec__accent" style={{ background: sec.color }} />
              <span className="nlib-sec__label">{sec.label}</span>
              <span className="pal-sec__count">{sec.types.length}</span>
            </div>
            <div className="nlib-grid">
              {sec.types.map(([type, m]) => {
                const [name, color, icon, , desc] = m;
                return (
                  <article className="nlib-card" key={type} onClick={() => flash('Add ' + name)}>
                    <span className="nlib-card__ico" style={{ background: `color-mix(in srgb, ${color} 16%, transparent)`, color }}>
                      <Icon name={icon} />
                    </span>
                    <div style={{ minWidth: 0 }}>
                      <div className="nlib-card__name">{name}</div>
                      <div className="nlib-card__type">{type}</div>
                      <div className="nlib-card__desc">{desc}</div>
                    </div>
                  </article>
                );
              })}
            </div>
          </section>
        ))}
      </div>
    </div>
  );
}

function runTone(s) { return s === 'success' ? 'var(--success)' : s === 'error' ? 'var(--danger)' : 'var(--running)'; }

function RunHistoryScreen({ flash }) {
  return (
    <div className="screen">
      <div className="screen__inner">
        <ScreenHeader eyebrow="Execution log" title="Run History"
          sub="Every workflow run with status, duration, and rows processed.">
          <button className="btn btn--ghost" onClick={() => flash('Filter runs')}><Icon name="list-filter" /> Filter</button>
        </ScreenHeader>
        <div className="runs-table">
          <div className="runs-row runs-row--head">
            <span></span><span>Workflow</span><span>When</span><span>Duration</span><span>Rows</span><span>Status</span>
          </div>
          {window.RUNS.map((r) => (
            <div className="runs-row" key={r.id} onClick={() => flash('Open run ' + r.id)} style={{ cursor: 'pointer' }}>
              <span className="runs-status" style={{ background: runTone(r.status) }} />
              <div style={{ minWidth: 0 }}>
                <div className="runs-wf">{r.wf}</div>
                {r.err && <div className="runs-err">{r.err}</div>}
                {!r.err && <div className="runs-when" style={{ marginTop: 2 }}>{r.nodes} nodes</div>}
              </div>
              <span className="runs-when">{r.when}</span>
              <span className="runs-cell">{r.dur}</span>
              <span className="runs-cell">{r.rows == null ? '—' : r.rows.toLocaleString()}</span>
              <span>
                <span className="runs-badge" style={{ background: `color-mix(in srgb, ${runTone(r.status)} 13%, transparent)`, color: runTone(r.status) }}>
                  <span className="runs-status" style={{ background: runTone(r.status), width: 6, height: 6 }} />
                  {r.status === 'success' ? 'Succeeded' : r.status === 'error' ? 'Failed' : 'Running'}
                </span>
              </span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

function AutomationsScreen({ flash }) {
  const [items, setItems] = React.useState(window.AUTOMATIONS);
  const toggle = (id) => setItems((arr) => arr.map((a) => a.id === id ? { ...a, active: !a.active } : a));
  return (
    <div className="screen">
      <div className="screen__inner">
        <ScreenHeader eyebrow="Running on autopilot" title="Automations"
          sub="Workflows scheduled to run on a cron — toggle, inspect last run, and see what's next.">
          <button className="btn btn--ghost" onClick={() => flash('Schedule a workflow')}><Icon name="plus" /> New schedule</button>
        </ScreenHeader>
        <div className="autom-grid">
          {items.map((a) => (
            <article className="autom-card" key={a.id}>
              <span className="autom-card__ico"><Icon name="clock" /></span>
              <div className="autom-card__main">
                <div className="autom-card__name">{a.wf}</div>
                <div className="autom-card__cron"><code>{a.cron}</code>{a.human}</div>
              </div>
              <div className="autom-card__meta">
                <div className="autom-card__next">Next: {a.active ? a.next : '—'}</div>
                <div className="autom-card__last">{a.active ? a.last : 'Paused'}</div>
              </div>
              <button className={'sw-toggle' + (a.active ? ' sw-toggle--on' : '')} aria-pressed={a.active}
                title={a.active ? 'Active' : 'Paused'} onClick={() => { toggle(a.id); flash((a.active ? 'Paused ' : 'Activated ') + a.wf); }}>
                <span className="sw-toggle__knob" />
              </button>
            </article>
          ))}
        </div>
      </div>
    </div>
  );
}

Object.assign(window, { ScreenHeader, NodeLibraryScreen, RunHistoryScreen, AutomationsScreen });
