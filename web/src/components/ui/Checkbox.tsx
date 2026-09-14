import React from 'react'
import { Check } from 'lucide-react'

interface CheckboxProps extends Omit<React.InputHTMLAttributes<HTMLInputElement>, 'type'> {
  label?: string
}

export const Checkbox = React.forwardRef<HTMLInputElement, CheckboxProps>(
  ({ label, className = '', checked, onChange, disabled, ...props }, ref) => {
    return (
      <label className={`inline-flex items-center gap-2.5 cursor-pointer select-none group ${disabled ? 'opacity-40 cursor-not-allowed' : ''} ${className}`}>
        <div className="relative flex items-center justify-center shrink-0">
          <input
            type="checkbox"
            className="peer sr-only"
            checked={checked}
            onChange={onChange}
            disabled={disabled}
            ref={ref}
            {...props}
          />
          <div className={`h-5 w-5 rounded-lg flex items-center justify-center transition-all duration-150 ${checked ? 'bg-primary text-primary-foreground' : 'bg-secondary text-transparent hover:bg-accent'}`}>
            <Check className={`h-3 w-3 transition-transform stroke-[2.2] ${checked ? 'scale-100' : 'scale-0'}`} />
          </div>
        </div>
        {label && <span className="text-xs sm:text-sm font-medium text-foreground">{label}</span>}
      </label>
    )
  }
)
Checkbox.displayName = 'Checkbox'
