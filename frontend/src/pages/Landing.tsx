import React, { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  Shield, AlertTriangle, Clock, ArrowRight,
  CreditCard, ShoppingBag, BarChart2, RefreshCw, Sparkles,
} from 'lucide-react'
import { TopBar } from '../components/TopBar'
import { Card } from '../components/Card'
import { PillButton } from '../components/PillButton'
import { useAuth } from '../lib/auth'

// ── Scenarios ────────────────────────────────────────────────────────────────
const SCENARIOS = [
  {
    icon: <Clock size={20} className="text-warning" />,
    badge: 'STUCK',
    badgeColor: 'bg-[#FFF4D6] text-warning',
    title: 'Stuck Payment',
    desc: 'Captured in PayPal, silent in your DB. ResolveAI re-queries live APIs and drives recovery.',
  },
  {
    icon: <AlertTriangle size={20} className="text-danger" />,
    badge: 'DOUBLE-CHARGE',
    badgeColor: 'bg-[#FDEBE6] text-danger',
    title: 'Double Charge Risk',
    desc: 'Idempotency key mismatch or retry storm. Policy rule R04 blocks duplicate captures.',
  },
  {
    icon: <Shield size={20} className="text-pp-blue" />,
    badge: 'DISPUTE',
    badgeColor: 'bg-blue-50 text-pp-blue',
    title: 'Dispute & Refund',
    desc: 'Buyer opens a dispute. AI Investigator gathers authoritative evidence and proposes resolution.',
  },
]

// ── Mini Hero Scene ───────────────────────────────────────────────────────────
function MiniHero() {
  const [resolved, setResolved] = useState(false)
  return (
    <div
      className="w-full h-32 cursor-pointer select-none"
      onClick={() => setResolved(r => !r)}
      title="Tap to resolve"
    >
      <svg viewBox="0 0 320 100" className="w-full h-full overflow-visible">
        <defs>
          <linearGradient id="miniGrad" x1="0%" y1="0%" x2="100%" y2="0%">
            <stop offset="0%"   stopColor="#009CDE" />
            <stop offset="50%"  stopColor="#FFC439" />
            <stop offset="100%" stopColor="#1F8A4C" />
          </linearGradient>
        </defs>
        <path d="M 60 50 L 145 50" fill="none" stroke="url(#miniGrad)"
          strokeWidth="2.5" strokeDasharray="5 4" opacity="0.9" />
        <path d="M 175 50 L 260 50" fill="none"
          stroke={resolved ? '#1F8A4C' : '#EAEDEF'}
          strokeWidth="2.5" strokeDasharray="5 4"
          className="transition-colors duration-500" />
        <circle r="4" fill="#FFC439">
          <animateMotion dur="1.6s" repeatCount="indefinite" path="M 60 50 L 145 50" />
        </circle>
        {resolved && (
          <circle r="4" fill="#1F8A4C">
            <animateMotion dur="1.6s" repeatCount="indefinite" path="M 175 50 L 260 50" />
          </circle>
        )}
        {/* Buyer */}
        <circle cx="40" cy="50" r="20" fill="#001C64" stroke="#009CDE" strokeWidth="2" />
        <text x="40" y="54" textAnchor="middle" fill="white" fontSize="9" fontWeight="600">Buyer</text>
        {/* PayPal Hub */}
        <circle cx="160" cy="50" r="26" fill="white"
          stroke={resolved ? '#1F8A4C' : '#0070E0'}
          strokeWidth="2.5" className="transition-colors duration-500" />
        <text x="160" y="47" textAnchor="middle" fill="#003087" fontSize="7" fontWeight="700">Resolve</text>
        <text x="160" y="57" textAnchor="middle" fill="#003087" fontSize="7" fontWeight="700">AI</text>
        {/* Morphing bubble */}
        {resolved ? (
          <circle cx="160" cy="24" r="11" fill="#1F8A4C">
            <animate attributeName="r" values="9;11;9" dur="1s" repeatCount="indefinite" />
          </circle>
        ) : (
          <circle cx="160" cy="24" r="10" fill="#FFC439">
            <animate attributeName="r" values="9;11;9" dur="1.5s" repeatCount="indefinite" />
          </circle>
        )}
        <text x="160" y="28" textAnchor="middle" fill="white" fontSize="11" fontWeight="800">
          {resolved ? '✓' : '?'}
        </text>
        {/* Seller */}
        <circle cx="280" cy="50" r="20" fill="#001C64"
          stroke={resolved ? '#1F8A4C' : '#EAEDEF'}
          strokeWidth="2" className="transition-colors duration-500" />
        <text x="280" y="54" textAnchor="middle" fill="white" fontSize="9" fontWeight="600">Seller</text>
      </svg>
      <p className="text-center text-[10px] text-white/60 -mt-1">Tap to resolve payment</p>
    </div>
  )
}

