import React from 'react'

export interface InputProps extends React.InputHTMLAttributes<HTMLInputElement> {
  label?: string
  error?: string
}

export const Input = React.forwardRef<HTMLInputElement, InputProps>(
  ({ label, error, className = '', ...props }, ref) => {
    return (
      <div className="w-full flex flex-col gap-1.5">
        {label && <label className="text-xs font-medium text-muted-foreground px-1">{label}</label>}
        <input
          ref={ref}
          className={`flex h-11 w-full rounded-2xl border-0 bg-secondary px-4 py-2 text-sm text-foreground transition-all placeholder:text-muted-foreground/50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary/20 disabled:cursor-not-allowed disabled:opacity-50 ${error ? 'ring-2 ring-destructive' : ''} ${className}`}
          {...props}
        />
        {error && <span className="text-xs text-destructive px-1">{error}</span>}
      </div>
    )
  }
)
Input.displayName = 'Input'

export interface TextareaProps extends React.TextareaHTMLAttributes<HTMLTextAreaElement> {
  label?: string
  error?: string
}

export const Textarea = React.forwardRef<HTMLTextAreaElement, TextareaProps>(
  ({ label, error, className = '', ...props }, ref) => {
    return (
      <div className="w-full flex flex-col gap-1.5">
        {label && <label className="text-xs font-medium text-muted-foreground px-1">{label}</label>}
        <div className="relative rounded-2xl overflow-hidden bg-secondary">
          <textarea
            ref={ref}
            className={`flex min-h-[120px] w-full border-0 bg-transparent px-4 py-3 text-sm text-foreground transition-all placeholder:text-muted-foreground/50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary/20 disabled:cursor-not-allowed disabled:opacity-50 custom-scrollbar ${error ? 'ring-2 ring-destructive' : ''} ${className}`}
            {...props}
          />
        </div>
        {error && <span className="text-xs text-destructive px-1">{error}</span>}
      </div>
    )
  }
)
Textarea.displayName = 'Textarea'
