/** Deep links and navigation helpers for studio sections. */
import { useStudioSectionStore } from '../store/studioSectionStore'

export function automationDeepLink(automationId: string): string {
  const base = `${window.location.pathname}${window.location.search}`
  return `${base}#automations/${encodeURIComponent(automationId)}`
}

export function parseAutomationHash(hash: string): string | null {
  const match = hash.match(/^#automations\/([^/?#]+)/)
  return match ? decodeURIComponent(match[1]) : null
}

export function openAutomation(automationId: string): void {
  useStudioSectionStore.getState().openAutomation(automationId)
}

export function clearAutomationDeepLink(): void {
  const { pathname, search } = window.location
  if (window.location.hash.startsWith('#automations/')) {
    window.history.replaceState(null, '', `${pathname}${search}`)
  }
}
