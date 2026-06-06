import { useEffect, useState } from 'react'

/** True when viewport is below the studio desktop breakpoint. */
export function useCompactStudio(threshold = 1024): boolean {
  const [compact, setCompact] = useState(() =>
    typeof window !== 'undefined' ? window.matchMedia(`(max-width: ${threshold - 1}px)`).matches : false,
  )

  useEffect(() => {
    const mq = window.matchMedia(`(max-width: ${threshold - 1}px)`)
    const update = () => setCompact(mq.matches)
    mq.addEventListener('change', update)
    update()
    return () => mq.removeEventListener('change', update)
  }, [threshold])

  return compact
}
