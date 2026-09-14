import React from 'react'

export interface ButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: 'primary' | 'secondary' | 'outline' | 'ghost' | 'destructive' | 'action'
  size?: 'sm' | 'md' | 'lg' | 'icon'
  loading?: boolean
}

export const Button: React.FC<ButtonProps> = ({
  variant = 'primary',
  size = 'md',
  loading = false,
  className = '',
  disabled,
  children,
  ...props
}) => {
  const baseStyles =
    'relative inline-flex items-center justify-center text-center font-medium transition-all duration-150 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 select-none cursor-pointer active:scale-[0.98]'

  const variants = {
    primary:
      'bg-primary text-primary-foreground hover:opacity-90 shadow-xs rounded-full border-0',
    action:
      'bg-foreground text-background hover:opacity-90 shadow-xs rounded-full border-0 tracking-tight',
    secondary:
      'bg-secondary text-secondary-foreground hover:bg-accent rounded-full border-0',
    outline:
      'bg-secondary text-foreground hover:bg-accent rounded-full border-0',
    ghost:
      'text-muted-foreground hover:text-foreground hover:bg-secondary rounded-full border-0',
    destructive:
      'bg-destructive text-destructive-foreground hover:opacity-90 rounded-full border-0',
  }

  const sizes = {
    sm: 'h-8 px-3 text-xs gap-1.5',
    md: 'h-10 px-4 text-sm gap-2',
    lg: 'h-11 px-5 text-sm gap-2.5',
    icon: 'h-10 w-10 shrink-0 p-0',
  }

  const isActuallyDisabled = disabled && !loading

  return (
    <button
      disabled={disabled || loading}
      aria-busy={loading}
      className={`
        ${baseStyles}
        ${variants[variant]}
        ${sizes[size]}
        ${isActuallyDisabled ? 'opacity-40 pointer-events-none cursor-not-allowed' : ''}
        ${loading ? 'cursor-wait pointer-events-none' : ''}
        ${className}
      `}
      {...props}
    >
      {loading && (
        <span className="absolute inset-0 flex items-center justify-center z-10">
          <span className="h-4 w-4 animate-spin rounded-full border-2 border-current border-t-transparent" />
        </span>
      )}
      <span
        className={`inline-flex items-center justify-center gap-1.5 text-center w-full transition-opacity ${
          loading ? 'invisible select-none pointer-events-none' : 'visible'
        }`}
      >
        {children}
      </span>
    </button>
  )
}

