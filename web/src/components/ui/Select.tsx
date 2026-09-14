import React from 'react'
import { ChevronDown } from 'lucide-react'

export interface SelectOption {
  value: string
  label: string
}

export interface SelectProps extends React.SelectHTMLAttributes<HTMLSelectElement> {
  label?: string
  options?: SelectOption[]
  error?: string
}

export const Select = React.forwardRef<HTMLSelectElement, SelectProps>(
  ({ label, options, children, className = '', error, ...props }, ref) => {
    return (
      <div className="w-full flex flex-col gap-1.5">
        {label && <label className="text-xs font-medium text-muted-foreground px-1">{label}</label>}
        <div className="relative">
          <select
            ref={ref}
            className={`flex h-11 w-full appearance-none rounded-2xl border-0 bg-secondary px-4 pr-10 py-2 text-sm text-foreground transition-all cursor-pointer focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary/20 disabled:cursor-not-allowed disabled:opacity-50 ${error ? 'ring-2 ring-destructive' : ''} ${className}`}
            {...props}
          >
            {options
              ? options.map((opt) => (
                  <option key={opt.value} value={opt.value} className="bg-card text-foreground py-1">
                    {opt.label}
                  </option>
                ))
              : children}
          </select>
          <div className="pointer-events-none absolute inset-y-0 right-0 flex items-center pr-3.5 text-muted-foreground">
            <ChevronDown className="h-4 w-4 opacity-60" strokeWidth={1.5} />
          </div>
        </div>
        {error && <span className="text-xs text-destructive px-1">{error}</span>}
      </div>
    )
  }
)
Select.displayName = 'Select'
