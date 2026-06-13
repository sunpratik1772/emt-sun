import type { Monaco } from '@monaco-editor/react'
import type { Theme } from '../store/themeStore'

export type SherpaMonacoTheme = 'sherpa-dark' | 'sherpa-altermind' | 'sherpa-ripeplanet'

const MONACO_THEME_IDS: Record<Theme, SherpaMonacoTheme> = {
  dark: 'sherpa-dark',
  altermind: 'sherpa-altermind',
  ripeplanet: 'sherpa-ripeplanet',
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

const RIPEPLANET_RULES = [
  { token: 'comment', foreground: '7f7f7f', fontStyle: 'italic' },
  { token: 'string', foreground: '005955' },
  { token: 'number', foreground: 'a3725c' },
  { token: 'keyword', foreground: 'b86b66' },
  { token: 'type', foreground: '00403d' },
  { token: 'key', foreground: '00403d' },
] as const

const ALTERMIND_RULES = [
  { token: 'comment', foreground: '7d8c87', fontStyle: 'italic' },
  { token: 'string', foreground: 'b7d4a5' },
  { token: 'number', foreground: 'e6c98c' },
  { token: 'keyword', foreground: 'e8d9b0' },
  { token: 'type', foreground: 'a8d4cf' },
  { token: 'key', foreground: 'a8d4cf' },
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
  ripeplanet: {
    background: '#ffffff',
    foreground: '#040404',
    lineNumber: '#7f7f7f',
    lineNumberActive: '#4c4c4c',
    lineHighlight: '#f2efeb',
    accent: '#d3817a',
    widgetBackground: '#dddad7',
    widgetBorder: 'rgba(4, 4, 4, 0.10)',
    scrollbar: 'rgba(4, 4, 4, 0.14)',
    scrollbarHover: 'rgba(4, 4, 4, 0.24)',
    scrollbarActive: 'rgba(4, 4, 4, 0.32)',
  },
  altermind: {
    background: '#0a1f1c',
    foreground: '#f5f1e8',
    lineNumber: '#7d8c87',
    lineNumberActive: '#a8b5b0',
    lineHighlight: '#0f2925',
    accent: '#d4c9a8',
    widgetBackground: '#0f2925',
    widgetBorder: 'rgba(245, 241, 232, 0.12)',
    scrollbar: 'rgba(245, 241, 232, 0.12)',
    scrollbarHover: 'rgba(245, 241, 232, 0.22)',
    scrollbarActive: 'rgba(245, 241, 232, 0.28)',
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

export function applySherpaMonacoTheme(monaco: Monaco, theme: Theme): SherpaMonacoTheme {
  monaco.editor.defineTheme('sherpa-dark', {
    base: 'vs-dark',
    inherit: true,
    rules: [...DARK_RULES],
    colors: buildThemeColors('dark'),
  })

  monaco.editor.defineTheme('sherpa-ripeplanet', {
    base: 'vs',
    inherit: true,
    rules: [...RIPEPLANET_RULES],
    colors: buildThemeColors('ripeplanet'),
  })

  monaco.editor.defineTheme('sherpa-altermind', {
    base: 'vs-dark',
    inherit: true,
    rules: [...ALTERMIND_RULES],
    colors: buildThemeColors('altermind'),
  })

  const id = sherpaMonacoThemeId(theme)
  monaco.editor.setTheme(id)
  return id
}