// ── Role switcher options ─────────────────────────────────────────────────────
const ROLES = [
  { key: 'buyer',  label: 'Buyer'   },
  { key: 'seller', label: 'Seller'  },
  { key: 'admin',  label: 'Console' },
] as const

// ── Landing Page ──────────────────────────────────────────────────────────────
export function Landing() {
  const nav = useNavigate()
  const { role, switchRole } = useAuth()

  const handleRole = (r: 'buyer' | 'seller' | 'admin') => {
    switchRole(r)
    if (r === 'admin') nav('/console')
  }

  const roleLabel =
    role === 'admin'  ? 'Merchant Console' :
    role === 'seller' ? 'Seller' : 'Buyer'

  const greeting =
    new Date().getHours() < 12 ? 'Good morning' :
    new Date().getHours() < 17 ? 'Good afternoon' : 'Good evening'

  return (
    <div className="min-h-full bg-surface">

      {/* ── Hero gradient section ── */}
      <section className="hero-gradient pb-8 rounded-b-[2.5rem] relative overflow-hidden">
        {/* Decorative blobs */}
        <div className="absolute -top-16 -right-16 w-48 h-48 rounded-full bg-white/5 blur-2xl pointer-events-none" />
        <div className="absolute -bottom-8 -left-10 w-40 h-40 rounded-full bg-white/5 blur-xl pointer-events-none" />

        {/* Top bar */}
        <TopBar />

        {/* Greeting */}
        <div className="px-5 mt-1">
          <p className="text-white/70 text-sm font-medium">{greeting}, {roleLabel} 👋</p>
          <h1 className="text-white font-bold text-2xl mt-0.5 leading-tight">
            Payments should never<br />leave you guessing.
          </h1>
        </div>

        {/* Balance / Stats card */}
        <div className="px-5 mt-5">
          <div className="bg-white/15 backdrop-blur-sm rounded-3xl p-5 border border-white/20">
            <p className="text-white/70 text-xs font-semibold uppercase tracking-widest">
              Autonomous Recovery Engine
            </p>
            <div className="flex items-end justify-between mt-2">
              <div>
                <p className="text-white font-bold text-3xl tracking-tight">$0.00</p>
                <p className="text-white/60 text-xs mt-1">Sandbox Mode · PayPal APIs</p>
              </div>
              <span className="text-xs font-mono bg-pp-gold/20 text-pp-gold px-2.5 py-1 rounded-full font-semibold border border-pp-gold/30">
                SANDBOX
              </span>
            </div>
            {/* Mini hero animation */}
            <div className="mt-4">
              <MiniHero />
            </div>
          </div>
        </div>

        {/* Quick action buttons */}
        <div className="px-5 mt-5 grid grid-cols-4 gap-3">
          {[
            { label: 'Checkout', Icon: ShoppingBag, path: '/checkout', bg: 'bg-white/20' },
            { label: 'Console',  Icon: BarChart2,   path: '/console',  bg: 'bg-white/20' },
            { label: 'Cases',    Icon: Sparkles,    path: '/console',  bg: 'bg-white/20' },
            { label: 'Resolve',  Icon: RefreshCw,   path: '/checkout', bg: 'bg-pp-gold/80' },
          ].map(({ label, Icon, path, bg }) => (
            <button
              key={label}
              onClick={() => nav(path)}
              className="flex flex-col items-center gap-1.5 group"
            >
              <div className={`w-12 h-12 rounded-2xl ${bg} backdrop-blur flex items-center justify-center text-white transition-transform group-active:scale-95`}>
                <Icon size={20} />
              </div>
              <span className="text-white/80 text-[10px] font-semibold">{label}</span>
            </button>
          ))}
        </div>
      </section>

      {/* ── Role Switcher ── */}
      <section className="px-5 mt-6">
        <p className="text-xs text-ink-soft font-semibold uppercase tracking-wider mb-3">Switch Role</p>
        <div className="flex items-center bg-white rounded-2xl p-1 border border-line shadow-card gap-1">
          {ROLES.map(({ key, label }) => (
            <button
              key={key}
              onClick={() => handleRole(key)}
              className={`flex-1 py-2 rounded-xl text-sm font-semibold transition-all duration-200 ${
                role === key
                  ? 'bg-pp-blue-dark text-white shadow-sm'
                  : 'text-ink-soft hover:text-ink'
              }`}
            >
              {label}
            </button>
          ))}
        </div>
      </section>

      {/* ── Stats Row ── */}
      <section className="px-5 mt-6">
        <div className="grid grid-cols-3 gap-3">
          {[
            { label: 'Total Cases', value: '—', color: 'text-pp-blue'  },
            { label: 'Resolved',    value: '—', color: 'text-success'  },
            { label: 'Pending',     value: '—', color: 'text-warning'  },
          ].map(({ label, value, color }) => (
            <div key={label} className="bg-white rounded-2xl p-4 border border-line shadow-card text-center">
              <p className={`font-bold text-xl ${color}`}>{value}</p>
              <p className="text-ink-soft text-[10px] font-semibold mt-0.5 leading-tight">{label}</p>
            </div>
          ))}
        </div>
      </section>

      {/* ── CTA Buttons ── */}
      <section className="px-5 mt-6 flex flex-col gap-3">
        <PillButton
          variant="gold"
          onClick={() => nav('/checkout')}
          className="w-full text-base font-bold shadow-float"
        >
          <ShoppingBag size={18} />
          <span>Start Sandbox Checkout</span>
          <ArrowRight size={16} />
        </PillButton>
        <PillButton
          variant="outline"
          onClick={() => nav('/console')}
          className="w-full"
        >
          Open Merchant Console
        </PillButton>
      </section>

      {/* ── Scenarios horizontal scroll ── */}
      <section className="mt-8 px-5">
        <div className="flex items-center justify-between mb-4">
          <h2 className="font-bold text-pp-blue-dark text-lg">Payment Scenarios</h2>
          <span className="text-xs text-ink-soft">Tap to simulate →</span>
        </div>
        <div className="scroll-row">
          {SCENARIOS.map((sc, i) => (
            <div
              key={i}
              onClick={() => nav('/checkout')}
              className="flex-shrink-0 w-[220px] bg-white rounded-2xl border border-line shadow-card p-4 cursor-pointer active:scale-95 transition-transform"
            >
              <div className="flex items-center justify-between mb-3">
                <div className="p-2.5 bg-surface rounded-xl">{sc.icon}</div>
                <span className={`text-[10px] font-bold px-2 py-0.5 rounded-full ${sc.badgeColor}`}>
                  {sc.badge}
                </span>
              </div>
              <h3 className="font-bold text-ink text-sm mb-1">{sc.title}</h3>
              <p className="text-xs text-ink-soft leading-relaxed">{sc.desc}</p>
              <div className="mt-3 flex items-center gap-1 text-xs font-semibold text-pp-blue">
                <span>Simulate</span><ArrowRight size={11} />
              </div>
            </div>
          ))}
        </div>
      </section>

      {/* ── How It Works ── */}
      <section className="px-5 mt-8">
        <h2 className="font-bold text-pp-blue-dark text-lg mb-4">How ResolveAI Works</h2>
        <div className="space-y-3">
          {[
            { icon: <CreditCard size={18} className="text-pp-blue" />,  title: 'Real PayPal APIs',    desc: 'OAuth2 + Orders v2 + Payments v2. Every decision is grounded in authoritative live data.' },
            { icon: <Shield size={18} className="text-success" />,       title: 'Fail-Closed Policy',  desc: 'Rules R01–R09 block any action that cannot be proven safe. Timeouts ≠ failure.' },
            { icon: <Sparkles size={18} className="text-pp-gold" />,     title: 'AI Investigator',     desc: 'Streams tool calls in real-time. Evidence cites. Buyer & Seller guidance. Policy-adjusted.' },
          ].map(({ icon, title, desc }) => (
            <div key={title} className="bg-white rounded-2xl border border-line shadow-card p-4 flex gap-4 items-start">
              <div className="p-2.5 bg-surface rounded-xl shrink-0">{icon}</div>
              <div>
                <p className="font-bold text-ink text-sm">{title}</p>
                <p className="text-xs text-ink-soft mt-0.5 leading-relaxed">{desc}</p>
              </div>
            </div>
          ))}
        </div>
      </section>

      {/* ── Footer ── */}
      <footer className="mt-8 px-5 py-6 text-center text-[10px] text-ink-soft border-t border-line">
        <p>Built on the PayPal Developer Platform · Sandbox</p>
        <p className="mt-1 text-gray-400">
          OAuth2 · Orders v2 · Payments v2 · Webhooks · Policy Engine (R01–R09)
        </p>
      </footer>
    </div>
  )
}
