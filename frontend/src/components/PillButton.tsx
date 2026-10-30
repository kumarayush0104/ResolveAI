import React from 'react'
import { motion } from 'framer-motion'

type Variant = 'gold' | 'blue' | 'outline' | 'danger'

const VARIANTS: Record<Variant, string> = {
  gold:    'bg-pp-gold hover:bg-pp-gold-hover text-[#2C2E2F] font-semibold shadow-sm',
  blue:    'bg-pp-blue hover:bg-pp-blue-dark text-white font-semibold shadow-sm',
  outline: 'border-2 border-pp-blue text-pp-blue hover:bg-blue-50 font-medium',
  danger:  'bg-danger hover:bg-red-700 text-white font-semibold shadow-sm',
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
      whileHover={{ scale: disabled || loading ? 1 : 1.02 }}
      whileTap={{ scale: disabled || loading ? 1 : 0.97 }}
      disabled={disabled || loading}
      className={`
        inline-flex items-center justify-center gap-2
        rounded-full min-h-[48px] px-6 text-sm
        transition-colors duration-200
        disabled:opacity-50 disabled:cursor-not-allowed
        ${VARIANTS[variant]} ${className}
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
