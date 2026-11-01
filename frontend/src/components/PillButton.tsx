import React from 'react'
import { motion } from 'framer-motion'

type Variant = 'gold' | 'blue' | 'outline' | 'danger' | 'white'

const VARIANTS: Record<Variant, string> = {
  gold:    'bg-pp-gold text-ink hover:bg-pp-gold-hover',
  blue:    'bg-cyan text-white hover:bg-cyan-deep',
  outline: 'border-2 border-cyan/40 bg-white text-cyan-deep hover:bg-cyan-soft',
  danger:  'bg-danger text-white hover:bg-[#B92D08]',
  white:   'bg-white text-navy hover:bg-cyan-soft',
}

interface PillButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: Variant
  loading?: boolean
  children: React.ReactNode
}

export function PillButton({
  variant = 'blue',
  loading,
  children,
  disabled,
  className = '',
  ...rest
}: PillButtonProps) {
  return (
    <motion.button
      whileTap={{ scale: disabled || loading ? 1 : 0.97 }}
      disabled={disabled || loading}
      className={`
        inline-flex min-h-[50px] items-center justify-center gap-2
        rounded-full px-6 text-[14px] font-bold
        transition-colors duration-150
        disabled:cursor-not-allowed disabled:opacity-50
        ${VARIANTS[variant]} ${className}
      `}
      {...(rest as any)}
    >
      {loading && <span className="h-4 w-4 animate-spin rounded-full border-2 border-current border-t-transparent" />}
      {children}
    </motion.button>
  )
}
