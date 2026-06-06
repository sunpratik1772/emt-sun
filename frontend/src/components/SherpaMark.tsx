import type { CSSProperties } from 'react'
import { useThemeStore } from '../store/themeStore'
import { brandLogoForTheme } from '../lib/brandAssets'
/** Zoom into the PNG mark so baked edge shadow/glow is clipped off on white panels. */
const MARK_ZOOM = 1.55

/** sherpa rail / copilot mark — theme-aware PNG (matches browser favicon). */
export function SherpaMark({
  size = 17,
  className,
  style,
}: {
  size?: number
  className?: string
  style?: CSSProperties
}) {
  const theme = useThemeStore((s) => s.theme)
  const src = brandLogoForTheme(theme)
  const scaled = Math.round(size * MARK_ZOOM)

  return (
    <span
      className={className}
      aria-hidden
      style={{
        display: 'inline-flex',
        alignItems: 'center',
        justifyContent: 'center',
        width: size,
        height: size,
        overflow: 'hidden',
        flexShrink: 0,
        ...style,
      }}
    >
      <img
        src={src}
        alt=""
        draggable={false}
        width={scaled}
        height={scaled}
        style={{ display: 'block', objectFit: 'contain' }}
      />
    </span>
  )
}
