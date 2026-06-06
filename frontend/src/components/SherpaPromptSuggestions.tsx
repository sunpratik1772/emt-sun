import { useMemo } from 'react'
import { PromptStatusRow } from './Copilot/CopilotUi'
import { useSherpaStarterPrompts } from '../hooks/useSherpaStarterPrompts'
import {
  buildSherpaStarterContext,
  type SherpaStarterContext,
  type SherpaStarterPrompt,
} from '../lib/sherpaStarterPrompts'
import { useWorkflowStore } from '../store/workflowStore'
import { useRunLogs, useWorkflowCatalog } from '../hooks/useLibraryQueries'

type Variant = 'canvas' | 'dashboard' | 'copilot' | 'home'

type PromptFeed = {
  prompts: SherpaStarterPrompt[]
  loading: boolean
  aiReady: boolean
  status: 'loading' | 'ready' | 'error'
}

export default function SherpaPromptSuggestions({
  onSelect,
  variant = 'dashboard',
  limit = 5,
  context: contextOverride,
  hasCanvasWorkflow: hasCanvasWorkflowProp,
  prompts: promptsOverride,
  loading: loadingOverride,
  aiReady: aiReadyOverride,
  status: statusOverride,
}: {
  onSelect: (text: string) => void
  variant?: Variant
  limit?: number
  context?: SherpaStarterContext
  hasCanvasWorkflow?: boolean
  prompts?: SherpaStarterPrompt[]
  loading?: boolean
  aiReady?: boolean
  status?: 'loading' | 'ready' | 'error'
}) {
  const useInternalFeed = promptsOverride === undefined

  const { data: catalog = [] } = useWorkflowCatalog(
    useInternalFeed && (variant === 'home' || variant === 'copilot'),
  )
  const { data: runLogs = [] } = useRunLogs(
    useInternalFeed && (variant === 'home' || variant === 'copilot'),
    400,
  )

  const canvasWorkflow = useWorkflowStore((s) => s.workflow)
  const context = useMemo(() => {
    if (!useInternalFeed) return contextOverride
    if (contextOverride) return contextOverride
    if (variant !== 'home' && variant !== 'copilot') return undefined
    const onCanvas = Boolean(canvasWorkflow?.nodes?.length)
    return buildSherpaStarterContext(catalog, runLogs, {
      hasCanvasWorkflow: hasCanvasWorkflowProp ?? onCanvas,
    })
  }, [
    contextOverride,
    useInternalFeed,
    variant,
    catalog,
    runLogs,
    canvasWorkflow,
    hasCanvasWorkflowProp,
  ])

  const internal = useSherpaStarterPrompts(
    useInternalFeed ? limit : 0,
    context,
    variant === 'copilot' ? undefined : undefined,
  )

  const feed: PromptFeed = useInternalFeed
    ? {
        prompts: internal.prompts,
        loading: internal.loading,
        aiReady: internal.aiReady,
        status: internal.status,
      }
    : {
        prompts: promptsOverride ?? [],
        loading: loadingOverride ?? false,
        aiReady: aiReadyOverride ?? false,
        status: statusOverride ?? 'ready',
      }

  const { prompts, loading, aiReady, status } = feed

  const rootClass =
    variant === 'canvas'
      ? 'sherpa-suggestions sherpa-suggestions--canvas'
      : variant === 'copilot'
        ? 'sherpa-suggestions sherpa-suggestions--copilot'
        : variant === 'home'
          ? 'sherpa-suggestions sherpa-suggestions--home'
          : 'sherpa-suggestions sherpa-suggestions--dashboard'

  const showFullText = variant === 'copilot' || variant === 'home'
  const showTryHeader = variant === 'canvas' || variant === 'dashboard'

  if (!prompts.length && !loading) return null

  return (
    <div className={rootClass} role="list" aria-label="Suggested Sherpa prompts">
      {variant === 'home' ? (
        <p className="sherpa-suggestions__intro" aria-live="polite">
          {loading && !aiReady
            ? 'Sherpa is tailoring workflows for you…'
            : 'Suggested for you'}
        </p>
      ) : null}

      {showTryHeader ? (
        <div className="sherpa-suggestions__head">
          <span className="sherpa-suggestions__label">Try</span>
          {loading && !aiReady ? (
            <span className="sherpa-suggestions__status" aria-live="polite">
              Generating…
            </span>
          ) : aiReady ? (
            <span className="sherpa-suggestions__status sherpa-suggestions__status--ready">AI</span>
          ) : null}
        </div>
      ) : null}

      {status !== 'ready' && status !== 'loading' && prompts.length === 0 ? (
        <PromptStatusRow status={status} />
      ) : (
        <div className={`sherpa-suggestions__list${showFullText ? ' sherpa-suggestions__list--full' : ''}`}>
          {prompts.map((prompt) => (
            <button
              key={prompt.text}
              type="button"
              role="listitem"
              className={[
                'sherpa-suggestions__chip',
                showFullText ? 'sherpa-suggestions__chip--full' : '',
                variant === 'home' ? 'sherpa-suggestions__chip--home' : '',
                prompt.fromAi ? 'sherpa-suggestions__chip--ai' : '',
                loading && !aiReady ? 'sherpa-suggestions__chip--loading' : '',
              ]
                .filter(Boolean)
                .join(' ')}
              title={prompt.text}
              data-testid={`sherpa-suggestion-${prompt.label}`}
              onClick={() => onSelect(prompt.text)}
            >
              <span className="sherpa-suggestions__chip-text">
                {showFullText ? prompt.text : prompt.label}
              </span>
            </button>
          ))}
        </div>
      )}
    </div>
  )
}
