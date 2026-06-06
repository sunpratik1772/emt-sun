/* dbSherpa Studio — UI Kit app shell. Routes the rail nav across surfaces:
   Dashboard · Workflow canvas · Sherpa Copilot · Node Library · Run History ·
   Automations. Theme (dark/light/aurora) lives in the rail and applies globally. */

function greetingFor(d = new Date()) {
  const h = d.getHours();
  const hello = h < 12 ? 'Good morning' : h < 18 ? 'Good afternoon' : 'Good evening';
  const date = d.toLocaleDateString('en-US', { weekday: 'long', month: 'long', day: 'numeric' });
  return { hello, date };
}

const SCREEN_NAVS = ['dashboard', 'workflow', 'agent', 'nodes', 'runs', 'automations'];

function DashboardScreen({ D, greeting, flash }) {
  return (
    <div className="scroll">
      <div className="inner">
        <Header greeting={greeting} name={D.user.name}
          onSearch={() => flash('Command palette — ⌘K')} onNew={() => flash('New workflow — opening Studio…')} />
        <SherpaBar onSubmit={(t) => flash('Sherpa is planning: "' + truncate(t) + '"')} />
        <div className="content">
          <div className="stats">{D.stats.map((s) => <StatCard key={s.label} stat={s} />)}</div>
          <div className="insight">
            <HealthCard health={D.health} />
            <ActivityCalendar health={D.health} />
          </div>
          <div>
            <div className="wf-head">
              <span className="wf-head__title">Recent workflows</span>
              <button className="wf-head__link" onClick={() => flash('Opening workflow library…')}>
                View all <Icon name="arrow-up-right" size={13} />
              </button>
            </div>
            <div className="wf-grid">
              {D.workflows.slice(0, 3).map((wf) => (
                <WorkflowCard key={wf.id} wf={wf} onOpen={() => flash('Opening "' + wf.name + '"')} />
              ))}
              <NewWorkflowCard onNew={() => flash('New workflow — opening Studio…')} />
              {D.workflows.slice(3).map((wf) => (
                <WorkflowCard key={wf.id} wf={wf} onOpen={() => flash('Opening "' + wf.name + '"')} />
              ))}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

function App() {
  const D = window.STUDIO_DATA;
  const [theme, setTheme] = React.useState(() => localStorage.getItem('dssk:theme') || window.DS_INIT_THEME || 'aurora');
  const [nav, setNav] = React.useState(window.DS_INIT_SCREEN || 'dashboard');
  const [toast, setToast] = React.useState('');
  const greeting = greetingFor();

  React.useEffect(() => {
    document.documentElement.setAttribute('data-theme', theme);
    localStorage.setItem('dssk:theme', theme);
  }, [theme]);

  React.useEffect(() => { if (window.lucide) window.lucide.createIcons({ attrs: { 'stroke-width': 1.75 } }); });

  React.useEffect(() => {
    if (!toast) return;
    const id = setTimeout(() => setToast(''), 2400);
    return () => clearTimeout(id);
  }, [toast]);

  const flash = (m) => setToast(m);

  function handleNav(id) {
    if (SCREEN_NAVS.includes(id)) setNav(id);
    else flash(navMsg(id));
  }

  return (
    <div className="studio">
      <div className="studio-backdrop" aria-hidden />
      <Rail active={nav} onNav={handleNav} user={D.user} theme={theme} onTheme={setTheme} />
      <div className="main">
        {nav === 'dashboard' && <DashboardScreen D={D} greeting={greeting} flash={flash} />}

        {(nav === 'workflow' || nav === 'agent') && (
          <div style={{ display: 'flex', flex: 1, minHeight: 0, minWidth: 0 }}>
            <NodePalette onAdd={(n) => flash('Added ' + n)} />
            <WorkflowCanvasScreen flash={flash} />
            {nav === 'agent' && <AgentPanel flash={flash} onClose={() => setNav('workflow')} />}
          </div>
        )}

        {nav === 'nodes' && <NodeLibraryScreen flash={flash} />}
        {nav === 'runs' && <RunHistoryScreen flash={flash} />}
        {nav === 'automations' && <AutomationsScreen flash={flash} />}
      </div>
      <Toast msg={toast} />
    </div>
  );
}

function truncate(s, n = 38) { return s.length > n ? s.slice(0, n) + '…' : s; }
function navMsg(id) {
  const map = { data: 'Data Sources', settings: 'Settings' };
  return (map[id] || 'Section') + ' — demo view';
}

ReactDOM.createRoot(document.getElementById('root')).render(<App />);
