import type { Theme } from '../store/themeStore'

export const BRAND_LOGO_LIGHT = '/brand/dbsherpa-logo-light.png'
export const BRAND_LOGO_DARK = '/brand/dbsherpa-logo-dark.png'

export function brandLogoForTheme(theme: Theme): string {
  return theme === 'dark' || theme === 'claude' || theme === 'turquoise'
    ? BRAND_LOGO_DARK
    : BRAND_LOGO_LIGHT
}
