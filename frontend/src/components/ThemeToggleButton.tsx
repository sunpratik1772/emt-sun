import { ArcIcon, Droplets, Moon, Palette, Sun } from '../icons/arc'
import { useThemeStore } from '../store/themeStore'

type ThemeToggleVariant = 'studio' | 'dashboard'

export default function ThemeToggleButton({ variant = 'studio' }: { variant?: ThemeToggleVariant }) {
  const theme = useThemeStore((s) => s.theme)
  const toggleTheme = useThemeStore((s) => s.toggle)
  const label =
    theme === 'dark'
      ? 'Switch to light mode'
      : theme === 'light'
        ? 'Switch to turquoise mode'
        : theme === 'turquoise'
          ? 'Switch to Claude mode'
          : theme === 'claude'
            ? 'Switch to dark mode'
            : 'Switch to dark mode'
  const icon =
    theme === 'dark' ? Sun : theme === 'light' ? Droplets : theme === 'turquoise' ? Palette : Moon

  if (variant === 'dashboard') {
    return (
      <button
        type="button"
        className="dash-topbar__icon-btn"
        onClick={toggleTheme}
        title={label}
        aria-label={label}
      >
        <ArcIcon icon={icon} size={16} strokeWidth={2} />
      </button>
    )
  }

  return (
    <button
      type="button"
      onClick={toggleTheme}
      title={label}
      aria-label={label}
      className="flex items-center justify-center studio-topbar-theme-btn"
    >
      <ArcIcon icon={icon} size={14} strokeWidth={2} />
    </button>
  )
}
