import React from 'react'
import { motion } from 'framer-motion'
import { Lock } from 'lucide-react'

export interface StateMachineVizProps {
  currentState: string
  lastTransition?: { from: string; to: string }
  blockedRules?: Array<{ action: string; rule_id: string; reason?: string }>
}

interface NodeCoord {
  id: string
  label: string
  x: number
  y: number
  color: string
}

const NODES: NodeCoord[] = [
  { id: 'CREATED',        label: 'Created',        x: 70,  y: 70,  color: '#5B6B8C' },
  { id: 'PENDING',        label: 'Pending',        x: 230, y: 70,  color: '#B26A00' },
  { id: 'UNKNOWN',        label: 'Unknown',        x: 390, y: 170, color: '#5B6B8C' },
  { id: 'COMPLETED',      label: 'Completed',      x: 550, y: 70,  color: '#1F8A4C' },
  { id: 'DENIED',         label: 'Denied',         x: 390, y: 270, color: '#D9360B' },
  { id: 'RETRY_ALLOWED',  label: 'Retry Allowed',  x: 230, y: 270, color: '#B26A00' },
  { id: 'REFUND_PENDING', label: 'Refund Pending', x: 710, y: 70,  color: '#B26A00' },
  { id: 'REFUNDED',       label: 'Refunded',       x: 870, y: 70,  color: '#1F8A4C' },
]

interface EdgeDef {
  id: string
  from: string
  to: string
  d: string
  midX: number
  midY: number
  isBlocked?: boolean
  blockTooltip?: string
}

const EDGES: EdgeDef[] = [
  { id: 'e-cr-pe', from: 'CREATED',       to: 'PENDING',        d: 'M 105 70 L 195 70',                  midX: 150, midY: 70 },
  { id: 'e-pe-co', from: 'PENDING',       to: 'COMPLETED',      d: 'M 265 70 L 515 70',                  midX: 390, midY: 70 },
  { id: 'e-pe-un', from: 'PENDING',       to: 'UNKNOWN',        d: 'M 255 85 Q 320 120 365 155',        midX: 310, midY: 120 },
  { id: 'e-un-co', from: 'UNKNOWN',       to: 'COMPLETED',      d: 'M 415 155 Q 460 120 525 85',        midX: 470, midY: 120 },
  { id: 'e-un-de', from: 'UNKNOWN',       to: 'DENIED',         d: 'M 390 195 L 390 245',                midX: 390, midY: 220 },
  { id: 'e-de-ra', from: 'DENIED',        to: 'RETRY_ALLOWED',  d: 'M 355 270 L 265 270',                midX: 310, midY: 270 },
  { id: 'e-ra-pe', from: 'RETRY_ALLOWED', to: 'PENDING',        d: 'M 230 245 L 230 95',                 midX: 230, midY: 170 },
  { id: 'e-co-rp', from: 'COMPLETED',     to: 'REFUND_PENDING', d: 'M 585 70 L 675 70',                  midX: 630, midY: 70 },
  { id: 'e-rp-rf', from: 'REFUND_PENDING',to: 'REFUNDED',       d: 'M 745 70 L 835 70',                  midX: 790, midY: 70 },
]

