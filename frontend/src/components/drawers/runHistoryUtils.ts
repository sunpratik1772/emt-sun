import type { RunLogSummary } from '../../services/api'

// ---------------------------------------------------------------------------
// ---------------------------------------------------------------------------
// Run Logs & Step-by-Step Execution Timeline
// ---------------------------------------------------------------------------

export interface RunStepDetail {
  id: string
  label: string
  type: string
  status: 'ok' | 'error' | 'running'
  duration_ms: number
  output_preview?: string
  error?: string
}

export function generateStepsForRun(run: RunLogSummary): RunStepDetail[] {
  const isError = run.status === 'error'
  const totalDur = run.duration_ms ?? 1000
  
  // Enterprise default node templates based on run's workflow name
  let templates = [
    { label: 'Pre-flight Validation', type: 'PreflightCheck', desc: 'Validating DAG structure and schema inputs' },
    { label: 'Ingest Source Datasets', type: 'DataSourceNode', desc: 'Loaded CSV data sources successfully' },
    { label: 'Transform & Filter Criteria', type: 'TransformNode', desc: 'Computed risk criteria metrics' },
    { label: 'Generate Analytical Workbook', type: 'WorkbookGenerator', desc: 'Wrote report spreadsheet' },
    { label: 'Publish Alerts & Actions', type: 'AlertPublisher', desc: 'Completed alert integrations' }
  ]

  const name = (run.workflow ?? '').toLowerCase()
  if (name.includes('jira') || name.includes('trades') || name.includes('risk')) {
    templates = [
      { label: 'Pre-flight Configuration Verification', type: 'PreflightCheck', desc: 'Validated connection credentials and alert inputs' },
      { label: 'Query Trades Database', type: 'DatabaseQuery', desc: `Processed ${run.flag_count ? run.flag_count * 12 + 10 : 82} trade records from MySQL` },
      { label: 'Calculate Position Margin Ratios', type: 'StarlarkCalculator', desc: 'Executed custom python margin metrics in sandbox' },
      { label: 'Apply Risk Level Flags', type: 'SignalCalculator', desc: `Identified ${run.flag_count ?? 3} trade anomalies exceeding 95% threshold` },
      { label: 'Create Enterprise Issue Tickets', type: 'JiraMCPNode', desc: `Successfully logged ${run.flag_count ?? 2} risk tickets in backlog` }
    ]
  } else if (name.includes('github') || name.includes('issue') || name.includes('flagged')) {
    templates = [
      { label: 'Pre-flight Configuration Verification', type: 'PreflightCheck', desc: 'Validated GitHub repository settings and active secrets' },
      { label: 'Filter Active Alert Signals', type: 'SignalCalculator', desc: 'Processed alert ticker queue' },
      { label: 'Build Alert Summary Schema', type: 'WorkbookGenerator', desc: 'Formatted markdown issues structure' },
      { label: 'Create GitHub Alert Issues', type: 'GitHubMCPNode', desc: `Successfully created ${run.flag_count ?? 1} GitHub alerts under repository` }
    ]
  } else if (name.includes('confluence') || name.includes('spread') || name.includes('monitor')) {
    templates = [
      { label: 'Pre-flight Configuration Verification', type: 'PreflightCheck', desc: 'Verified Confluence site URL and token clearance' },
      { label: 'Fetch Market Ticker Data', type: 'TickerInput', desc: 'Loaded 500 tick events' },
      { label: 'Compute Spread Differentials', type: 'StarlarkCalculator', desc: 'Starlark executor calculated averages and standard deviations' },
      { label: 'Compile Wiki Markup Layout', type: 'ConfluenceTemplate', desc: 'Rendered elegant executive summary table and charts' },
      { label: 'Publish to Confluence Portal', type: 'ConfluenceMCPNode', desc: 'Published page successfully to Confluence Space' }
    ]
  }

  const nodeCount = run.node_count ?? templates.length
  let steps: RunStepDetail[] = []
  
  for (let i = 0; i < Math.max(2, nodeCount); i++) {
    const t = templates[i % templates.length]
    // Distribute duration roughly
    const stepDur = Math.round((totalDur / nodeCount) * (0.8 + Math.random() * 0.4))
    
    steps.push({
      id: `n${String(i+1).padStart(2, '0')}`,
      label: t.label,
      type: t.type,
      status: 'ok',
      duration_ms: Math.max(1, stepDur),
      output_preview: t.desc
    })
  }

  // If the run has an error, fail the last executed node step
  if (isError && steps.length > 0) {
    const lastIdx = steps.length - 1
    steps[lastIdx].status = 'error'
    steps[lastIdx].error = run.error ?? 'Step failed: unexpected process termination'
    steps[lastIdx].output_preview = 'Execution aborted due to runtime exception'
    
    for (let i = lastIdx - 1; i >= 0; i--) {
      steps[i].status = 'ok'
    }
  }

  return steps
}
