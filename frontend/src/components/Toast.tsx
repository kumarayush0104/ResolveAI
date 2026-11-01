import React, { createContext, useContext, useState, useCallback } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { CheckCircle, Info, AlertTriangle, X } from 'lucide-react'

export interface ToastItem {
  id: number
  message: string
  type: 'info' | 'success' | 'warning'
}

interface ToastCtx {
  addToast: (msg: string, type?: ToastItem['type']) => void
}

const ToastContext = createContext<ToastCtx>({ addToast: () => {} })
export const useToast = () => useContext(ToastContext)

/** Toasts drop in from the top of the phone screen. Must sit inside a `relative` container. */
export function ToastProvider({ children }: { children: React.ReactNode }) {
  const [toasts, setToasts] = useState<ToastItem[]>([])

  const addToast = useCallback((message: string, type: ToastItem['type'] = 'info') => {
    const id = Date.now() + Math.random()
    setToasts((t) => [...t.slice(-2), { id, message, type }])
    setTimeout(() => setToasts((t) => t.filter((x) => x.id !== id)), 4500)
  }, [])

  return (
    <ToastContext.Provider value={{ addToast }}>
      {children}
      <div
        className="pointer-events-none absolute inset-x-3 top-[96px] z-50 flex flex-col gap-2 max-sm:top-[72px]"
        aria-live="polite"
      >
        <AnimatePresence>
          {toasts.map((t) => (
            <motion.div
              key={t.id}
              initial={{ opacity: 0, y: -16, scale: 0.97 }}
              animate={{ opacity: 1, y: 0, scale: 1 }}
              exit={{ opacity: 0, y: -16, scale: 0.97 }}
              className="pointer-events-auto flex items-start gap-3 rounded-2xl border border-line bg-white p-3.5 shadow-card"
            >
              {t.type === 'success' && <CheckCircle size={18} className="mt-0.5 shrink-0 text-success" />}
              {t.type === 'info' && <Info size={18} className="mt-0.5 shrink-0 text-cyan-deep" />}
              {t.type === 'warning' && <AlertTriangle size={18} className="mt-0.5 shrink-0 text-warning" />}
              <p className="flex-1 text-[13px] font-medium leading-snug text-ink">{t.message}</p>
              <button
                onClick={() => setToasts((t2) => t2.filter((x) => x.id !== t.id))}
                className="text-muted"
                aria-label="Dismiss"
              >
                <X size={14} />
              </button>
            </motion.div>
          ))}
        </AnimatePresence>
      </div>
    </ToastContext.Provider>
  )
}
