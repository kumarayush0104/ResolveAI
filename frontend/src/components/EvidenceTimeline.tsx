import React, { useEffect, useState } from 'react'
import { motion } from 'framer-motion'
import { Server, Bell, MessageSquare, Brain, Shield, RefreshCw, CheckCircle, HelpCircle } from 'lucide-react'

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

const SOURCE_ICONS: Record<string, React.ReactNode> = {
  API:        <Server size={14} className="text-pp-blue" />,
  WEBHOOK:    <Bell size={14} className="text-purple-600" />,
  USER:       <MessageSquare size={14} className="text-teal-600" />,
  AI:         <Brain size={14} className="text-pink-600" />,
  POLICY:     <Shield size={14} className="text-pp-blue-dark" />,
  RECONCILER: <RefreshCw size={14} className="text-warning" />,
}

export function EvidenceTimeline({ events, highlightedRef }: EvidenceTimelineProps) {
  const [lineDrawn, setLineDrawn] = useState(false)

  useEffect(() => {
    const t = setTimeout(() => setLineDrawn(true), 300)
    return () => clearTimeout(t)
  }, [])

  if (!events || events.length === 0) {
    return (
      <div className="py-8 text-center text-ink-soft text-sm">
        <HelpCircle size={24} className="mx-auto mb-2 opacity-40" />
        No evidence events recorded yet.
      </div>
    )
  }

  return (
    <div className="relative pl-6 py-2">
      {/* Self-drawing vertical line on mount */}
      <svg
        className="absolute left-[11px] top-4 bottom-4 w-1 h-full pointer-events-none"
        style={{ overflow: 'visible' }}
      >
        <motion.line
          x1="0"
          y1="0"
          x2="0"
          y2="100%"
          stroke="#EAEDEF"
          strokeWidth="2"
          initial={{ pathLength: 0 }}
          animate={{ pathLength: 1 }}
          transition={{ duration: 1.2, ease: 'easeInOut' }}
        />
      </svg>

      <div className="space-y-4">
        {events.map((ev, idx) => {
          const isHighlighted = highlightedRef && (ev.ref === highlightedRef || ev.event_type.toLowerCase().includes(highlightedRef.toLowerCase()))
          const icon = SOURCE_ICONS[ev.source?.toUpperCase()] || <Server size={14} className="text-ink-soft" />

          return (
            <motion.div
              key={ev.id || idx}
              initial={{ opacity: 0, x: -20 }}
              animate={{ opacity: 1, x: 0 }}
              transition={{ type: 'spring', damping: 20, delay: idx * 0.05 }}
              className={`relative rounded-xl border p-3.5 transition-all duration-300 ${
                isHighlighted
                  ? 'border-pp-blue ring-2 ring-pp-blue/20 bg-blue-50/50 shadow-md'
                  : 'border-line bg-white hover:border-gray-300 shadow-sm'
              }`}
            >
              {/* Node dot on the vertical line */}
              <div className="absolute -left-[29px] top-4 w-6 h-6 rounded-full bg-white border-2 border-line flex items-center justify-center shadow-sm">
                {icon}
              </div>

              {/* Event Header */}
              <div className="flex flex-wrap items-center justify-between gap-2 mb-1.5">
                <div className="flex items-center gap-2">
                  <span className="text-xs font-mono font-semibold text-pp-blue-dark">
                    {ev.event_type}
                  </span>
                  <span className="inline-flex items-center gap-0.5 text-[10px] font-semibold text-success bg-[#E6F4EC] px-1.5 py-0.5 rounded">
                    <CheckCircle size={10} />
                    Verified
                  </span>
                </div>

                <div className="flex items-center gap-2">
                  {ev.is_simulated ? (
                    <span className="sim-stripe border border-pp-gold text-ink text-[10px] font-bold px-2 py-0.5 rounded-full uppercase tracking-wider">
                      SIMULATION
                    </span>
                  ) : (
                    <span className="bg-[#E6F4EC] text-success border border-success/30 text-[10px] font-bold px-2 py-0.5 rounded-full uppercase tracking-wider">
                      LIVE SANDBOX
                    </span>
                  )}
                  <span className="text-[11px] font-mono text-ink-soft">
                    {new Date(ev.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' })}
                  </span>
                </div>
              </div>

              {/* Event Description */}
              <p className="text-xs text-ink whitespace-pre-wrap break-words leading-relaxed">
                {ev.description}
              </p>
            </motion.div>
          )
        })}
      </div>
    </div>
  )
}
