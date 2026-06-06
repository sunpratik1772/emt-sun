export const PANE_LIMITS = {
  paletteWidth: { min: 180, max: 420, def: 224 },
  copilotWidth: { min: 280, max: 640, def: 360 },
} as const

const PANE_KEY = 'dbsherpa:panes:v1'
type PaneSizes = { paletteWidth: number; copilotWidth: number }

export function clampPane(v: number, min: number, max: number): number {
  if (Number.isNaN(v)) return min
  return Math.min(max, Math.max(min, Math.round(v)))
}

export function readPaneSizes(): PaneSizes {
  const defaults = {
    paletteWidth: PANE_LIMITS.paletteWidth.def,
    copilotWidth: PANE_LIMITS.copilotWidth.def,
  }
  if (typeof window === 'undefined') return defaults
  try {
    const raw = window.localStorage.getItem(PANE_KEY)
    if (!raw) return defaults
    const parsed = JSON.parse(raw) as Partial<PaneSizes>
    return {
      paletteWidth: clampPane(parsed.paletteWidth ?? defaults.paletteWidth, PANE_LIMITS.paletteWidth.min, PANE_LIMITS.paletteWidth.max),
      copilotWidth: clampPane(parsed.copilotWidth ?? defaults.copilotWidth, PANE_LIMITS.copilotWidth.min, PANE_LIMITS.copilotWidth.max),
    }
  } catch {
    return defaults
  }
}

export function writePaneSizes(sizes: PaneSizes): void {
  if (typeof window === 'undefined') return
  try {
    window.localStorage.setItem(PANE_KEY, JSON.stringify(sizes))
  } catch {
    /* swallow quota / safari-private errors */
  }
}
