import { useCallback, useEffect, useLayoutEffect, useMemo, useRef, useState } from 'react'
import Editor, { type Monaco, type OnMount } from '@monaco-editor/react'
import '../../lib/monacoSetup'
import { applySherpaMonacoTheme, sherpaMonacoThemeId } from '../../lib/monacoTheme'
import { useWorkflowStore } from '../../store/workflowStore'
import { useThemeStore } from '../../store/themeStore'
import AsyncFallback from '../AsyncFallback'
import { api } from '../../services/api'
import { toast } from '../../store/toastStore'
import { useCodeEditorToolbar, type CodeFormat } from '../WorkspaceToolbar/context'
import type { Workflow } from '../../types'

const FONT_SIZE = 12.5
const LINE_HEIGHT = 19
const FONT_FAMILY = "'Geist Mono Variable', 'Geist Mono', ui-monospace, monospace"

export default function WorkflowCodeEditor() {
  const workflow = useWorkflowStore((s) => s.workflow)
  const setWorkflow = useWorkflowStore((s) => s.setWorkflow)
  const resetRun = useWorkflowStore((s) => s.resetRun)
  const workspaceEditMode = useWorkflowStore((s) => s.workspaceEditMode)
  const setWorkspaceEditMode = useWorkflowStore((s) => s.setWorkspaceEditMode)
  const appTheme = useThemeStore((s) => s.theme)
  const { register } = useCodeEditorToolbar()

  const [format, setFormat] = useState<CodeFormat>('json')
  const [content, setContent] = useState('')
  const [loading, setLoading] = useState(false)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const monacoRef = useRef<Monaco | null>(null)
  const editorRef = useRef<Parameters<OnMount>[0] | null>(null)

  const editing = workspaceEditMode === 'edit'
  const language = format === 'json' ? 'json' : 'yaml'
  const monacoTheme = sherpaMonacoThemeId(appTheme)
  const readOnly = !editing || loading
  const editorPath = format === 'json' ? 'workflow.json' : 'workflow.yaml'

  const syncTheme = useCallback(
    (monaco: Monaco) => {
      monacoRef.current = monaco
      applySherpaMonacoTheme(monaco, appTheme)
    },
    [appTheme],
  )

  useLayoutEffect(() => {
    if (!monacoRef.current) return
    applySherpaMonacoTheme(monacoRef.current, appTheme)
    editorRef.current?.layout()
  }, [appTheme])

  useEffect(() => {
    let cancelled = false
    async function syncFromWorkflow() {
      if (!workflow) {
        if (!cancelled) {
          setContent('')
          setError(null)
        }
        return
      }
      setLoading(true)
      setError(null)
      try {
        if (format === 'json') {
          if (!cancelled) setContent(JSON.stringify(workflow, null, 2))
        } else {
          const { content: yaml } = await api.workflowToYaml(workflow)
          if (!cancelled) setContent(yaml)
        }
      } catch (e) {
        if (!cancelled) setError((e as Error).message)
      } finally {
        if (!cancelled) setLoading(false)
      }
    }
    void syncFromWorkflow()
    return () => {
      cancelled = true
    }
  }, [workflow, format])

  const handleCopy = useCallback(async () => {
    try {
      await navigator.clipboard.writeText(content)
      toast.success('Copied to clipboard')
    } catch {
      toast.error('Could not copy code to clipboard.')
    }
  }, [content])

  const applyCodeChanges = useCallback(async () => {
    if (!workflow) return
    setSaving(true)
    setError(null)
    try {
      const nextWorkflow: Workflow =
        format === 'json'
          ? (JSON.parse(content) as Workflow)
          : (await api.workflowFromYaml(content)).workflow
      setWorkflow(nextWorkflow)
      resetRun()
    } catch (e) {
      setError((e as Error).message)
    } finally {
      setSaving(false)
    }
  }, [workflow, format, content, setWorkflow, resetRun])

  const cancelEditing = useCallback(() => {
    setWorkspaceEditMode('view')
    setError(null)
    if (!workflow) return
    if (format === 'json') {
      setContent(JSON.stringify(workflow, null, 2))
      return
    }
    void api.workflowToYaml(workflow).then((resp) => setContent(resp.content)).catch(() => void 0)
  }, [workflow, format, setWorkspaceEditMode])

  useLayoutEffect(() => {
    register({
      format,
      setFormat,
      saving,
      loading,
      hasWorkflow: !!workflow,
      hasContent: !!content,
      onCopy: () => {
        void handleCopy()
      },
      onSave: () => {
        void applyCodeChanges()
      },
      onCancel: cancelEditing,
    })
    return () => register(null)
  }, [
    register,
    format,
    saving,
    loading,
    workflow,
    content,
    handleCopy,
    applyCodeChanges,
    cancelEditing,
  ])

  const handleBeforeMount = useCallback(
    (monaco: Monaco) => {
      syncTheme(monaco)
    },
    [syncTheme],
  )

  const handleMount: OnMount = useCallback((editor, monaco) => {
    editorRef.current = editor
    syncTheme(monaco)
    editor.updateOptions({ readOnly })
  }, [readOnly, syncTheme])

  useEffect(() => {
    editorRef.current?.updateOptions({ readOnly })
  }, [readOnly])

  const editorOptions = useMemo(
    () => ({
      readOnly,
      minimap: { enabled: false },
      fontSize: FONT_SIZE,
      lineHeight: LINE_HEIGHT,
      fontFamily: FONT_FAMILY,
      fontLigatures: false,
      scrollBeyondLastLine: false,
      wordWrap: 'on' as const,
      automaticLayout: true,
      padding: { top: 12, bottom: 12 },
      lineNumbers: 'on' as const,
      renderLineHighlight: editing ? ('line' as const) : ('none' as const),
      overviewRulerLanes: 0,
      overviewRulerBorder: false,
      hideCursorInOverviewRuler: true,
      scrollbar: {
        vertical: 'auto' as const,
        horizontal: 'auto' as const,
        verticalScrollbarSize: 8,
        horizontalScrollbarSize: 8,
        useShadows: false,
        verticalHasArrows: false,
        horizontalHasArrows: false,
        alwaysConsumeMouseWheel: false,
      },
      tabSize: 2,
      insertSpaces: true,
      occurrencesHighlight: editing ? ('multiFile' as const) : ('off' as const),
      selectionHighlight: editing,
      codeLens: false,
      folding: editing,
      quickSuggestions: editing,
      suggestOnTriggerCharacters: editing,
      parameterHints: { enabled: editing },
      hover: { enabled: editing },
      links: editing,
      colorDecorators: false,
      matchBrackets: editing ? ('always' as const) : ('never' as const),
      renderValidationDecorations: editing ? ('on' as const) : ('off' as const),
      smoothScrolling: false,
      cursorSmoothCaretAnimation: 'off' as const,
      contextmenu: editing,
      formatOnPaste: editing,
      formatOnType: editing,
    }),
    [editing, readOnly],
  )

  return (
    <div className="absolute inset-0 flex flex-col min-h-0" style={{ background: 'transparent' }}>
      <div className="flex-1 min-h-0 px-3 pb-3 flex flex-col">
        <div
          className="flex-1 min-h-0 overflow-hidden"
          style={{
            borderRadius: 10,
            border: '1px solid var(--border)',
            background: 'var(--bg-0)',
          }}
        >
          {loading ? (
            <AsyncFallback label={`Loading ${format === 'json' ? 'JSON' : 'YAML'}…`} />
          ) : (
            <Editor
              height="100%"
              path={editorPath}
              language={language}
              theme={monacoTheme}
              value={content}
              beforeMount={handleBeforeMount}
              onMount={handleMount}
              onChange={(value) => {
                if (editing && !loading) setContent(value ?? '')
              }}
              loading={<AsyncFallback label="Starting editor…" />}
              options={editorOptions}
            />
          )}
        </div>
        {error && (
          <div className="font-mono" style={{ marginTop: 8, fontSize: 11, color: 'var(--danger)' }}>
            {error}
          </div>
        )}
      </div>
    </div>
  )
}
