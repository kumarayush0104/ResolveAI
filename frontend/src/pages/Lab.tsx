import React, { useState } from 'react'
import { motion } from 'framer-motion'
import { FlaskConical, X, Zap } from 'lucide-react'
import { api } from '../lib/api'
import { useToast } from '../components/Toast'

// 8 lab actions
const LAB_ACTIONS = [
  {
    id: 'lose-success-response',
    label: 'Lose Success Response',
    desc: 'Real capture → UNKNOWN, reconciler recovers via GET',
    danger: false,
  },
  {
    id: 'inject-failure',
    label: 'Inject Definitive Failure',
    desc: 'Simulated DENIED snapshot, policy gates retry',
    danger: true,
  },
  {
    id: 'inject-pending',
    label: 'Inject Pending',
    desc: 'Simulated PAYMENT.CAPTURE.PENDING event',
    danger: false,
  },
  {
    id: 'delayed-event',
    label: 'Deliver Delayed Event',
    desc: 'COMPLETED arrives after delay via SSE broadcast',
    danger: false,
  },
  {
    id: 'duplicate-webhook',
    label: 'Duplicate Webhook',
    desc: 'Same event twice → deduplicated, no duplicate side-effects',
    danger: false,
  },
  {
    id: 'out-of-order',
    label: 'Out-of-Order Event',
    desc: 'Older event after new → engine does not regress state',
    danger: false,
  },
  {
    id: 'prompt-injection',
    label: 'Prompt Injection',
    desc: '"Ignore previous rules" in context note → policy blocks',
    danger: true,
  },
  {
    id: 'concurrent-retry',
    label: 'Concurrent Retry',
    desc: 'Two simultaneous retries → exactly one wins (409 on second)',
    danger: false,
  },
]

export function LabDrawer({
  orderId,
  caseId,
  onClose,
}: {
  orderId: string
  caseId: string
  onClose: () => void
}) {
  const { addToast } = useToast()
  const [running, setRunning] = useState<string | null>(null)

  const run = async (actionId: string) => {
    setRunning(actionId)
    try {
      await api.labAction(actionId, { order_id: orderId, case_id: caseId })
      addToast(`Simulation action '${actionId}' executed.`, 'success')
    } catch (e: any) {
      addToast(`Lab error: ${e.message}`, 'info')
    } finally {
      setRunning(null)
    }
  }

  return (
    <motion.div
      initial={{ x: '100%' }}
      animate={{ x: 0 }}
      exit={{ x: '100%' }}
      transition={{ type: 'spring', damping: 25, stiffness: 200 }}
      className="fixed right-0 top-0 h-full w-96 max-w-[90vw] bg-[#1a1a2e] text-white shadow-2xl z-50 flex flex-col"
    >
      <div className="sim-stripe p-4 flex items-center justify-between border-b border-pp-gold/30">
        <div className="flex items-center gap-2">
          <FlaskConical size={20} className="text-pp-gold shrink-0" />
          <span className="font-bold text-sm text-[#2C2E2F] uppercase tracking-wide">
            SIMULATION — Fault Lab
          </span>
        </div>
        <button
          onClick={onClose}
          className="text-[#2C2E2F] hover:opacity-70 p-1 transition-opacity"
          aria-label="Close lab drawer"
        >
          <X size={20} />
        </button>
      </div>

      <div className="p-4 border-b border-white/10 text-xs text-gray-300">
        Simulate edge cases against active Order <strong className="text-pp-gold font-mono">{orderId.slice(0, 12)}</strong>.
        All events pass through the policy engine flagged <code className="text-pp-gold">is_simulated=true</code>.
      </div>

      <div className="flex-1 overflow-y-auto p-4 space-y-3">
        {LAB_ACTIONS.map((action) => (
          <motion.button
            key={action.id}
            whileTap={{ x: [0, -4, 4, -4, 4, 0], transition: { duration: 0.3 } }}
            onClick={() => run(action.id)}
            disabled={!!running}
            className={`w-full text-left p-4 rounded-xl border transition-all ${
              action.danger
                ? 'border-danger/40 bg-danger/10 hover:bg-danger/20'
                : 'border-pp-gold/20 bg-white/5 hover:bg-white/10'
            } disabled:opacity-50`}
          >
            <div className="flex items-center gap-2">
              <Zap
                size={14}
                className={action.danger ? 'text-danger' : 'text-pp-gold'}
              />
              <span className="font-semibold text-sm">{action.label}</span>
              {running === action.id && (
                <span className="ml-auto w-3 h-3 border border-white border-t-transparent rounded-full animate-spin" />
              )}
            </div>
            <p className="text-xs text-gray-400 mt-1 leading-relaxed">
              {action.desc}
            </p>
          </motion.button>
        ))}
      </div>

      <div className="p-4 border-t border-white/10 text-center text-[11px] text-gray-400">
        Controlled sandbox fault injection · Never touches live money
      </div>
    </motion.div>
  )
}
