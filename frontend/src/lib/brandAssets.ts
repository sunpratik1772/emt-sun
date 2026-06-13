import type { Theme } from '../store/themeStore'

export const BRAND_LOGO_LIGHT = '/brand/dbsherpa-logo-light.png'
export const BRAND_LOGO_DARK = '/brand/dbsherpa-logo-dark.png'

export function brandLogoForTheme(theme: Theme): string {
  // ripeplanet has a light cream ground → use the dark-on-light logo.
  // dark + altermind use the light-on-dark logo.
  return theme === 'ripeplanet' ? BRAND_LOGO_LIGHT : BRAND_LOGO_DARK
}
