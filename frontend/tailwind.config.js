/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,ts,jsx,tsx}'],
  darkMode: ['class', '[data-theme="dark"]'],
  theme: {
    extend: {
      colors: {
        // Linear/Railway-inspired neutral palette
        bg: '#08090a',
        surface: '#101113',
        card: '#101113',
        elevated: '#16171a',
        border: 'rgba(255, 255, 255, 0.06)',
        'border-strong': 'rgba(255, 255, 255, 0.10)',
        muted: '#5d5d66',
        'text-primary': '#ededee',
        'text-secondary': '#8b8b94',
        'text-tertiary': '#5d5d66',
        primary: '#ededee',
        accent: '#2d9fc4',

        'port-dataframe': '#f59e0b',
        'port-object': '#38bdf8',
        'port-scalar': '#3ecf8e',
        'port-string-list': '#7c83ff',
        'port-workflow': '#f472b6',

        success: '#3ecf8e',
        danger: '#f87171',
        warning: '#f59e0b',
        info: '#60a5fa',
      },
      fontFamily: {
        sans: ['Geist Variable', 'Geist', 'system-ui', '-apple-system', 'BlinkMacSystemFont', 'sans-serif'],
        heading: ['Geist Variable', 'Geist', 'system-ui', '-apple-system', 'BlinkMacSystemFont', 'sans-serif'],
        mono: ['Geist Mono Variable', 'Geist Mono', 'ui-monospace', 'monospace'],
        display: ['Ronzino', 'system-ui', '-apple-system', 'BlinkMacSystemFont', 'sans-serif'],
      },
      keyframes: {
        'blink-soft': {
          '0%, 100%': { opacity: '1' },
          '50%': { opacity: '0.5' },
        },
        dashflow: {
          to: { strokeDashoffset: '-20' },
        },
      },
      animation: {
        'blink-soft': 'blink-soft 1.6s ease-in-out infinite',
        dashflow: 'dashflow 0.9s linear infinite',
      },
    },
  },
  plugins: [],
}
