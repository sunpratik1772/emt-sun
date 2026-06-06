import type { DashboardIntegration } from './types'

function statusLabel(status: DashboardIntegration['status']): string {
  if (status === 'connected') return 'Connected'
  if (status === 'partial') return 'Configure'
  return 'Off'
}

export default function IntegrationsStrip({
  integrations,
  onOpenSettings,
}: {
  integrations: DashboardIntegration[]
  onOpenSettings?: () => void
}) {
  return (
    <section className="dash-panel dash-panel--compact">
      <div className="dash-panel__head-row">
        <h2 className="dash-section-title">Integrations</h2>
        <button type="button" className="dash-link-btn dash-link-btn--sm" onClick={onOpenSettings}>
          Settings
        </button>
      </div>
      <ul className="dash-int-list">
        {integrations.map((item) => (
          <li key={item.id} className="dash-int-item">
            <div className="dash-int-item__text">
              <span className="dash-int-item__label">{item.label}</span>
              <span className="dash-int-item__detail">{item.detail}</span>
            </div>
            <div className="dash-int-capsules" aria-label={statusLabel(item.status)}>
              {[0, 1, 2].map((i) => (
                <span
                  key={i}
                  className={`dash-int-capsule${
                    (item.status === 'connected' && i < 3) ||
                    (item.status === 'partial' && i < 2)
                      ? ' dash-int-capsule--on'
                      : ''
                  }`}
                />
              ))}
            </div>
          </li>
        ))}
      </ul>
    </section>
  )
}
