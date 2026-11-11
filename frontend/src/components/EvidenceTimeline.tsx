import React, { useRef } from 'react'
import { motion, useReducedMotion, useInView, AnimatePresence } from 'framer-motion'
import { Server, Bell, MessageSquare, Brain, Shield, RefreshCw, BadgeCheck, HelpCircle } from 'lucide-react'

export interface TimelineEvent {
  id: string
  source: string
  event_type: string
  description: string
  is_simulated?: boolean
  created_at: string
  ref?: string
}

interface EvidenceTimelineProps {
  events: TimelineEvent[]
  highlightedRef?: string | null
  onHoverRef?: (ref: string | null) => void
}

const SOURCES: Record<string, { icon: React.ReactNode; tint: string }> = {
  API:        { icon: <Server size={15} />,        tint: 'bg-cyan-soft text-cyan-deep'   },
  WEBHOOK:    { icon: <Bell size={15} />,          tint: 'bg-[#EEE9FB] text-[#6B4FD0]'  },
  USER:       { icon: <MessageSquare size={15} />, tint: 'bg-[#E2F5F2] text-[#13846F]'  },
  AI:         { icon: <Brain size={15} />,         tint: 'bg-[#FCE8F1] text-[#C0306E]'  },
  POLICY:     { icon: <Shield size={15} />,        tint: 'bg-[#E6ECF8] text-navy'        },
  RECONCILER: { icon: <RefreshCw size={15} />,     tint: 'bg-[#FFF4D6] text-warning'    },
}
const FALLBACK = { icon: <Server size={15} />, tint: 'bg-canvas text-muted' }

/** Self-drawing vertical connector — no layout shift (absolute positioned) */
function ConnectorLine({ count }: { count: number }) {
  const ref = useRef<HTMLSpanElement>(null)
  const inView = useInView(ref, { once: true })
  const reduceMotion = useReducedMotion() ?? false
  const dur = Math.min(count * 0.1 + 0.3, 1.1)

  return (
    <span
      ref={ref}
      aria-hidden
      className="absolute bottom-3 left-[17px] top-3 w-0.5 origin-top rounded bg-line"
      style={{
        transform: reduceMotion || !inView ? 'scaleY(1)' : 'scaleY(0)',
        transition: reduceMotion ? 'none' : `transform ${dur}s cubic-bezier(0.4,0,0.2,1) 0.1s`,
      }}
    />
  )
}

function TimelineItem({
  ev,
  idx,
  hit,
  onHoverRef,
}: {
  ev: TimelineEvent
  idx: number
  hit: boolean
  onHoverRef?: (ref: string | null) => void
}) {
  const reduceMotion = useReducedMotion() ?? false
  const src = SOURCES[ev.source?.toUpperCase()] ?? FALLBACK

  return (
    <motion.li
      layout
      initial={reduceMotion ? false : { opacity: 0, x: -10, y: 4 }}
      animate={{ opacity: 1, x: 0, y: 0 }}
      transition={{
        delay: Math.min(idx, 6) * 0.055,
        type: 'spring',
        stiffness: 300,
        damping: 28,
      }}
      className="relative flex gap-3"
    >
      {/* Source icon bubble */}
      <span className={`relative z-[1] flex h-9 w-9 shrink-0 items-center justify-center rounded-full ring-4 ring-white ${src.tint}`}>
        {src.icon}
      </span>

      {/* Content card */}
      <motion.div
        className={`min-w-0 flex-1 rounded-2xl p-3 transition-colors duration-200 ${
          hit ? 'bg-cyan-soft ring-2 ring-cyan/40' : 'bg-mist'
        }`}
        animate={hit && !reduceMotion ? { scale: [1, 1.012, 1] } : {}}
        transition={{ duration: 0.3 }}
      >
        <div className="flex items-start justify-between gap-2">
          <span className="break-all font-mono text-[11.5px] font-semibold text-navy">
            {ev.event_type}
          </span>
          <span className="shrink-0 font-mono text-[10.5px] text-muted">
            {new Date(ev.created_at).toLocaleTimeString([], {
              hour: '2-digit', minute: '2-digit', second: '2-digit',
            })}
          </span>
        </div>

        <p className="mt-1 whitespace-pre-wrap break-words text-[12.5px] leading-relaxed text-ink">
          {ev.description}
        </p>

        <div className="mt-2 flex flex-wrap items-center gap-1.5">
          {ev.is_simulated ? (
            /* SIMULATION — diagonal gold stripe, clearly synthetic */
            <span className="sim-stripe inline-flex items-center gap-1 rounded-full border border-pp-gold px-2.5 py-0.5 text-[10.5px] font-bold text-ink">
              🧪 Simulated
            </span>
          ) : (
            /* LIVE SANDBOX — solid green, with live dot */
            <span className="inline-flex items-center gap-1 rounded-full bg-[#E4F5EB] px-2.5 py-0.5 text-[10.5px] font-bold text-success ring-1 ring-success/15">
              <span className="h-1.5 w-1.5 rounded-full bg-success" aria-hidden />
              Live sandbox
            </span>
          )}

          <span className="inline-flex items-center gap-1 text-[10.5px] font-bold text-success">
            <BadgeCheck size={12} /> Verified
          </span>

          {/* Evidence cross-link chip */}
          {ev.ref && onHoverRef && (
            <button
              className="rounded-full bg-cyan-soft px-2 py-0.5 font-mono text-[10px] text-cyan-deep transition-colors hover:bg-cyan hover:text-white focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-cyan"
              onMouseEnter={() => onHoverRef(ev.ref!)}
              onMouseLeave={() => onHoverRef(null)}
              onFocus={() => onHoverRef(ev.ref!)}
              onBlur={() => onHoverRef(null)}
              aria-label={`Evidence reference ${ev.ref}`}
            >
              {ev.ref}
            </button>
          )}
        </div>
      </motion.div>
    </motion.li>
  )
}

export function EvidenceTimeline({ events, highlightedRef, onHoverRef }: EvidenceTimelineProps) {
  if (!events || events.length === 0) {
    return (
      <div className="flex flex-col items-center gap-3 py-8 text-center text-[13px] text-muted">
        <span className="flex h-12 w-12 items-center justify-center rounded-full bg-mist">
          <HelpCircle size={22} className="opacity-40" />
        </span>
        <div>
          <p className="font-semibold text-navy">No evidence yet</p>
          <p className="mt-0.5 text-[12px]">Run the AI investigation to start collecting it.</p>
        </div>
      </div>
    )
  }

  return (
    <ol className="relative space-y-3">
      <ConnectorLine count={events.length} />
      <AnimatePresence initial={false}>
        {events.map((ev, idx) => {
          const hit =
            !!highlightedRef &&
            (ev.ref === highlightedRef ||
              ev.event_type.toLowerCase().includes(highlightedRef.toLowerCase()))
          return (
            <TimelineItem key={ev.id || idx} ev={ev} idx={idx} hit={hit} onHoverRef={onHoverRef} />
          )
        })}
      </AnimatePresence>
    </ol>
  )
}
