import React from 'react'
import { motion } from 'framer-motion'

type Variant = 'primary' | 'soft' | 'outline' | 'danger' | 'ghost' | 'white'

const VARIANTS: Record<Variant, string> = {
  primary: 'bg-navy text-white hover:bg-[#0F377F]',
  soft:    'bg-cyan-soft text-cyan-deep hover:bg-[#D3EEFB]',
  outline: 'bg-white text-navy border border-line hover:border-cyan/60 hover:bg-mist',
  danger:  'bg-danger text-white hover:bg-[#B92D08]',
  ghost:   'text-cyan-deep hover:bg-cyan-soft',
  white:   'bg-white text-navy hover:bg-cyan-soft',
}

interface ButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: Variant
  loading?: boolean
  /** Looks locked but stays tappable, so it can explain *why* it is locked. */
  locked?: boolean
  children: React.ReactNode
}

export function Button({
  variant = 'primary',
  loading,
  locked,
  children,
  disabled,
  className = '',
  ...rest
}: ButtonProps) {
  const off = disabled || loading
  return (
    <motion.button
      whileTap={{ scale: off ? 1 : 0.98 }}
      disabled={off}
      aria-disabled={locked || off || undefined}
      className={`
        inline-flex items-center justify-center gap-2
        rounded-full min-h-[50px] px-5 text-[14px] font-bold
        transition-colors duration-150
        disabled:opacity-50 disabled:cursor-not-allowed
        ${locked ? 'bg-canvas text-muted border border-dashed border-[#C3D0E0] hover:bg-mist' : VARIANTS[variant]}
        ${className}
      `}
      {...(rest as any)}
    >
      {loading && (
        <span className="w-4 h-4 border-2 border-current border-t-transparent rounded-full animate-spin" />
      )}
      {children}
    </motion.button>
  )
}
