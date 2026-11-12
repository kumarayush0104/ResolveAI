import React, { useState } from 'react'
import { motion, AnimatePresence, useReducedMotion } from 'framer-motion'
import { FlaskConical, Play, Sparkles, Loader2, CheckCircle2 } from 'lucide-react'
import { Sheet } from '../components/Sheet'
import { api } from '../lib/api'
import { useToast } from '../components/Toast'

// One-click end-to-end demo scenarios
const DEMO_SCENARIOS = [
  {
    id: 'run-scenario-1',
    label: 'Lost payment response',
    desc: 'Simulates a missing payment result, then resolves it with a simulated status check. No PayPal capture is started.',
  },
  {
    id: 'run-scenario-2',
    label: 'Payment declined; safe retry',
    desc: 'Shows a declined payment. Policy allows a retry only after merchant approval.',
  },
  {
    id: 'run-scenario-3',
    label: 'Delayed payment update',
    desc: 'Shows Pending first, then sends a simulated Completed update after five seconds.',
  },
]

// Individual fault injections
const LAB_ACTIONS: { id: string; label: string; desc: string; danger: boolean }[] = [
  { id: 'lose-success-response', label: 'Drop success response',    desc: 'Marks the result Unknown, then runs a simulated status check. No payment is made.', danger: false },
  { id: 'inject-failure',        label: 'Simulate payment failure',  desc: 'Shows a declined payment. A retry needs merchant approval.',                      danger: true  },
  { id: 'inject-pending',        label: 'Simulate pending payment',  desc: 'Shows a payment waiting for confirmation.',                                       danger: false },
  { id: 'delayed-event',         label: 'Send delayed update',       desc: 'Shows Pending, then sends a simulated Completed update after a short delay.',       danger: false },
  { id: 'duplicate-webhook',     label: 'Duplicate webhook',        desc: 'Sends the same event twice; the second copy is ignored.',                          danger: false },
  { id: 'out-of-order',          label: 'Out-of-order update',       desc: 'Sends an older Pending event after Completed; the case stays Completed.',          danger: false },
  { id: 'prompt-injection',      label: 'Prompt injection',         desc: 'Tests an unsafe refund instruction; policy blocks it.',                            danger: true  },
  { id: 'concurrent-retry',      label: 'Concurrent retry',         desc: 'Simulates two retries at once; one proceeds and the other gets a 409 conflict.',     danger: false },
]

/** Soft ripple ring on button trigger — professional feedback, no shockwave */
function RippleFeedback({ visible }: { visible: boolean }) {
  const reduceMotion = useReducedMotion() ?? false
  if (reduceMotion || !visible) return null
  return (
    <motion.span
      aria-hidden
      className="pointer-events-none absolute inset-0 rounded-2xl"
      initial={{ opacity: 0.4, scale: 0.96 }}
      animate={{ opacity: 0, scale: 1.04 }}
      transition={{ duration: 0.5, ease: 'easeOut' }}
      style={{ border: '2px solid rgba(255,196,57,0.6)' }}
    />
  )
}

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
  const [lastRun, setLastRun] = useState<string | null>(null)

  const run = async (actionId: string) => {
    if (running) return
    setRunning(actionId)
    setLastRun(null)
    try {
      await api.labAction(actionId, { order_id: orderId, case_id: caseId })
      setLastRun(actionId)
      addToast('Simulation triggered — watch the timeline update.', 'success')
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
      {/* Simulation context banner — SIMULATION stripe, clear scope */}
      <div className="sim-stripe -mx-1 mb-5 rounded-2xl border border-pp-gold/35 px-4 py-3">
        <p className="text-[12px] font-semibold leading-relaxed text-white/85">
          Simulated events for order{' '}
          <span className="font-mono text-pp-gold">{orderId.slice(0, 12)}…</span>
        </p>
        <p className="mt-0.5 text-[11.5px] text-white/55">
          Every action is a simulation and runs through the real policy rules. It never contacts PayPal or moves money.
        </p>
      </div>

      {/* Demo scenarios — gold tinted, prominent */}
      <div className="mb-1.5 flex items-center gap-1.5 text-[12px] font-extrabold uppercase tracking-wide text-pp-gold">
        <Sparkles size={13} /> End-to-end scenarios
      </div>
      <div className="space-y-2 mb-5">
        {DEMO_SCENARIOS.map((sc) => {
          const isRunning = running === sc.id
          const isDone    = lastRun === sc.id && !running
          return (
            <motion.button
              key={sc.id}
              whileTap={{ scale: 0.98 }}
              onClick={() => run(sc.id)}
              disabled={!!running}
              className="relative w-full overflow-hidden rounded-2xl border border-pp-gold/35 bg-pp-gold/8 p-3.5 text-left disabled:opacity-50 transition-colors hover:bg-pp-gold/14 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-pp-gold"
            >
              <RippleFeedback visible={isDone} />
              <div className="flex items-center gap-2">
                {isRunning ? (
                  <Loader2 size={13} className="animate-spin text-pp-gold" />
                ) : isDone ? (
                  <CheckCircle2 size={13} className="text-pp-gold" />
                ) : (
                  <Play size={13} className="fill-pp-gold text-pp-gold" />
                )}
                <span className="text-[13px] font-bold text-white">{sc.label}</span>
              </div>
              <p className="mt-1 text-[12px] leading-snug text-white/60">{sc.desc}</p>
            </motion.button>
          )
        })}
      </div>

      {/* Individual fault injections */}
      <div className="mb-1.5 text-[12px] font-extrabold uppercase tracking-wide text-white/50">
        Single fault injections
      </div>
      <div className="space-y-2">
        {LAB_ACTIONS.map((action) => {
          const isRunning = running === action.id
          const isDone    = lastRun === action.id && !running
          return (
            <motion.button
              key={action.id}
              whileTap={{ scale: 0.98 }}
              onClick={() => run(action.id)}
              disabled={!!running}
              className={`relative w-full overflow-hidden rounded-2xl border p-3.5 text-left disabled:opacity-50 transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-pp-gold ${
                action.danger
                  ? 'border-danger/40 bg-danger/10 hover:bg-danger/16'
                  : 'border-white/10 bg-white/5 hover:bg-white/8'
              }`}
            >
              <RippleFeedback visible={isDone} />
              <div className="flex items-center gap-2">
                {isRunning ? (
                  <Loader2 size={13} className="animate-spin text-white/60" />
                ) : isDone ? (
                  <CheckCircle2 size={13} className="text-pp-gold" />
                ) : (
                  /* Armed indicator dot */
                  <span
                    className={`h-2 w-2 shrink-0 rounded-full ${
                      action.danger ? 'bg-danger' : 'bg-pp-gold/70'
                    }`}
                    aria-hidden
                  />
                )}
                <span className="text-[13px] font-bold text-white">{action.label}</span>
                {action.danger && (
                  <span className="ml-auto rounded-full bg-danger/25 px-2 py-0.5 text-[10px] font-bold uppercase tracking-wide text-danger">
                    danger
                  </span>
                )}
              </div>
              <p className="mt-1 text-[12px] leading-snug text-white/55">{action.desc}</p>
            </motion.button>
          )
        })}
      </div>
    </Sheet>
  )
}
