import { createContext, useContext, useMemo, type ReactNode } from 'react'
import { useDashboardSherpaContent } from '../../hooks/useDashboardSherpaContent'

type DashboardSherpaFeed = ReturnType<typeof useDashboardSherpaContent>

const DashboardSherpaContext = createContext<DashboardSherpaFeed | null>(null)

/** One fetch per dashboard visit; remounts on navigation back or full page refresh. */
export function DashboardSherpaProvider({ children }: { children: ReactNode }) {
  const mountNonce = useMemo(() => Date.now(), [])
  const feed = useDashboardSherpaContent(3, true, mountNonce)

  return (
    <DashboardSherpaContext.Provider value={feed}>{children}</DashboardSherpaContext.Provider>
  )
}

export function useDashboardSherpaFeed(): DashboardSherpaFeed {
  const feed = useContext(DashboardSherpaContext)
  if (!feed) {
    throw new Error('useDashboardSherpaFeed must be used within DashboardSherpaProvider')
  }
  return feed
}
