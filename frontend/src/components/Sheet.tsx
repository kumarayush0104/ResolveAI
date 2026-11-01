import React from 'react'
import { motion } from 'framer-motion'
import { X } from 'lucide-react'
import { Overlay } from './Overlay'

/** Bottom sheet that slides up inside the phone. */
export function Sheet({
  title,
  onClose,
  children,
  tone = 'light',
  tall,
}: {
  title: React.ReactNode
  onClose: () => void
  children: React.ReactNode
  tone?: 'light' | 'dark'
  tall?: boolean
}) {
  const dark = tone === 'dark'
  return (
    <Overlay>
      <motion.div
        className="pointer-events-auto absolute inset-0 bg-navy-deep/50"
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        exit={{ opacity: 0 }}
        onClick={onClose}
      />
      <motion.div
        role="dialog"
        aria-modal="true"
        className={`pointer-events-auto absolute inset-x-0 bottom-0 flex flex-col overflow-hidden rounded-t-[28px] shadow-2xl ${
          tall ? 'h-[86%]' : 'max-h-[86%]'
        } ${dark ? 'bg-navy-deep text-white' : 'bg-white text-ink'}`}
        initial={{ y: '100%' }}
        animate={{ y: 0 }}
        exit={{ y: '100%' }}
        transition={{ type: 'spring', damping: 30, stiffness: 320 }}
      >
        <div className="flex shrink-0 items-center justify-between px-5 pb-2 pt-4">
          <div className="text-[16px] font-extrabold tracking-tight">{title}</div>
          <button
            onClick={onClose}
            aria-label="Close"
            className={`flex h-9 w-9 items-center justify-center rounded-full ${
              dark ? 'bg-white/10 text-white' : 'bg-canvas text-muted'
            }`}
          >
            <X size={18} />
          </button>
        </div>
        <div className="phone-scroll min-h-0 flex-1 overflow-y-auto px-5 pb-6">{children}</div>
      </motion.div>
    </Overlay>
  )
}
