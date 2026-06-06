/* dbSherpa Studio — UI Kit components.
   Presentational React components for the Studio dashboard. Exported to window
   so app.jsx can compose them. Icons are Lucide (rendered from <i data-lucide>;
   App calls lucide.createIcons() after each render). */
const { useState, useRef } = React;

/* Brand monogram (logo data-URI is injected by index.html as window.DS_LOGO_DARK) */
function Brand({ size = 20 }) {
  return (
    <div className="rail__brand" title="dbSherpa Studio">
      <img src={window.DS_LOGO_DARK} alt="dbSherpa" style={{ width: size }} />
    </div>
  );
}

function Icon({ name, size }) {
  const style = size ? { width: size, height: size } : undefined;
  return <i data-lucide={name} style={style} />;
}

/* Left navigation rail */
function Rail({ active, onNav, user, theme, onTheme }) {
  const themeOpts = [{ id: 'dark', icon: 'moon' }, { id: 'light', icon: 'sun' }, { id: 'aurora', icon: 'sparkles' }];
  return (
    <nav className="rail">
      <Brand />
      <div className="rail__nav">
        {window.STUDIO_DATA.nav.map((item) => (
          <button
            key={item.id}
            className={'rail__btn' + (active === item.id ? ' rail__btn--active' : '')}
            title={item.label}
            aria-label={item.label}
            aria-current={active === item.id ? 'page' : undefined}
            onClick={() => onNav(item.id)}
          >
            <Icon name={item.icon} />
          </button>
        ))}
      </div>
      <div className="rail__spacer" />
      {onTheme && (
        <div className="rail__themes">
          {themeOpts.map((o) => (
            <button key={o.id} className={'rail__btn' + (theme === o.id ? ' rail__btn--active' : '')}
              title={'Theme: ' + o.id} aria-pressed={theme === o.id} onClick={() => onTheme(o.id)}>
              <Icon name={o.icon} />
            </button>
          ))}
        </div>
      )}
      <div className="rail__avatar" title={user.name}>{user.initials}</div>
    </nav>
  );
}

/* Theme segmented control: dark / light / aurora */
function ThemeSeg({ theme, onChange }) {
  const opts = [
    { id: 'dark', icon: 'moon', label: 'Dark' },
    { id: 'light', icon: 'sun', label: 'Light' },
    { id: 'aurora', icon: 'sparkles', label: 'Aurora' },
  ];
  return (
    <div className="seg" role="group" aria-label="Theme">
      {opts.map((o) => (
        <button
          key={o.id}
          className={'seg__btn' + (theme === o.id ? ' seg__btn--on' : '')}
          title={o.label}
          aria-pressed={theme === o.id}
          onClick={() => onChange(o.id)}
        >
          <Icon name={o.icon} />
        </button>
      ))}
    </div>
  );
}

/* Header: time-aware greeting + tools */
function Header({ greeting, name, onSearch, onNew }) {
  return (
    <header className="head">
      <div className="welcome reveal">
        <div className="welcome__eyebrow">{greeting.date}</div>
        <h1 className="welcome__title">{greeting.hello}, {name}</h1>
        <p className="welcome__sub">Here's what's ready to run or automate today.</p>
      </div>
      <div className="head__tools">
        <button className="search" onClick={onSearch}>
          <Icon name="search" />
          <span>Search Studio…</span>
          <span className="search__kbd">⌘K</span>
        </button>
        <button className="btn btn--ghost" onClick={onNew}>
          <Icon name="plus" /> New workflow
        </button>
      </div>
    </header>
  );
}

/* Sherpa prompt bar + suggestion chips */
function SherpaBar({ onSubmit }) {
  const [value, setValue] = useState('');
  const ref = useRef(null);
  const submit = (e) => { e.preventDefault(); const t = value.trim(); if (t) { onSubmit(t); setValue(''); } };
  return (
    <section className="ai-card">
      <form className="sherpa" onSubmit={submit}>
        <span className="sherpa__icon"><Icon name="sparkles" /></span>
        <input ref={ref} className="sherpa__input" placeholder="Ask Sherpa anything…"
          value={value} onChange={(e) => setValue(e.target.value)} aria-label="Ask Sherpa" />
        <button type="submit" className="sherpa__send" disabled={!value.trim()} aria-label="Send to Sherpa">
          <Icon name="arrow-up-right" />
        </button>
      </form>
      <div className="suggest-label">Suggested for you</div>
      <div className="suggest">
        {window.STUDIO_DATA.suggestions.map((s, i) => (
          <button key={i} className="suggest__chip" onClick={() => { setValue(s); ref.current && ref.current.focus(); }}>
            <span>{s}</span><Icon name="arrow-up-right" />
          </button>
        ))}
      </div>
    </section>
  );
}

