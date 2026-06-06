import type { Monaco } from '@monaco-editor/react'
import type { Theme } from '../store/themeStore'

export type SherpaMonacoTheme = 'sherpa-dark' | 'sherpa-light' | 'sherpa-turquoise' | 'sherpa-claude'

const MONACO_THEME_IDS: Record<Theme, SherpaMonacoTheme> = {
  dark: 'sherpa-dark',
  light: 'sherpa-light',
  turquoise: 'sherpa-turquoise',
  claude: 'sherpa-claude',
}

export function sherpaMonacoThemeId(theme: Theme): SherpaMonacoTheme {
  return MONACO_THEME_IDS[theme]
}

const DARK_RULES = [
  { token: 'comment', foreground: '62666d', fontStyle: 'italic' },
  { token: 'string', foreground: '98c379' },
  { token: 'number', foreground: 'd19a66' },
  { token: 'keyword', foreground: 'e5c07b' },
  { token: 'type', foreground: '61afef' },
  { token: 'key', foreground: '61afef' },
] as const

const LIGHT_RULES = [
  { token: 'comment', foreground: '8aa0ad', fontStyle: 'italic' },
  { token: 'string', foreground: '1f7a4a' },
  { token: 'number', foreground: 'b45309' },
  { token: 'keyword', foreground: '92600a' },
  { token: 'type', foreground: '1d6fb8' },
  { token: 'key', foreground: '1d6fb8' },
] as const

interface MonacoPalette {
  background: string
  foreground: string
  lineNumber: string
  lineNumberActive: string
  lineHighlight: string
  accent: string
  widgetBackground: string
  widgetBorder: string
  scrollbar: string
  scrollbarHover: string
  scrollbarActive: string
}

/** Static palettes mirror globals.css tokens — avoids reading CSS before data-theme flips. */
const PALETTES: Record<Theme, MonacoPalette> = {
  dark: {
    background: '#08090a',
    foreground: '#ffffff',
    lineNumber: '#71717a',
    lineNumberActive: '#a1a1aa',
    lineHighlight: '#0f1011',
    accent: '#3eb5db',
    widgetBackground: '#141516',
    widgetBorder: 'rgba(255, 255, 255, 0.14)',
    scrollbar: 'rgba(255, 255, 255, 0.12)',
    scrollbarHover: 'rgba(255, 255, 255, 0.22)',
    scrollbarActive: 'rgba(255, 255, 255, 0.28)',
  },
  light: {
    background: '#ffffff',
    foreground: '#0a0a0a',
    lineNumber: '#737373',
    lineNumberActive: '#525252',
    lineHighlight: '#ebebeb',
    accent: '#2489ab',
    widgetBackground: '#f5f5f5',
    widgetBorder: 'rgba(0, 0, 0, 0.12)',
    scrollbar: 'rgba(0, 0, 0, 0.14)',
    scrollbarHover: 'rgba(0, 0, 0, 0.24)',
    scrollbarActive: 'rgba(0, 0, 0, 0.32)',
  },
  turquoise: {
    background: '#f6fbfb',
    foreground: '#172a33',
    lineNumber: '#6a828c',
    lineNumberActive: '#526871',
    lineHighlight: '#e3f2f2',
    accent: '#2e8a86',
    widgetBackground: '#e1efef',
    widgetBorder: 'rgba(20, 60, 70, 0.12)',
    scrollbar: 'rgba(20, 60, 70, 0.14)',
    scrollbarHover: 'rgba(20, 60, 70, 0.24)',
    scrollbarActive: 'rgba(20, 60, 70, 0.32)',
  },
  claude: {
    background: '#fcfaf6',
    foreground: '#2e2319',
    lineNumber: '#9a8b7a',
    lineNumberActive: '#7a6b5c',
    lineHighlight: '#f4efe6',
    accent: '#cc6a3d',
    widgetBackground: '#f4efe6',
    widgetBorder: 'rgba(80, 50, 20, 0.10)',
    scrollbar: 'rgba(80, 50, 20, 0.14)',
    scrollbarHover: 'rgba(80, 50, 20, 0.24)',
    scrollbarActive: 'rgba(80, 50, 20, 0.32)',
  },
}

function scrollbarFromCss(theme: Theme): {
  scrollbar: string
  scrollbarHover: string
  scrollbarActive: string
} | null {
  if (typeof document === 'undefined') return null
  const style = getComputedStyle(document.documentElement)
  const thumb = style.getPropertyValue('--scrollbar-thumb').trim()
  const hover = style.getPropertyValue('--scrollbar-thumb-hover').trim()
  const active = style.getPropertyValue('--scrollbar-thumb-active').trim()
  if (!thumb) return null
  return {
    scrollbar: thumb,
    scrollbarHover: hover || thumb,
    scrollbarActive: active || hover || thumb,
  }
}

function selectionBackground(accent: string): string {
  return `${accent}33`
}

function buildThemeColors(theme: Theme) {
  const palette = { ...PALETTES[theme], ...scrollbarFromCss(theme) }
  return {
    'editor.background': palette.background,
    'editor.foreground': palette.foreground,
    'editorLineNumber.foreground': palette.lineNumber,
    'editorLineNumber.activeForeground': palette.lineNumberActive,
    'editor.selectionBackground': selectionBackground(palette.accent),
    'editor.lineHighlightBackground': palette.lineHighlight,
    'editorCursor.foreground': palette.accent,
    'editorWidget.background': palette.widgetBackground,
    'editorWidget.border': palette.widgetBorder,
    'editorGutter.background': palette.background,
    'scrollbarSlider.background': palette.scrollbar,
    'scrollbarSlider.hoverBackground': palette.scrollbarHover,
    'scrollbarSlider.activeBackground': palette.scrollbarActive,
    'scrollbar.shadow': 'transparent',
    'editorOverviewRuler.background': palette.background,
    'editorOverviewRuler.border': palette.widgetBorder,
    'overviewRuler.border': palette.widgetBorder,
    'overviewRuler.errorForeground': 'transparent',
    'overviewRuler.warningForeground': 'transparent',
    'overviewRuler.infoForeground': 'transparent',
  }
}

/** Register both Sherpa themes and activate the one matching `theme`. */
export function applySherpaMonacoTheme(monaco: Monaco, theme: Theme): SherpaMonacoTheme {
  monaco.editor.defineTheme('sherpa-dark', {
    base: 'vs-dark',
    inherit: true,
    rules: [...DARK_RULES],
    colors: buildThemeColors('dark'),
  })

  monaco.editor.defineTheme('sherpa-light', {
    base: 'vs',
    inherit: true,
    rules: [...LIGHT_RULES],
    colors: buildThemeColors('light'),
  })

  monaco.editor.defineTheme('sherpa-turquoise', {
    base: 'vs',
    inherit: true,
    rules: [...LIGHT_RULES],
    colors: buildThemeColors('turquoise'),
  })

  monaco.editor.defineTheme('sherpa-claude', {
    base: 'vs',
    inherit: true,
    rules: [...LIGHT_RULES],
    colors: buildThemeColors('claude'),
  })

  const id = sherpaMonacoThemeId(theme)
  monaco.editor.setTheme(id)
  return id
}
