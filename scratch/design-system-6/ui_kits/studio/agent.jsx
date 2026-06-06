/* dbSherpa Studio — Sherpa Copilot (agent) side panel.
   Faithful to Copilot/index.tsx, CopilotChatInput.tsx, SherpaRouteChips.tsx. */

function AgentMessage({ m }) {
  if (m.role === 'user') return <div className="msg-user">{m.text}</div>;
  if (m.role === 'thinking') {
    return (
      <div className="think">
        <div className="think__head"><Icon name="sparkles" /> Thought for a few seconds</div>
        <div className="think__steps">
          {m.steps.map((s, i) => (
            <div className="think__step" key={i}>
              <span className="think__bullet"><Icon name="check" /></span>
              <div>
                <div className="think__step-label">{s.label}</div>
                <div className="think__step-detail">{s.detail}</div>
              </div>
            </div>
          ))}
        </div>
      </div>
    );
  }
  // assistant — render light markdown (**bold**, `code`)
  const html = m.text
    .replace(/&/g, '&amp;').replace(/</g, '&lt;')
    .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
    .replace(/`(.+?)`/g, '<code>$1</code>');
  return (
    <div className="msg-asst">
      <span className="msg-asst__avatar"><Icon name="sparkles" /></span>
      <div className="msg-asst__body" dangerouslySetInnerHTML={{ __html: html }} />
    </div>
  );
}

function AgentPanel({ flash, onClose, wfName = 'Lead scoring pipeline', nodeCount = 6 }) {
  const [value, setValue] = React.useState('');
  const taRef = React.useRef(null);
  const endRef = React.useRef(null);
  const submit = () => { const t = value.trim(); if (!t) return; flash('Sherpa: "' + (t.length > 40 ? t.slice(0, 40) + '…' : t) + '"'); setValue(''); };

  return (
    <aside className="agent">
      <div className="agent__head">
        <span className="agent__avatar"><Icon name="sparkles" /></span>
        <span className="agent__title">sherpa</span>
        <div className="agent__tools">
          <button className="agent__tool" title="Chat history" onClick={() => flash('Chat history')}><Icon name="clock" /></button>
          <button className="agent__tool" title="New chat" onClick={() => flash('New chat')}><Icon name="message-square" /></button>
          {onClose && <button className="agent__tool" title="Close" onClick={onClose}><Icon name="x" /></button>}
        </div>
      </div>

      <div className="agent__msgs">
        {window.AGENT_THREAD.map((m, i) => <AgentMessage key={i} m={m} />)}
        <div ref={endRef} />
      </div>

      <div className="routes">
        <div className="routes__head">
          <span className="routes__label">Routes</span>
          <span className="routes__hint">Press \ or tap a route</span>
        </div>
        <div className="routes__list">
          {window.AGENT_ROUTES.map((r) => (
            <button className="route-chip" key={r.command} onClick={() => { setValue(r.command + ' '); taRef.current && taRef.current.focus(); }}>
              <span className="route-chip__cmd">{r.command}</span>
              <span className="route-chip__name">{r.label}</span>
            </button>
          ))}
        </div>
      </div>

      <div className="agent__input">
        <div className="agent__chip"><Icon name="wrench" /><span>Editing "{wfName}" · {nodeCount} nodes</span></div>
        <div className="agent__box">
          <textarea ref={taRef} className="agent__ta" rows={1} placeholder="Ask Sherpa to build or edit…"
            value={value} onChange={(e) => setValue(e.target.value)}
            onKeyDown={(e) => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); submit(); } }} />
          <button className="agent__send" disabled={!value.trim()} onClick={submit} aria-label="Send"><Icon name="arrow-up" /></button>
        </div>
        <div className="agent__foot">⏎ send · ⇧⏎ newline · \ for routes · /run /build /check-run</div>
      </div>
    </aside>
  );
}

Object.assign(window, { AgentPanel, AgentMessage });
