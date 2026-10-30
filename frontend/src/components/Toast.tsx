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

export function ToastProvider({ children }: { children: React.ReactNode }) {
  const [toasts, setToasts] = useState<ToastItem[]>([])

  const addToast = useCallback((message: string, type: ToastItem['type'] = 'info') => {
    const id = Date.now() + Math.random()
    setToasts((t) => [...t, { id, message, type }])
    setTimeout(() => setToasts((t) => t.filter((x) => x.id !== id)), 4500)
  }, [])

  return (
    <ToastContext.Provider value={{ addToast }}>
      {children}
      <div className="fixed bottom-6 right-6 z-50 flex flex-col gap-2 w-80 max-w-[calc(100vw-3rem)]">
        <AnimatePresence>
          {toasts.map((t) => (
            <motion.div
              key={t.id}
              initial={{ opacity: 0, x: 60, scale: 0.95 }}
              animate={{ opacity: 1, x: 0, scale: 1 }}
              exit={{ opacity: 0, x: 60, scale: 0.95 }}
              className="bg-white rounded-2xl shadow-card border border-line p-4 flex items-start gap-3"
            >
              {t.type === 'success' && <CheckCircle size={18} className="text-success mt-0.5 shrink-0" />}
              {t.type === 'info' && <Info size={18} className="text-pp-blue mt-0.5 shrink-0" />}
              {t.type === 'warning' && <AlertTriangle size={18} className="text-warning mt-0.5 shrink-0" />}
              <p className="text-sm text-ink flex-1 leading-snug">{t.message}</p>
              <button
                onClick={() => setToasts((t2) => t2.filter((x) => x.id !== t.id))}
                className="text-ink-soft hover:text-ink transition-colors"
                aria-label="Dismiss toast"
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
