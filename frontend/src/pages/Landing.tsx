import React, { useState } from 'react'
import { motion } from 'framer-motion'
import { useNavigate } from 'react-router-dom'
import { Shield, AlertTriangle, Clock, ChevronRight, User, Building2, CreditCard, Check } from 'lucide-react'
import { useAuth } from '../lib/auth'

// Buyer -> PayPal -> Seller. Tap to see the payment resolve.
function HeroScene() {
  const [resolved, setResolved] = useState(false)
  return (
    <button
      onClick={() => setResolved((r) => !r)}
      className="relative block w-full select-none"
      aria-label={resolved ? 'Payment resolved. Tap to reset.' : 'Payment unconfirmed. Tap to resolve.'}
    >
      <svg viewBox="0 0 340 150" className="h-auto w-full overflow-visible">
        <path d="M 66 70 L 132 70" stroke="#fff" strokeOpacity=".55" strokeWidth="2.5" strokeDasharray="5 5" fill="none" />
        <path
          d="M 208 70 L 274 70"
          stroke={resolved ? '#7CF0A8' : '#fff'}
          strokeOpacity={resolved ? 1 : 0.25}
          strokeWidth="2.5"
          strokeDasharray="5 5"
          fill="none"
        />
        <circle r="4.5" fill="#FFC439">
          <animateMotion dur="2s" repeatCount="indefinite" path="M 66 70 L 132 70" />
        </circle>
        {resolved && (
          <circle r="4.5" fill="#7CF0A8">
            <animateMotion dur="1.6s" repeatCount="indefinite" path="M 208 70 L 274 70" />
          </circle>
        )}

        {/* Buyer */}
        <circle cx="40" cy="70" r="26" fill="#fff" />
        <foreignObject x="28" y="58" width="24" height="24">
          <div className="flex h-full w-full items-center justify-center text-navy"><User size={18} /></div>
        </foreignObject>
        <text x="40" y="118" textAnchor="middle" fill="#fff" fontSize="12" fontWeight="700">Buyer</text>

        {/* PayPal */}
        <circle cx="170" cy="70" r="36" fill="#fff" stroke={resolved ? '#7CF0A8' : '#FFC439'} strokeWidth="4" />
        <foreignObject x="156" y="56" width="28" height="28">
          <div className="flex h-full w-full items-center justify-center text-navy"><CreditCard size={22} /></div>
        </foreignObject>
        <text x="170" y="126" textAnchor="middle" fill="#fff" fontSize="12" fontWeight="700">PayPal</text>
        <g transform="translate(200 28)">
          {resolved ? (
            <motion.g initial={{ scale: 0.6 }} animate={{ scale: 1 }} transition={{ type: 'spring', damping: 12 }}>
              <circle r="14" fill="#1F8A4C" stroke="#fff" strokeWidth="2" />
              <foreignObject x="-8" y="-8" width="16" height="16">
                <div className="flex h-full w-full items-center justify-center text-white"><Check size={12} strokeWidth={3.5} /></div>
              </foreignObject>
            </motion.g>
          ) : (
            <g>
              <circle r="14" fill="#FFC439" stroke="#1E2A3B" strokeWidth="1.5" />
              <text dy=".35em" textAnchor="middle" fill="#1E2A3B" fontSize="15" fontWeight="800">?</text>
            </g>
          )}
        </g>

        {/* Seller */}
        <circle cx="300" cy="70" r="26" fill={resolved ? '#1F8A4C' : '#fff'} className="transition-colors duration-500" />
        <foreignObject x="288" y="58" width="24" height="24">
          <div className={`flex h-full w-full items-center justify-center ${resolved ? 'text-white' : 'text-navy'}`}>
            <Building2 size={18} />
          </div>
        </foreignObject>
        <text x="300" y="118" textAnchor="middle" fill="#fff" fontSize="12" fontWeight="700">Seller</text>
      </svg>
      <p className="mt-1 text-center text-[12px] font-semibold text-white/80">
        {resolved ? 'Confirmed by PayPal. Safe to ship.' : 'Unconfirmed. Tap to see how we resolve it.'}
      </p>
    </button>
  )
}

