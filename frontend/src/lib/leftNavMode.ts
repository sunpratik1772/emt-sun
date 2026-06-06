export type LeftNavMode = 'expanded' | 'collapsed' | 'hover'

export const LEFT_NAV_MODE_KEY = 'dbsherpa.leftnav.mode'

export const LEFT_NAV_MODE_EVENT = 'sheep:leftnav-mode'

export function getLeftNavMode(): LeftNavMode {
  if (typeof window === 'undefined') return 'hover'
  const saved = window.localStorage.getItem(LEFT_NAV_MODE_KEY) as LeftNavMode | null
  return saved ?? 'hover'
}

export function setLeftNavMode(mode: LeftNavMode): void {
  if (typeof window === 'undefined') return
  window.localStorage.setItem(LEFT_NAV_MODE_KEY, mode)
  window.dispatchEvent(new CustomEvent(LEFT_NAV_MODE_EVENT, { detail: mode }))
}
