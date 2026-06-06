import { AgentIcon } from '../Copilot/AgentChrome'

/** Full-canvas veil while Sherpa streams a build/load workflow onto the canvas. */
export function SherpaCanvasGeneratingOverlay() {
  return (
    <div
      className="workflow-canvas__generating-veil"
      role="status"
      aria-live="polite"
      aria-label="Generating workflow"
    >
      <div className="workflow-canvas__generating-card">
        <AgentIcon live size={30} />
        <div className="workflow-canvas__generating-copy">
          <span className="workflow-canvas__generating-label">Generating</span>
          <span className="workflow-canvas__generating-dots" aria-hidden>
            <span className="workflow-canvas__generating-dot" />
            <span className="workflow-canvas__generating-dot" />
            <span className="workflow-canvas__generating-dot" />
          </span>
        </div>
      </div>
    </div>
  )
}
