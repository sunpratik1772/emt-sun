import type { CSSProperties } from 'react'
import { DbSherpaIcon, type BrandLogoVariant } from './DbSherpaIcon'

type BrandMarkProps = {
  size?: number
  className?: string
  style?: CSSProperties
  variant?: BrandLogoVariant
}

export default function BrandMark({ size = 28, className, style, variant }: BrandMarkProps) {
  return (
    <DbSherpaIcon
      size={size}
      className={className}
      variant={variant}
      style={{ flexShrink: 0, ...style }}
    />
  )
}
