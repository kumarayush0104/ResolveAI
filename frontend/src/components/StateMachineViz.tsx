import React, { useState } from 'react'
import { motion, useReducedMotion } from 'framer-motion'
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

const MAIN_PATH     = ['CREATED', 'PENDING', 'COMPLETED', 'REFUND_PENDING', 'REFUNDED']
const RECOVERY_PATH = ['UNKNOWN', 'DENIED', 'RETRY_ALLOWED']

/**
 * Soft traveling beam on the outgoing edge from the current node.
 */
function AnimatedEdge({ active, color }: { active: boolean; color: string }) {
  const reduceMotion = useReducedMotion() ?? false
  return (
    <span className="relative mx-1 flex shrink-0 items-center">
      <ChevronRight
        size={13}
        className="shrink-0 transition-colors duration-300"
        style={{ color: active ? color : '#C4D2E0' }}
      />
      {active && !reduceMotion && (
        <motion.span
          aria-hidden
          className="pointer-events-none absolute top-1/2 h-1 w-1 -translate-y-1/2 rounded-full"
          style={{ background: color, left: 0 }}
          animate={{ x: ['0px', '12px'], opacity: [0, 1, 0] }}
          transition={{ duration: 0.85, repeat: Infinity, ease: 'easeInOut', repeatDelay: 0.15 }}
        />
      )}
    </span>
  )
}

/** State node chip with status-colored ambient glow when active */
function Chip({ id, current, isNext }: { id: string; current: boolean; isNext?: boolean }) {
  const s = STATES[id]
  const reduceMotion = useReducedMotion() ?? false

  return (
    <span className="relative inline-flex shrink-0">
      {/* Primary pulse ring — status-colored ambient */}
      {current && (
        <motion.span
          aria-hidden
          className="absolute rounded-full"
          style={{
            inset: '-5px',
            background: `${s.color}18`,
            border: `1.5px solid ${s.color}`,
          }}
          animate={reduceMotion ? {} : {
            opacity: [0.7, 0.2, 0.7],
            scale:   [0.95, 1.06, 0.95],
          }}
          transition={{ duration: 2.2, repeat: Infinity, ease: 'easeInOut' }}
        />
      )}
      <span
        className="relative z-[1] whitespace-nowrap rounded-full px-3 py-1.5 text-[12px] font-bold transition-all duration-200"
        style={
          current
            ? {
                background: s.color,
                color: '#fff',
                boxShadow: `0 0 0 3px ${s.color}28, 0 2px 8px ${s.color}40`,
              }
            : {
                background: isNext ? `${s.color}0D` : '#fff',
                color: '#1E2A3B',
                boxShadow: `inset 0 0 0 1.5px ${isNext ? s.color + '60' : '#D5E1EC'}`,
              }
        }
        aria-current={current ? 'step' : undefined}
      >
        {s.label}
      </span>
    </span>
  )
}

function Row({ ids, current }: { ids: string[]; current: string }) {
  const currentIdx = ids.indexOf(current)
  return (
    <div className="flex flex-wrap items-center gap-y-2">
      {ids.map((id, i) => (
        <React.Fragment key={id}>
          <Chip id={id} current={current === id} isNext={i === currentIdx + 1} />
          {i < ids.length - 1 && (
            <AnimatedEdge
              active={i === currentIdx}
              color={STATES[id]?.color ?? '#9FB0C6'}
            />
          )}
        </React.Fragment>
      ))}
    </div>
  )
}

/**
 * Locked status notice item with precise top-aligned lock icon container.
 * - Uses flex items-start gap-2.5
 * - Icon container has shrink-0 and mt-0.5 for crisp alignment with the first text line
 * - Accompanying text block is min-w-0 flex-1 leading-snug to prevent misalignment on wrap
 */
function LockRule({ label, rule, why }: { label: string; rule: string; why: string }) {
  const [open, setOpen] = useState(false)
  return (
    <li
      className="relative flex items-start gap-2.5 text-[12px]"
      onMouseEnter={() => setOpen(true)}
      onMouseLeave={() => setOpen(false)}
      onFocus={() => setOpen(true)}
      onBlur={() => setOpen(false)}
    >
      <span className="mt-0.5 flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-[#FDEBE6] text-danger">
        <Lock size={11} className="shrink-0" />
      </span>
      <span className="min-w-0 flex-1 leading-snug text-muted">
        <strong className="text-ink">{label} is locked.</strong>{' '}
        <button
          className="inline font-mono text-[11px] font-semibold text-danger underline-offset-2 hover:underline focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-danger"
          aria-label={`Policy rule ${rule}: ${why}`}
          onClick={() => setOpen((o) => !o)}
        >
          {rule}
        </button>
        {' '}— {why}
      </span>
      {open && (
        <span
          role="tooltip"
          className="pointer-events-none absolute -top-9 left-6 z-20 max-w-[220px] rounded-lg bg-[#1E2A3B] px-2.5 py-1.5 text-[11px] font-semibold leading-snug text-white shadow-lg"
        >
          <span className="font-mono text-danger">{rule}</span>: {why}
        </span>
      )}
    </li>
  )
}

export function StateMachineViz({ currentState, blockedRules = [] }: StateMachineVizProps) {
  const cur = currentState?.toUpperCase() || 'UNKNOWN'

  const locks: { label: string; rule: string; why: string }[] = []
  if (cur === 'COMPLETED' || cur === 'PENDING' || cur === 'UNKNOWN') {
    locks.push({
      label: 'Retry payment',
      rule:  cur === 'COMPLETED' ? 'R01' : cur === 'PENDING' ? 'R02' : 'R03',
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
          {locks.map((l) => <LockRule key={l.label} {...l} />)}
        </ul>
      )}
    </div>
  )
}
