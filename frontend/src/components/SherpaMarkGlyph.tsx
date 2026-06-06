import { useId } from 'react'
import type { CSSProperties } from 'react'
import { BRAND_LOGO_DARK, BRAND_LOGO_LIGHT } from '../lib/brandAssets'

export type MarkSurface = 'on-dark' | 'on-light'

const MASK = {
  'on-dark': { src: BRAND_LOGO_DARK, viewBox: '0 0 164 186' },
  'on-light': { src: BRAND_LOGO_LIGHT, viewBox: '0 0 268 340' },
} as const

/** Transparent dS monogram — PNG is used only as a luminance mask, not a visible tile. */
export function SherpaMarkGlyph({
  size = 17,
  surface = 'on-light',
  className,
  style,
}: {
  size?: number
  surface?: MarkSurface
  className?: string
  style?: CSSProperties
}) {
  const maskId = useId().replace(/:/g, '')
  const { src, viewBox } = MASK[surface]

  return (
    <svg
      width={size}
      height={size}
      viewBox={viewBox}
      className={className}
      aria-hidden
      style={{ display: 'block', flexShrink: 0, ...style }}
    >
      <defs>
        <mask id={maskId} maskUnits="userSpaceOnUse" x="0" y="0" width="100%" height="100%">
          <image href={src} width="100%" height="100%" preserveAspectRatio="xMidYMid meet" />
        </mask>
      </defs>
      <rect width="100%" height="100%" fill="currentColor" mask={`url(#${maskId})`} />
    </svg>
  )
}