export function StateMachineViz({ currentState, lastTransition, blockedRules = [] }: StateMachineVizProps) {
  const normState = currentState?.toUpperCase() || 'UNKNOWN'

  // Determine blocked states / edges
  const isRetryBlocked = normState === 'COMPLETED' || normState === 'PENDING' || normState === 'UNKNOWN'
  const isRefundBlocked = normState !== 'COMPLETED'

  return (
    <div className="w-full overflow-x-auto py-2">
      <div className="min-w-[720px] max-w-[940px] mx-auto">
        <svg viewBox="0 0 940 320" className="w-full h-auto select-none" xmlns="http://www.w3.org/2000/svg">
          <defs>
            <marker
              id="arrowhead"
              markerWidth="7"
              markerHeight="7"
              refX="6"
              refY="3.5"
              orient="auto"
            >
              <polygon points="0 0, 7 3.5, 0 7" fill="#6C7378" />
            </marker>
            <filter id="glow" x="-20%" y="-20%" width="140%" height="140%">
              <feGaussianBlur stdDeviation="5" result="blur" />
              <feComposite in="SourceGraphic" in2="blur" operator="over" />
            </filter>
          </defs>

          {/* Background grid dots */}
          <pattern id="smallGrid" width="20" height="20" patternUnits="userSpaceOnUse">
            <circle cx="2" cy="2" r="1" fill="#EAEDEF" />
          </pattern>
          <rect width="940" height="320" fill="url(#smallGrid)" rx="16" />

          {/* Render Edges */}
          {EDGES.map((edge) => {
            const isLastTransition =
              lastTransition &&
              lastTransition.from.toUpperCase() === edge.from &&
              lastTransition.to.toUpperCase() === edge.to

            // Check if this edge is blocked in the current state
            let blockedReason = ''
            if (edge.id === 'e-ra-pe' && isRetryBlocked) {
              blockedReason =
                normState === 'COMPLETED'
                  ? 'Blocked by policy: R01_COMPLETED_BLOCKS_RETRY (Payment already completed)'
                  : normState === 'PENDING'
                  ? 'Blocked by policy: R02_PENDING_BLOCKS_RETRY (Attempt already pending)'
                  : 'Blocked by policy: R03_UNKNOWN_FAILS_CLOSED (Fails closed on unknown state)'
            } else if (edge.id === 'e-co-rp' && isRefundBlocked) {
              blockedReason = 'Blocked by policy: R05_REFUND_ONLY_COMPLETED (Only COMPLETED orders can be refunded)'
            }

            return (
              <g key={edge.id}>
                {/* The edge line */}
                <path
                  id={edge.id}
                  d={edge.d}
                  fill="none"
                  stroke={blockedReason ? '#D9360B' : '#A2B0BC'}
                  strokeWidth={blockedReason ? 1.5 : 2}
                  strokeDasharray={blockedReason ? '4 3' : 'none'}
                  markerEnd="url(#arrowhead)"
                  opacity={blockedReason ? 0.6 : 0.9}
                />

                {/* Animated traveling dot for last transition */}
                {isLastTransition && (
                  <circle r="4" fill="#0070E0">
                    <animateMotion
                      dur="1.8s"
                      repeatCount="indefinite"
                      path={edge.d}
                    />
                  </circle>
                )}

                {/* Blocked lock icon */}
                {blockedReason && (
                  <g transform={`translate(${edge.midX - 8}, ${edge.midY - 8})`}>
                    <title>{blockedReason}</title>
                    <rect x="0" y="0" width="16" height="16" rx="4" fill="#FDEBE6" stroke="#D9360B" strokeWidth="1" />
                    <foreignObject x="2" y="2" width="12" height="12">
                      <div className="w-full h-full flex items-center justify-center text-danger">
                        <Lock size={9} />
                      </div>
                    </foreignObject>
                  </g>
                )}
              </g>
            )
          })}

          {/* Render State Nodes */}
          {NODES.map((node) => {
            const isCurrent = normState === node.id

            return (
              <g key={node.id} transform={`translate(${node.x}, ${node.y})`}>
                {/* Glowing ring animation on current state */}
                {isCurrent && (
                  <motion.circle
                    r="44"
                    fill="none"
                    stroke={node.color}
                    strokeWidth="3"
                    initial={{ scale: 0.95, opacity: 0.8 }}
                    animate={{ scale: [0.95, 1.25, 0.95], opacity: [0.8, 0.2, 0.8] }}
                    transition={{ duration: 2, repeat: Infinity, ease: 'easeInOut' }}
                  />
                )}

                {/* Node circle */}
                <circle
                  r="35"
                  fill={isCurrent ? node.color : '#FFFFFF'}
                  stroke={isCurrent ? node.color : '#CAD1D8'}
                  strokeWidth={isCurrent ? 3 : 2}
                  filter={isCurrent ? 'url(#glow)' : undefined}
                  className="transition-colors duration-300"
                />

                {/* Node label */}
                <text
                  textAnchor="middle"
                  dy=".3em"
                  fontSize="11"
                  fontWeight={isCurrent ? '700' : '500'}
                  fill={isCurrent ? '#FFFFFF' : '#2C2E2F'}
                  className="pointer-events-none select-none tracking-tight"
                >
                  {node.label}
                </text>
              </g>
            )
          })}
        </svg>
      </div>
      <div className="flex items-center justify-between text-xs text-ink-soft px-4 mt-2">
        <span className="flex items-center gap-1.5">
          <span className="w-2.5 h-2.5 rounded-full bg-pp-blue inline-block animate-pulse" />
          Glowing node = Current authoritative policy state
        </span>
        <span className="flex items-center gap-1.5">
          <Lock size={12} className="text-danger" />
          Lock icon = Blocked transition (hover for exact policy rule)
        </span>
      </div>
    </div>
  )
}
