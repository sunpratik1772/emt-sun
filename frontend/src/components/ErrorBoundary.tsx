import { Component, type ErrorInfo, type ReactNode } from 'react'

interface Props {
  children: ReactNode
  /** Short label shown in the fallback (e.g. "Copilot", "Canvas"). */
  region?: string
  onReset?: () => void
}

interface State {
  error: Error | null
}

/**
 * Catches render errors in a panel region so one broken component
 * does not crash the entire Studio shell.
 */
export default class ErrorBoundary extends Component<Props, State> {
  state: State = { error: null }

  static getDerivedStateFromError(error: Error): State {
    return { error }
  }

  componentDidCatch(error: Error, info: ErrorInfo): void {
    console.error(`[ErrorBoundary${this.props.region ? `: ${this.props.region}` : ''}]`, error, info)
  }

  private handleReset = (): void => {
    this.setState({ error: null })
    this.props.onReset?.()
  }

  render(): ReactNode {
    if (this.state.error) {
      const label = this.props.region ?? 'This panel'
      return (
        <div
          className="flex flex-col items-center justify-center h-full min-h-[120px] p-6 text-center"
          style={{ color: 'var(--text-2)', background: 'var(--bg-1)' }}
          role="alert"
        >
          <p className="display" style={{ fontSize: 14, fontWeight: 540, color: 'var(--text-0)', marginBottom: 6 }}>
            {label} encountered an error
          </p>
          <p style={{ fontSize: 12, lineHeight: 1.5, maxWidth: 360, marginBottom: 16 }}>
            {this.state.error.message || 'Something went wrong while rendering this view.'}
          </p>
          <button
            type="button"
            onClick={this.handleReset}
            style={{
              fontSize: 12,
              padding: '6px 14px',
              borderRadius: 6,
              border: '1px solid var(--border-soft)',
              background: 'var(--bg-2)',
              color: 'var(--text-0)',
              cursor: 'pointer',
            }}
          >
            Try again
          </button>
        </div>
      )
    }
    return this.props.children
  }
}
