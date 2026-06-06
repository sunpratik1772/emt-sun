import { describe, expect, it } from 'vitest'
import type { RunLogEntry, ValidationIssue } from '../../types'
import {
  collectErrorHints,
  buildPromptFromThread,
  buildPromptWithApprovedPlan,
  buildThreadMessages,
  extractPlanSteps,
  formatApprovedPlanForChat,
  formatPlanPhaseChatMessage,
  hasBuildPlanContent,
  planPhaseChatAcknowledgement,
  isRunOutputQuestion,
  shouldEditExistingWorkflow,
  stripNextActionFooter,
} from './copilotUtils'

describe('hasBuildPlanContent', () => {
  it('detects numbered pipeline plans', () => {
    const plan = [
      'Plan for your request:',
      '1. Load orders CSV',
      '2. Aggregate revenue by region',
      '3. Export Excel report',
    ].join('\n')
    expect(hasBuildPlanContent(plan)).toBe(true)
  })

  it('ignores footer-only replies', () => {
    const text = [
      'I will wait for your confirmation.',
      '**Next step:** Create **Orders** on the canvas from the plan above.',
      'Should I create **Orders** on the canvas now?',
    ].join('\n\n')
    expect(hasBuildPlanContent(text)).toBe(false)
    expect(stripNextActionFooter(text)).not.toMatch(/Next step/i)
  })
})

describe('planPhaseChatAcknowledgement', () => {
  it('returns a short ack without duplicating plan steps', () => {
    const long = [
      'Here is the plan to create an Excel report:',
      '1. Load orders.csv',
      '2. Join products',
    ].join('\n')
    expect(planPhaseChatAcknowledgement(long)).toBe('Below is the plan.')
  })
})

describe('buildPromptWithApprovedPlan', () => {
  it('appends approved plan steps to the user request', () => {
    const out = buildPromptWithApprovedPlan(
      [{ role: 'user', content: 'Build Excel report from orders' }],
      'Build Excel report',
      ['Load orders.csv', 'Export Excel'],
    )
    expect(out).toContain('Build Excel report from orders')
    expect(out).toContain('Approved plan to build on the canvas')
    expect(out).toContain('1. Load orders.csv')
  })
})

describe('formatApprovedPlanForChat', () => {
  it('formats numbered plan steps for chat', () => {
    expect(formatApprovedPlanForChat(['Load CSV', 'Export Excel'])).toContain(
      '1. Load CSV',
    )
    expect(formatApprovedPlanForChat(['Load CSV', 'Export Excel'])).toContain('**Plan**')
  })
})

describe('formatPlanPhaseChatMessage', () => {
  it('puts the plan before the user approves in chat history', () => {
    const msg = formatPlanPhaseChatMessage(['Load CSV', 'Export Excel'])
    expect(msg).toMatch(/^Below is the plan\.\n\n\*\*Plan\*\*/)
    expect(msg).toContain('1. Load CSV')
  })
})

describe('extractPlanSteps', () => {
  it('pulls numbered steps for the approval modal', () => {
    const plan = [
      'Plan:',
      '1. Load orders CSV',
      '2. Aggregate revenue by region',
      '3. Export Excel report',
    ].join('\n')
    expect(extractPlanSteps(plan)).toEqual([
      'Load orders CSV',
      'Aggregate revenue by region',
      'Export Excel report',
    ])
  })

  it('pulls labeled steps for the approval modal', () => {
    const plan = [
      'Below is the plan.',
      'Load Data: Start by loading the orders.csv dataset.',
      'Join Data: Join orders.csv with products.csv on sku.',
      'Export to Excel: Output the final sorted list.',
    ].join('\n')
    expect(extractPlanSteps(plan).length).toBeGreaterThanOrEqual(3)
  })
})

describe('buildPromptFromThread', () => {
  it('joins all user turns for harness build', () => {
    const thread = [
      { role: 'user', content: 'Build Excel from orders.csv' },
      { role: 'assistant', content: 'Plan...' },
      { role: 'user', content: 'Add GitHub export' },
    ]
    expect(buildPromptFromThread(thread, 'fallback')).toContain('GitHub export')
  })
})

describe('isRunOutputQuestion', () => {
  it('detects run output follow-ups', () => {
    expect(isRunOutputQuestion('ANALYSE THE OUTPUT AND TELL WHAT HAPPENED')).toBe(true)
    expect(isRunOutputQuestion('name top 3 traders from output')).toBe(true)
  })

  it('rejects build commands', () => {
    expect(isRunOutputQuestion('build a workflow that analyzes output')).toBe(false)
  })
})

describe('shouldEditExistingWorkflow', () => {
  it('returns false for create/generate prompts', () => {
    expect(shouldEditExistingWorkflow('Create a new pipeline')).toBe(false)
    expect(shouldEditExistingWorkflow('Generate a workflow from scratch')).toBe(false)
  })

  it('returns true for edit/fix prompts', () => {
    expect(shouldEditExistingWorkflow('Fix the current workflow')).toBe(true)
    expect(shouldEditExistingWorkflow('Add a node to this canvas')).toBe(true)
  })

  it('returns false for yes after a sample-run offer', () => {
    const thread = [
      {
        role: 'assistant' as const,
        content:
          '**Trade summary**\n\n**Next step:** Run **Trade summary** with sample data.\n\nWant me to start a sample run now?',
      },
    ]
    expect(shouldEditExistingWorkflow('yes', { threadMessages: thread })).toBe(false)
  })
})

describe('buildThreadMessages', () => {
  it('returns prior turns and excludes the current message by default', () => {
    const msgs = [
      { role: 'user', content: 'Build pipeline' },
      { role: 'assistant', content: 'Built pipeline' },
      { role: 'user', content: 'Automate at 9:30' },
    ]
    expect(buildThreadMessages(msgs)).toEqual([
      { role: 'user', content: 'Build pipeline' },
      { role: 'assistant', content: 'Built pipeline' },
    ])
  })
})

describe('collectErrorHints', () => {
  it('deduplicates validation and runtime errors', () => {
    const validationIssues: ValidationIssue[] = [
      {
        code: 'MISSING_EDGE',
        message: 'Node n02 has no input',
        severity: 'error',
        node_id: 'n02',
      },
    ]
    const runLog: RunLogEntry[] = [
      {
        node_id: 'n03',
        node_type: 'python',
        label: 'Script',
        index: 1,
        total: 1,
        status: 'error',
        error: 'SyntaxError',
      },
    ]

    const hints = collectErrorHints(validationIssues, runLog, 'Workflow failed')
    expect(hints).toHaveLength(2)
    expect(hints[0].kind).toBe('validation')
    expect(hints[1].message).toContain('python')
  })

  it('omits generic runError when validation issues exist', () => {
    const validationIssues: ValidationIssue[] = [
      { code: 'X', message: 'bad', severity: 'error' },
    ]
    const hints = collectErrorHints(validationIssues, [], 'generic failure')
    expect(hints).toHaveLength(1)
    expect(hints[0].message).toBe('bad')
  })

  it('includes runError when no validation issues', () => {
    const hints = collectErrorHints(null, [], 'Connection refused')
    expect(hints).toEqual([
      { kind: 'runtime', severity: 'error', message: 'Connection refused' },
    ])
  })
})
