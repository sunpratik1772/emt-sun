import { createContext, useContext, useMemo, useState, type ReactNode } from 'react'

export type CodeFormat = 'json' | 'yaml'

export interface CodeEditorToolbarApi {
  format: CodeFormat
  setFormat: (format: CodeFormat) => void
  saving: boolean
  loading: boolean
  hasWorkflow: boolean
  hasContent: boolean
  onCopy: () => void
  onSave: () => void
  onCancel: () => void
}

interface CodeEditorToolbarContextValue {
  api: CodeEditorToolbarApi | null
  register: (api: CodeEditorToolbarApi | null) => void
}

const CodeEditorToolbarContext = createContext<CodeEditorToolbarContextValue | null>(null)

export function CodeEditorToolbarProvider({ children }: { children: ReactNode }) {
  const [api, setApi] = useState<CodeEditorToolbarApi | null>(null)
  const value = useMemo(
    () => ({
      api,
      register: setApi,
    }),
    [api],
  )
  return (
    <CodeEditorToolbarContext.Provider value={value}>{children}</CodeEditorToolbarContext.Provider>
  )
}

export function useCodeEditorToolbar() {
  const ctx = useContext(CodeEditorToolbarContext)
  if (!ctx) {
    throw new Error('useCodeEditorToolbar must be used within CodeEditorToolbarProvider')
  }
  return ctx
}
