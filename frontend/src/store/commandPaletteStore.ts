import { create } from 'zustand'

interface CommandPaletteStore {
  open: boolean
  setOpen: (open: boolean) => void
  toggle: () => void
}

export const useCommandPaletteStore = create<CommandPaletteStore>((set, get) => ({
  open: false,
  setOpen: (open) => set({ open }),
  toggle: () => set({ open: !get().open }),
}))

/** Display label for the command palette shortcut (⌘K on Mac, Ctrl+K elsewhere). */
export function commandPaletteShortcutLabel(): string {
  const isMac =
    typeof navigator !== 'undefined' && /mac/i.test(navigator.platform)
  return isMac ? '⌘K' : 'Ctrl+K'
}

/** Expand node palette and focus its search field. */
export function focusNodeSearch(): void {
  window.dispatchEvent(new CustomEvent('studio:focus-node-search'))
}
