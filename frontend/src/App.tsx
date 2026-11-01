import React, { useState } from 'react'
import { BrowserRouter, Routes, Route, Navigate, useLocation, useNavigate } from 'react-router-dom'
import { ChevronRight, LayoutDashboard, CreditCard, Home, Minus, Plus, ExternalLink } from 'lucide-react'
import { AuthProvider, useAuth } from './lib/auth'
import { PhoneFrame } from './components/PhoneFrame'
import { Logo } from './components/Logo'
import { Landing } from './pages/Landing'
import { Checkout } from './pages/Checkout'
import { CasePage } from './pages/CasePage'
import { Console } from './pages/Console'

function AppRoutes() {
  return (
    <Routes>
      <Route path="/" element={<Landing />} />
      <Route path="/checkout" element={<Checkout />} />
      <Route path="/cases/:id" element={<CasePage />} />
      <Route path="/console" element={<Console />} />
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  )
}

/** Left column of the site: what this is, and shortcuts into each part of the app. */
function SiteIntro() {
  const nav = useNavigate()
  const { switchRole } = useAuth()
  const { pathname } = useLocation()

  const links = [
    { label: 'Explore the buyer checkout', icon: CreditCard,      to: '/checkout', role: 'buyer' },
    { label: 'See the merchant console',   icon: LayoutDashboard, to: '/console',  role: 'admin' },
    { label: 'Back to the overview',       icon: Home,            to: '/',         role: null },
  ] as const

  return (
    <div className="hidden w-[520px] shrink-0 flex-col lg:flex">
      <Logo size="md" tagline="PAYMENT RECOVERY · PAYPAL SANDBOX" />

      <p className="mt-16 flex items-center gap-3 text-[13px] font-bold uppercase tracking-[0.2em] text-cyan-deep">
        <span className="h-2.5 w-2.5 rounded-full bg-cyan ring-4 ring-cyan/20" aria-hidden />
        Built around the truth
      </p>
      <h1 className="mt-5 text-[76px] font-extrabold leading-[0.98] tracking-[-0.04em] text-navy">
        Your payment.
        <br />
        Made <span className="text-cyan">clear.</span>
      </h1>
      <p className="mt-7 max-w-[470px] text-[19px] leading-[1.75] text-muted">
        From a lost confirmation to the next safe step. A clearer way to check, decide and stay in sync with what PayPal
        actually recorded.
      </p>

      <div className="mt-10 space-y-3.5">
        {links.map(({ label, icon: Icon, to, role }) => {
          const active = pathname === to
          return (
            <button
              key={label}
              onClick={() => {
                if (role) switchRole(role)
                nav(to)
              }}
              className={`group flex w-full items-center gap-4 rounded-[20px] border bg-white/80 px-5 py-[18px] text-left shadow-card backdrop-blur transition-colors ${
                active ? 'border-cyan' : 'border-cyan/25 hover:border-cyan/60'
              }`}
            >
              <span className="flex h-10 w-10 items-center justify-center rounded-xl text-cyan-deep">
                <Icon size={22} />
              </span>
              <span className="flex-1 text-[17px] font-bold text-cyan-deep">{label}</span>
              <ChevronRight size={20} className="text-cyan transition-transform group-hover:translate-x-0.5" />
            </button>
          )
        })}
      </div>

      <div className="mt-8 flex items-center gap-6 text-[14px]">
        <a
          href="https://developer.paypal.com/docs/api/transaction-search/v1/"
          target="_blank"
          rel="noreferrer"
          className="inline-flex items-center gap-1.5 font-bold text-cyan-deep"
        >
          How status checks work <ExternalLink size={14} />
        </a>
      </div>
      <p className="mt-6 text-[13px] leading-relaxed text-muted">
        Interactive sandbox · ResolveAI
        <br />
        PayPal sandbox only. No real payments move.
      </p>
    </div>
  )
}

/** Zoom control like the reference site: scale the phone to fit the screen. */
function ZoomControl({ zoom, setZoom }: { zoom: number; setZoom: (z: number) => void }) {
  const step = (d: number) => setZoom(Math.min(1.2, Math.max(0.6, Math.round((zoom + d) * 100) / 100)))
  return (
    <div className="fixed right-6 top-4 z-50 hidden items-center gap-3 rounded-2xl bg-white px-4 py-2.5 shadow-card ring-1 ring-line lg:flex">
      <span className="w-12 text-[15px] font-semibold tabular-nums text-ink">{Math.round(zoom * 100)}%</span>
      <button onClick={() => step(-0.1)} aria-label="Zoom out" className="flex h-8 w-8 items-center justify-center rounded-full text-navy hover:bg-mist">
        <Minus size={18} />
      </button>
      <button onClick={() => step(0.1)} aria-label="Zoom in" className="flex h-8 w-8 items-center justify-center rounded-full text-navy hover:bg-mist">
        <Plus size={18} />
      </button>
      <button onClick={() => setZoom(1)} className="rounded-full border border-line px-4 py-1.5 text-[14px] font-semibold text-muted hover:bg-mist">
        Reset
      </button>
    </div>
  )
}

export default function App() {
  const [zoom, setZoom] = useState(1)
  return (
    <BrowserRouter>
      <AuthProvider>
        <div className="site-bg flex min-h-[100dvh] items-center justify-center gap-24 px-6 py-4 max-sm:p-0">
          <ZoomControl zoom={zoom} setZoom={setZoom} />
          <SiteIntro />
          <PhoneFrame zoom={zoom}>
            <AppRoutes />
          </PhoneFrame>
        </div>
        <p className="pointer-events-none fixed bottom-4 right-6 hidden text-[12px] font-semibold uppercase tracking-[0.14em] text-muted/70 lg:block">
          ResolveAI / Sandbox
        </p>
      </AuthProvider>
    </BrowserRouter>
  )
}
