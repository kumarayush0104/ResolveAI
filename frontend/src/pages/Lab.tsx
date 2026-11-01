import React, { useEffect, useState } from 'react'
import { motion } from 'framer-motion'
import { FlaskConical, Zap, Play, Sparkles } from 'lucide-react'
import { Sheet } from '../components/Sheet'
import { api } from '../lib/api'
import { useToast } from '../components/Toast'

// One-click demo scenarios
const DEMO_SCENARIOS = [
  { id: 'run-scenario-1', label: 'Scenario 1: Lost success response', desc: 'Unknown → reconciler → Completed, live over SSE' },
  { id: 'run-scenario-2', label: 'Scenario 2: Definitive failure and safe retry', desc: 'Denied → AI diagnoses → rule R04 gates the retry' },
  { id: 'run-scenario-3', label: 'Scenario 3: Delayed reconciliation', desc: 'Pending → delayed Completed webhook → live SSE toast' },
]

// Individual fault injections
const LAB_ACTIONS = [
  { id: 'lose-success-response', label: 'Lose success response',    desc: 'Real capture → Unknown; the reconciler recovers it via GET', danger: false },
  { id: 'inject-failure',        label: 'Inject definitive failure', desc: 'Simulated Denied snapshot; policy gates the retry',          danger: true  },
  { id: 'inject-pending',        label: 'Inject pending',            desc: 'Simulated PAYMENT.CAPTURE.PENDING event',                    danger: false },
  { id: 'delayed-event',         label: 'Deliver delayed event',     desc: 'Completed arrives after a delay via SSE broadcast',          danger: false },
  { id: 'duplicate-webhook',     label: 'Duplicate webhook',         desc: 'Same event twice → deduplicated, no duplicate side effects',  danger: false },
  { id: 'out-of-order',          label: 'Out-of-order event',        desc: 'An older event after a newer one → state does not regress',   danger: false },
  { id: 'prompt-injection',      label: 'Prompt injection',          desc: '“Ignore previous rules” in a note → the policy blocks it',   danger: true  },
  { id: 'concurrent-retry',      label: 'Concurrent retry',          desc: 'Two simultaneous retries → exactly one wins (409 on second)', danger: false },
]

/** Bottom sheet. Render inside <Overlay><AnimatePresence>…</AnimatePresence></Overlay>. */
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
      addToast(`Ran “${actionId}” in the simulator.`, 'success')
    } catch (e: any) {
      addToast(`Lab error: ${e.message}`, 'info')
    } finally {
      setRunning(null)
    }
  }

  return (
    <Sheet
      tall
      tone="dark"
      onClose={onClose}
      title={
        <span className="flex items-center gap-2">
          <FlaskConical size={18} className="text-pp-gold" />
          Fault lab
        </span>
      }
    >
      <p className="sim-stripe -mx-1 mb-4 rounded-2xl border border-pp-gold/40 p-3 text-[12px] leading-relaxed text-white/90">
        Simulated events for order <strong className="font-mono text-pp-gold">{orderId.slice(0, 12)}</strong>. Every one
        is flagged as a simulation and goes through the policy engine. No real money moves.
      </p>

      <div className="mb-2 flex items-center gap-1.5 text-[13px] font-extrabold text-pp-gold">
        <Sparkles size={14} /> Demo scenarios
      </div>
      <div className="space-y-2">
        {DEMO_SCENARIOS.map((sc) => (
          <motion.button
            key={sc.id}
            whileTap={{ scale: 0.98 }}
            onClick={() => run(sc.id)}
            disabled={!!running}
            className="w-full rounded-2xl border border-pp-gold/40 bg-pp-gold/10 p-3.5 text-left disabled:opacity-50"
          >
            <div className="flex items-center gap-2">
              <Play size={13} className="fill-pp-gold text-pp-gold" />
              <span className="text-[13px] font-bold">{sc.label}</span>
              {running === sc.id && (
                <span className="ml-auto h-3.5 w-3.5 animate-spin rounded-full border-2 border-pp-gold border-t-transparent" />
              )}
            </div>
            <p className="mt-1 text-[12px] leading-snug text-white/65">{sc.desc}</p>
          </motion.button>
        ))}
      </div>

      <div className="mb-2 mt-6 text-[13px] font-extrabold text-white/70">Single fault injections</div>
      <div className="space-y-2">
        {LAB_ACTIONS.map((action) => (
          <motion.button
            key={action.id}
            whileTap={{ scale: 0.98 }}
            onClick={() => run(action.id)}
            disabled={!!running}
            className={`w-full rounded-2xl border p-3.5 text-left disabled:opacity-50 ${
              action.danger ? 'border-danger/50 bg-danger/10' : 'border-white/10 bg-white/5'
            }`}
          >
            <div className="flex items-center gap-2">
              <Zap size={14} className={action.danger ? 'text-[#FF8A66]' : 'text-pp-gold'} />
              <span className="text-[13px] font-bold">{action.label}</span>
              {running === action.id && (
                <span className="ml-auto h-3.5 w-3.5 animate-spin rounded-full border-2 border-white border-t-transparent" />
              )}
            </div>
            <p className="mt-1 text-[12px] leading-snug text-white/60">{action.desc}</p>
          </motion.button>
        ))}
      </div>
    </Sheet>
  )
}
