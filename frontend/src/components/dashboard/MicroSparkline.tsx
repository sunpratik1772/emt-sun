/** Lightweight SVG sparkline for dashboard stat cards. */
export default function MicroSparkline({
  values,
  className = '',
}: {
  values: number[]
  className?: string
}) {
  const series = values.length > 0 ? values : [0]
  const w = 120
  const h = 28
  const max = Math.max(1, ...series)
  const step = series.length > 1 ? w / (series.length - 1) : w

  const points = series
    .map((v, i) => {
      const x = i * step
      const y = h - 4 - (v / max) * (h - 8)
      return `${x.toFixed(1)},${y.toFixed(1)}`
    })
    .join(' ')

  const areaPoints = `${points} ${w},${h} 0,${h}`

  return (
    <svg
      className={`dash-sparkline ${className}`.trim()}
      viewBox={`0 0 ${w} ${h}`}
      preserveAspectRatio="none"
      aria-hidden
    >
      <polygon className="dash-sparkline__fill" points={areaPoints} />
      <polyline className="dash-sparkline__line" points={points} />
    </svg>
  )
}
