import { create } from 'zustand'

export type ToastVariant = 'success' | 'error' | 'info' | 'warning'

export interface ToastItem {
  id: string
  message: string
  variant: ToastVariant
  createdAt: number
}

interface ToastStore {
  toasts: ToastItem[]
  push: (toast: Omit<ToastItem, 'id' | 'createdAt'> & { duration?: number }) => void
  dismiss: (id: string) => void
}

let seq = 0

export const useToastStore = create<ToastStore>((set, get) => ({
  toasts: [],
  push: ({ message, variant, duration = 4500 }) => {
    const id = `toast-${++seq}`
    set((s) => ({
      toasts: [...s.toasts, { id, message, variant, createdAt: Date.now() }],
    }))
    window.setTimeout(() => get().dismiss(id), duration)
  },
  dismiss: (id) => set((s) => ({ toasts: s.toasts.filter((t) => t.id !== id) })),
}))

export const toast = {
  success: (message: string) => useToastStore.getState().push({ message, variant: 'success' }),
  error: (message: string) => useToastStore.getState().push({ message, variant: 'error', duration: 6000 }),
  info: (message: string) => useToastStore.getState().push({ message, variant: 'info' }),
  warning: (message: string) => useToastStore.getState().push({ message, variant: 'warning', duration: 5500 }),
}
