import React from 'react'
import { motion } from 'framer-motion'
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
}

const SOURCES: Record<string, { icon: React.ReactNode; tint: string }> = {
  API:        { icon: <Server size={15} />,        tint: 'bg-cyan-soft text-cyan-deep' },
  WEBHOOK:    { icon: <Bell size={15} />,          tint: 'bg-[#EEE9FB] text-[#6B4FD0]' },
  USER:       { icon: <MessageSquare size={15} />, tint: 'bg-[#E2F5F2] text-[#13846F]' },
  AI:         { icon: <Brain size={15} />,         tint: 'bg-[#FCE8F1] text-[#C0306E]' },
  POLICY:     { icon: <Shield size={15} />,        tint: 'bg-[#E6ECF8] text-navy' },
  RECONCILER: { icon: <RefreshCw size={15} />,     tint: 'bg-[#FFF4D6] text-warning' },
}
const FALLBACK = { icon: <Server size={15} />, tint: 'bg-canvas text-muted' }

export function EvidenceTimeline({ events, highlightedRef }: EvidenceTimelineProps) {
  if (!events || events.length === 0) {
    return (
      <div className="py-6 text-center text-[13px] text-muted">
        <HelpCircle size={24} className="mx-auto mb-2 opacity-40" />
        No evidence recorded yet. Run the AI investigation to start collecting it.
      </div>
    )
  }

  return (
    <ol className="relative space-y-3">
      <span aria-hidden className="absolute bottom-3 left-[17px] top-3 w-0.5 rounded bg-line" />
      {events.map((ev, idx) => {
        const hit =
          highlightedRef && (ev.ref === highlightedRef || ev.event_type.toLowerCase().includes(highlightedRef.toLowerCase()))
        const src = SOURCES[ev.source?.toUpperCase()] ?? FALLBACK
        return (
          <motion.li
            key={ev.id || idx}
            initial={{ opacity: 0, y: 6 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: Math.min(idx, 8) * 0.04 }}
            className="relative flex gap-3"
          >
            <span className={`relative z-[1] flex h-9 w-9 shrink-0 items-center justify-center rounded-full ring-4 ring-white ${src.tint}`}>
              {src.icon}
            </span>
            <div
              className={`min-w-0 flex-1 rounded-2xl p-3 transition-colors ${
                hit ? 'bg-cyan-soft ring-2 ring-cyan/40' : 'bg-mist'
              }`}
            >
              <div className="flex items-start justify-between gap-2">
                <span className="break-all font-mono text-[11.5px] font-semibold text-navy">{ev.event_type}</span>
                <span className="shrink-0 font-mono text-[10.5px] text-muted">
                  {new Date(ev.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' })}
                </span>
              </div>
              <p className="mt-1 whitespace-pre-wrap break-words text-[12.5px] leading-relaxed text-ink">{ev.description}</p>
              <div className="mt-2 flex flex-wrap items-center gap-1.5">
                {ev.is_simulated ? (
                  <span className="sim-stripe rounded-full border border-pp-gold px-2 py-0.5 text-[10.5px] font-bold text-ink">
                    Simulated
                  </span>
                ) : (
                  <span className="rounded-full bg-[#E4F5EB] px-2 py-0.5 text-[10.5px] font-bold text-success">Live sandbox</span>
                )}
                <span className="inline-flex items-center gap-1 text-[10.5px] font-bold text-success">
                  <BadgeCheck size={12} /> Verified
                </span>
              </div>
            </div>
          </motion.li>
        )
      })}
    </ol>
  )
}