const SCENARIOS = [
  {
    icon: AlertTriangle,
    tint: 'bg-[#FFF4D6] text-warning',
    title: 'Response never arrived',
    desc: 'Paid on PayPal, but the confirmation timed out. We hold the retry and check the real status.',
    badge: 'Timeout',
  },
  {
    icon: Shield,
    tint: 'bg-[#FDEBE6] text-danger',
    title: 'Payment declined',
    desc: 'PayPal said no. A fresh retry only opens after you review the proof.',
    badge: 'Declined',
  },
  {
    icon: Clock,
    tint: 'bg-cyan-soft text-cyan-deep',
    title: 'Confirmation running late',
    desc: 'The case updates live when PayPal’s delayed confirmation lands.',
    badge: 'Delayed',
  },
]

export function Landing() {
  const nav = useNavigate()
  const { switchRole } = useAuth()

  return (
    <div className="space-y-5 px-5 pb-8 pt-2">
      <section className="overflow-hidden rounded-[28px] bg-gradient-to-br from-cyan via-[#0A74C8] to-navy p-5 text-white shadow-card">
        <h1 className="text-[27px] font-extrabold leading-[1.1] tracking-[-0.025em]">
          The safe, easier way to settle a stuck payment.
        </h1>
        <p className="mt-2 text-[13px] leading-relaxed text-white/80">
          We read PayPal’s own records before anyone pays twice.
        </p>
        <div className="mt-4 rounded-2xl bg-white/10 px-3 pb-3 pt-5">
          <HeroScene />
        </div>
        <div className="mt-4 grid grid-cols-2 gap-2.5">
          <button
            onClick={() => { switchRole('buyer'); nav('/checkout') }}
            className="min-h-[50px] rounded-full bg-pp-gold px-3 text-[14px] font-extrabold text-ink"
          >
            Start checkout
          </button>
          <button
            onClick={() => { switchRole('admin'); nav('/console') }}
            className="min-h-[50px] rounded-full bg-white/15 px-3 text-[14px] font-bold text-white ring-1 ring-white/30"
          >
            Open console
          </button>
        </div>
      </section>

      <section>
        <div className="mb-2.5 flex items-baseline justify-between px-1">
          <h2 className="text-[17px] font-extrabold tracking-tight text-navy">What goes wrong</h2>
          <span className="text-[12px] font-semibold text-muted">Tap to try it</span>
        </div>
        <ul className="space-y-2.5">
          {SCENARIOS.map(({ icon: Icon, tint, title, desc, badge }) => (
            <li key={title}>
              <button
                onClick={() => { switchRole('buyer'); nav('/checkout') }}
                className="flex w-full items-start gap-3 rounded-card bg-white p-3.5 text-left shadow-card"
              >
                <span className={`flex h-11 w-11 shrink-0 items-center justify-center rounded-full ${tint}`}>
                  <Icon size={20} />
                </span>
                <span className="min-w-0 flex-1">
                  <span className="flex items-center justify-between gap-2">
                    <span className="text-[14.5px] font-bold text-navy">{title}</span>
                    <span className={`shrink-0 rounded-full px-2 py-0.5 text-[11px] font-bold ${tint}`}>{badge}</span>
                  </span>
                  <span className="mt-0.5 block text-[12.5px] leading-snug text-muted">{desc}</span>
                </span>
                <ChevronRight size={18} className="mt-3 shrink-0 text-cyan" />
              </button>
            </li>
          ))}
        </ul>
      </section>

      <p className="px-2 text-center text-[11px] leading-relaxed text-muted">
        Built on the PayPal Developer Platform. Sandbox only, no real money moves.
      </p>
    </div>
  )
}
