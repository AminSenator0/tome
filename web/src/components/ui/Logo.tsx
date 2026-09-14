import React from 'react'

interface LogoProps {
  className?: string
  size?: number
  withText?: boolean
}

export const Logo: React.FC<LogoProps> = ({ className = '', size = 28, withText = true }) => {
  return (
    <div className={`flex items-center gap-2 select-none ${className}`}>
      <svg
        width={size}
        height={size}
        viewBox="0 0 48 48"
        fill="none"
        xmlns="http://www.w3.org/2000/svg"
        className="shrink-0 text-muted-foreground"
      >
        <text
          x="24"
          y="34"
          fontSize="36"
          fontWeight="bold"
          fontFamily='"Helvetica Neue", Helvetica, sans-serif'
          fill="currentColor"
          textAnchor="middle"
        >
          *.
        </text>
      </svg>
      {withText && (
        <span className="font-semibold text-lg tracking-tight text-foreground font-sans">
          Tome
        </span>
      )}
    </div>
  )
}
