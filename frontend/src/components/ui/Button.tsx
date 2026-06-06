import type { ButtonHTMLAttributes, ReactNode } from 'react'

export type ButtonVariant = 'primary' | 'secondary' | 'ghost' | 'danger' | 'stop' | 'icon'
export type ButtonSize = 'sm' | 'md'

type ButtonProps = ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: ButtonVariant
  size?: ButtonSize
  fullWidth?: boolean
  lift?: boolean
  children?: ReactNode
}

export function Button({
  variant = 'secondary',
  size = 'md',
  fullWidth = false,
  lift = true,
  className = '',
  type = 'button',
  children,
  ...props
}: ButtonProps) {
  const classes = [
    'btn',
    `btn--${variant}`,
    variant !== 'icon' ? `btn--${size}` : '',
    fullWidth ? 'btn--full' : '',
    lift ? 'lift' : '',
    className,
  ]
    .filter(Boolean)
    .join(' ')

  return (
    <button type={type} className={classes} {...props}>
      {children}
    </button>
  )
}