/* Tiny sparkline path builder */
function sparkPath(values, w = 96, h = 26) {
  const max = Math.max(...values, 1), min = Math.min(...values, 0);
  const span = max - min || 1;
  const pts = values.map((v, i) => [
    (i / (values.length - 1)) * w,
    h - ((v - min) / span) * (h - 4) - 2,
  ]);
  const line = pts.map((p, i) => (i ? 'L' : 'M') + p[0].toFixed(1) + ',' + p[1].toFixed(1)).join(' ');
  const fill = line + ` L${w},${h} L0,${h} Z`;
  return { line, fill };
}

function StatCard({ stat }) {
  const { line, fill } = sparkPath(stat.spark);
  return (
    <div className="stat">
      <div className="stat__top">
        <div className="stat__val">{stat.value}</div>
        <svg className="stat__spark" viewBox="0 0 96 26" preserveAspectRatio="none">
          <path className="fill" d={fill} /><path className="line" d={line} />
        </svg>
      </div>
      <div className="stat__label">{stat.label}</div>
      <div className={'stat__sub' + (stat.up ? ' stat__sub--up' : '')}>{stat.sub}</div>
    </div>
  );
}

function HealthCard({ health }) {
  return (
    <section className="health">
      <span className="health__blob health__blob--1" />
      <span className="health__blob health__blob--2" />
      <div className="health__c">
        <div className="health__val health__val--success">{health.rate}</div>
        <div className="health__label">Success rate this month</div>
        <p className="health__copy">{health.summary}</p>
        <span className="pill pill--online"><span className="pill__dot" />{health.online ? 'Engine online' : 'Engine offline'}</span>
      </div>
    </section>
  );
}

function ActivityCalendar({ health }) {
  const heat = health.heat;
  const weeks = [];
  for (let i = 0; i < heat.length; i += 7) weeks.push(heat.slice(i, i + 7));
  const tone = (v) => {
    if (v <= 0) return 'var(--bg-3)';
    const pct = Math.min(1, v / 4) * 100;
    return `color-mix(in srgb, var(--heat) ${20 + pct * 0.7}%, var(--bg-3))`;
  };
  return (
    <section className="activity">
      <div className="activity__head">
        <span className="activity__title">Run activity</span>
        <span className="activity__streak">3-week streak</span>
      </div>
      <div className="cal">
        {weeks.map((wk, i) => (
          <div className="cal__week" key={i}>
            {wk.map((v, j) => <span className="cal__cell" key={j} style={{ background: tone(v) }} />)}
          </div>
        ))}
      </div>
      <div className="activity__legend">
        Less
        <span className="cal__cell" style={{ background: 'var(--bg-3)' }} />
        <span className="cal__cell" style={{ background: 'color-mix(in srgb, var(--heat) 45%, var(--bg-3))' }} />
        <span className="cal__cell" style={{ background: 'color-mix(in srgb, var(--heat) 75%, var(--bg-3))' }} />
        <span className="cal__cell" style={{ background: 'var(--heat)' }} />
        More
      </div>
    </section>
  );
}

function WorkflowCard({ wf, onOpen }) {
  const cls = 'wf' + (wf.status === 'success' ? ' wf--success' : wf.status === 'error' ? ' wf--error' : '');
  const statusCls = 'wf__status' + (wf.status === 'success' ? ' wf__status--success' : wf.status === 'error' ? ' wf__status--error' : '');
  return (
    <article className={cls} onClick={onOpen}>
      <div className="wf__head">
        <h3 className="wf__title">{wf.name}</h3>
        <span className="wf__time">{wf.time}</span>
      </div>
      <div className="wf__chips" style={{ marginBottom: '-2px' }}>
        {wf.draft && <span className="chip chip--draft">Draft</span>}
        <span className={statusCls}>{wf.statusLabel}</span>
      </div>
      <p className="wf__nodes">{wf.nodes} nodes</p>
      <div className="wf__chips">{wf.chips.map((c) => <span className="chip" key={c}>{c}</span>)}</div>
      <button className="wf__action">Open Studio <Icon name="arrow-up-right" /></button>
    </article>
  );
}

function NewWorkflowCard({ onNew }) {
  return (
    <article className="wf wf--new" onClick={onNew}>
      <div className="wf--new__icon"><Icon name="plus" /></div>
      <p className="wf--new__hint">Start from scratch or pick a template</p>
    </article>
  );
}

function Toast({ msg }) {
  if (!msg) return null;
  return <div className="toast"><Icon name="sparkles" />{msg}</div>;
}

Object.assign(window, {
  Brand, Icon, Rail, ThemeSeg, Header, SherpaBar,
  StatCard, HealthCard, ActivityCalendar, WorkflowCard, NewWorkflowCard, Toast,
});
