import type { CSSProperties } from 'react'
import { useThemeStore } from '../store/themeStore'
import { BRAND_LOGO_DARK, BRAND_LOGO_LIGHT, brandLogoForTheme } from '../lib/brandAssets'

export type BrandLogoVariant = 'auto' | 'on-dark' | 'on-light'

/** dbSherpa product mark — theme-aware PNG (matches browser favicon). */
export function DbSherpaIcon({
  size = 24,
  className,
  style,
  alt = '',
  variant = 'auto',
}: {
  size?: number
  className?: string
  style?: CSSProperties
  alt?: string
  variant?: BrandLogoVariant
}) {
  const theme = useThemeStore((s) => s.theme)
  const src =
    variant === 'on-dark'
      ? BRAND_LOGO_DARK
      : variant === 'on-light'
        ? BRAND_LOGO_LIGHT
        : brandLogoForTheme(theme)

  return (
    <img
      src={src}
      width={size}
      height={size}
      alt={alt}
      aria-hidden={alt ? undefined : true}
      className={className}
      draggable={false}
      style={{
        display: 'block',
        objectFit: 'contain',
        flexShrink: 0,
        ...style,
      }}
    />
  )
}
