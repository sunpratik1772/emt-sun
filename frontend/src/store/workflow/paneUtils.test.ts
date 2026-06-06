import { describe, expect, it } from 'vitest'
import { clampPane, PANE_LIMITS } from './paneUtils'

describe('clampPane', () => {
  it('clamps within min and max', () => {
    expect(clampPane(100, 180, 420)).toBe(180)
    expect(clampPane(500, 180, 420)).toBe(420)
    expect(clampPane(250, 180, 420)).toBe(250)
  })

  it('rounds to nearest integer', () => {
    expect(clampPane(250.6, 180, 420)).toBe(251)
  })

  it('returns min for NaN', () => {
    expect(clampPane(Number.NaN, PANE_LIMITS.paletteWidth.min, PANE_LIMITS.paletteWidth.max)).toBe(
      PANE_LIMITS.paletteWidth.min,
    )
  })
})
