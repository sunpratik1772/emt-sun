import MicroSparkline from './MicroSparkline'
import type { DashboardStat } from './types'

export default function StatRow({ stats }: { stats: DashboardStat[] }) {
  return (
    <div className="dash-stats">
      {stats.map((stat) => (
        <div key={stat.label} className="dash-stat dash-stat--glass">
          <div className="dash-stat__top">
            <div className="dash-stat__value">{stat.value}</div>
            {stat.sparkline && stat.sparkline.length > 0 ? (
              <MicroSparkline values={stat.sparkline} className="dash-stat__sparkline" />
            ) : null}
          </div>
          <div className="dash-stat__label">{stat.label}</div>
          {stat.sub ? <div className="dash-stat__sub">{stat.sub}</div> : null}
        </div>
      ))}
    </div>
  )
}
