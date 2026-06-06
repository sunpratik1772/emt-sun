import { describe, expect, it } from 'vitest'
import {
  buildSherpaStarterContext,
  ensureStarterPromptCount,
  isSherpaWorkspaceEmpty,
  isVagueSherpaSuggestion,
  personalizeStarterPrompts,
  referencesMissingWorkflow,
  resolveStarterPrompts,
} from './sherpaStarterPrompts'
import type { WorkflowCatalogEntry } from './workflowLibrary'

function entry(name: string, kind: 'saved' | 'draft' = 'draft'): WorkflowCatalogEntry {
  return {
    canonical_name: name,
    filename: `${name.toLowerCase().replace(/\s+/g, '-')}.json`,
    kind,
    workflow_id: null,
    updated_ms: Date.now(),
  }
}

const emptyCtx = buildSherpaStarterContext([], [])

describe('isVagueSherpaSuggestion', () => {
  it('rejects generic draft filler', () => {
    expect(
      isVagueSherpaSuggestion(
        'Finish my draft workflow: connect the open nodes and add a CSV export at the end.',
      ),
    ).toBe(true)
  })

  it('accepts prompts with workflow names and integrations', () => {
    expect(
      isVagueSherpaSuggestion(
        'Improve "FX Surveillance" with validation, a failure branch, and an Outlook summary when the run completes.',
      ),
    ).toBe(false)
  })
})

describe('isSherpaWorkspaceEmpty', () => {
  it('is true when catalog is empty', () => {
    expect(isSherpaWorkspaceEmpty(emptyCtx)).toBe(true)
  })
})

describe('referencesMissingWorkflow', () => {
  const withReal = buildSherpaStarterContext([entry('Real Workflow', 'saved')], [])

  it('rejects edit-this-workflow phrasing', () => {
    expect(
      referencesMissingWorkflow('Edit this workflow and add a CSV export.', emptyCtx),
    ).toBe(true)
  })

  it('rejects quoted names not in the catalog', () => {
    expect(
      referencesMissingWorkflow('Improve "Ghost Pipeline" with validation.', withReal),
    ).toBe(true)
  })

  it('rejects run review when the workflow has no stored runs', () => {
    expect(
      referencesMissingWorkflow('Review the latest run of "Real Workflow" and suggest fixes.', withReal),
    ).toBe(true)
  })

  it('rejects run review for orphan run logs not in the catalog', () => {
    const ctx = buildSherpaStarterContext([entry('Real Workflow', 'saved')], [
      { started_at: new Date().toISOString(), workflow: 'Ghost Pipeline' },
    ])
    expect(
      referencesMissingWorkflow('Review the latest run of "Ghost Pipeline" and suggest fixes.', ctx),
    ).toBe(true)
  })

  it('accepts run review for a catalog workflow with stored runs', () => {
    const ctx = buildSherpaStarterContext([entry('Real Workflow', 'saved')], [
      { started_at: new Date().toISOString(), workflow: 'Real Workflow' },
    ])
    expect(
      referencesMissingWorkflow('Review the latest run of "Real Workflow" and suggest fixes.', ctx),
    ).toBe(false)
  })

  it('rejects workflow-specific prompts when the workspace is empty', () => {
    expect(
      referencesMissingWorkflow('Did it analyze the last run of this workflow?', emptyCtx),
    ).toBe(true)
  })
})

describe('personalizeStarterPrompts', () => {
  it('returns discovery prompts when workspace is empty', () => {
    const out = personalizeStarterPrompts(
      [{ label: 'mcp', text: 'Publish via confluence_mcp after hs_trades.', fromAi: false }],
      emptyCtx,
      5,
    )
    expect(out.length).toBeGreaterThan(0)
    expect(out.some((p) => p.text.includes('export workflow results'))).toBe(true)
    expect(out.some((p) => p.text.toLowerCase().includes('improve "'))).toBe(false)
  })

  it('injects run suggestion only for catalog names', () => {
    const out = personalizeStarterPrompts(
      [],
      buildSherpaStarterContext([entry('My Draft Report')], []),
      5,
    )
    expect(
      out.some((p) => p.text.includes('Run "My Draft Report" with sample alert context')),
    ).toBe(true)
  })
})

describe('ensureStarterPromptCount', () => {
  it('always returns three dashboard suggestions for an empty workspace', () => {
    const out = ensureStarterPromptCount([], 3, emptyCtx)
    expect(out).toHaveLength(3)
    expect(out.every((p) => !referencesMissingWorkflow(p.text, emptyCtx))).toBe(true)
  })

  it('always returns five side-panel suggestions for an empty workspace', () => {
    const out = ensureStarterPromptCount([], 5, emptyCtx)
    expect(out).toHaveLength(5)
  })
})

describe('resolveStarterPrompts', () => {
  it('skips registry fallbacks when allowRegistryFallbacks is false', () => {
    expect(resolveStarterPrompts([], [], 5, { allowRegistryFallbacks: false })).toEqual([])
  })

  it('filters vague rows from AI prompt lists', () => {
    const out = resolveStarterPrompts(
      [
        {
          text: 'Finish my draft workflow: connect the open nodes and add a CSV export at the end.',
          tag: 'csv',
        },
        {
          text: 'Build a GitHub activity briefing from `github` commits and publish via Outlook.',
          tag: 'github',
        },
      ],
      [],
      5,
    )
    expect(out).toHaveLength(1)
    expect(out[0]?.text).toContain('GitHub')
  })
})
