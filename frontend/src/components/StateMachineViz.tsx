import React from 'react'
import { motion } from 'framer-motion'
import { Lock, ChevronRight, CornerDownRight } from 'lucide-react'

export interface StateMachineVizProps {
  currentState: string
  lastTransition?: { from: string; to: string }
  blockedRules?: Array<{ action: string; rule_id: string; reason?: string }>
}

const STATES: Record<string, { label: string; color: string }> = {
  CREATED:        { label: 'Created',        color: '#5B6B8C' },
  PENDING:        { label: 'Pending',        color: '#B26A00' },
  UNKNOWN:        { label: 'Unknown',        color: '#5B6B8C' },
  COMPLETED:      { label: 'Completed',      color: '#1F8A4C' },
  DENIED:         { label: 'Denied',         color: '#D9360B' },
  RETRY_ALLOWED:  { label: 'Retry allowed',  color: '#B26A00' },
  REFUND_PENDING: { label: 'Refund pending', color: '#B26A00' },
  REFUNDED:       { label: 'Refunded',       color: '#1F8A4C' },
}

const MAIN_PATH = ['CREATED', 'PENDING', 'COMPLETED', 'REFUND_PENDING', 'REFUNDED']
const RECOVERY_PATH = ['UNKNOWN', 'DENIED', 'RETRY_ALLOWED']

function Chip({ id, current }: { id: string; current: boolean }) {
  const s = STATES[id]
  return (
    <span className="relative inline-flex">
      {current && (
        <motion.span
          aria-hidden
          className="absolute -inset-1 rounded-full"
          style={{ border: `2px solid ${s.color}` }}
          animate={{ opacity: [0.7, 0.15, 0.7], scale: [0.98, 1.06, 0.98] }}
          transition={{ duration: 2, repeat: Infinity, ease: 'easeInOut' }}
        />
      )}
      <span
        className="relative whitespace-nowrap rounded-full px-3 py-1.5 text-[12px] font-bold"
        style={
          current
            ? { background: s.color, color: '#fff' }
            : { background: '#fff', color: '#1E2A3B', boxShadow: 'inset 0 0 0 1.5px #D5E1EC' }
        }
        aria-current={current ? 'step' : undefined}
      >
        {s.label}
      </span>
    </span>
  )
}

function Row({ ids, current }: { ids: string[]; current: string }) {
  return (
    <div className="flex flex-wrap items-center gap-y-2">
      {ids.map((id, i) => (
        <React.Fragment key={id}>
          <Chip id={id} current={current === id} />
          {i < ids.length - 1 && <ChevronRight size={14} className="mx-0.5 shrink-0 text-[#9FB0C6]" />}
        </React.Fragment>
      ))}
    </div>
  )
}

export function StateMachineViz({ currentState, blockedRules = [] }: StateMachineVizProps) {
  const cur = currentState?.toUpperCase() || 'UNKNOWN'

  // Transitions that are locked right now, with the rule that locks them
  const locks: { label: string; rule: string; why: string }[] = []
  if (cur === 'COMPLETED' || cur === 'PENDING' || cur === 'UNKNOWN') {
    locks.push({
      label: 'Retry payment',
      rule: cur === 'COMPLETED' ? 'R01' : cur === 'PENDING' ? 'R02' : 'R03',
      why:
        cur === 'COMPLETED'
          ? 'The payment already completed.'
          : cur === 'PENDING'
          ? 'An attempt is already pending.'
          : 'The outcome is unknown, so we fail closed.',
    })
  }
  if (cur !== 'COMPLETED') {
    locks.push({ label: 'Refund', rule: 'R05', why: 'Only completed payments can be refunded.' })
  }

  return (
    <div className="space-y-3">
      <div>
        <p className="mb-1.5 text-[11.5px] font-bold text-muted">Normal path</p>
        <Row ids={MAIN_PATH} current={cur} />
      </div>
      <div>
        <p className="mb-1.5 flex items-center gap-1 text-[11.5px] font-bold text-muted">
          <CornerDownRight size={12} /> If something goes wrong
        </p>
        <Row ids={RECOVERY_PATH} current={cur} />
      </div>

      {locks.length > 0 && (
        <ul className="space-y-1.5 border-t border-line pt-3">
          {locks.map((l) => (
            <li key={l.label} className="flex items-start gap-2 text-[12px]">
              <span className="mt-0.5 flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-[#FDEBE6] text-danger">
                <Lock size={11} />
              </span>
              <span className="leading-snug text-muted">
                <strong className="text-ink">{l.label} is locked.</strong> {l.why}{' '}
                <span className="font-mono text-[11px] text-danger">{l.rule}</span>
              </span>
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}
