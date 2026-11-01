import React, { useEffect, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { AnimatePresence } from 'framer-motion'
import { Bell, ChevronDown, ChevronRight, Check, ShoppingBag, Store, ShieldCheck, Store as Shop } from 'lucide-react'
import { LogoMark } from './Logo'
import { Sheet } from './Sheet'
import { StatusBadge } from './StatusBadge'
import { useAuth } from '../lib/auth'
import { api } from '../lib/api'

const ROLES = [
  { id: 'buyer',  label: 'Buyer',    note: 'Pay and track a payment',           icon: ShoppingBag },
  { id: 'seller', label: 'Seller',   note: 'See what to ship and when',         icon: Store },
  { id: 'admin',  label: 'Merchant', note: 'Console for all cases and metrics', icon: ShieldCheck },
] as const

const SHORT: Record<string, string> = { buyer: 'Buyer', seller: 'Seller', admin: 'Merchant' }
const UNRESOLVED = ['UNKNOWN', 'PENDING', 'REFUND_PENDING']

export function AppBar() {
  const { role, switchRole, token } = useAuth()
  const nav = useNavigate()
  const [rolesOpen, setRolesOpen] = useState(false)
  const [bellOpen, setBellOpen] = useState(false)
  const [open, setOpen] = useState<any[]>([])

  // The bell counts real cases that still need attention (merchant roles only).
  useEffect(() => {
    if (!token || role === 'buyer') { setOpen([]); return }
    let alive = true
    api.getMetrics()
      .then((m: any) => { if (alive) setOpen((m.cases ?? []).filter((c: any) => UNRESOLVED.includes(c.status))) })
      .catch(() => { if (alive) setOpen([]) })
    return () => { alive = false }
  }, [role, token, bellOpen])

  const pick = (r: string) => {
    switchRole(r)
    setRolesOpen(false)
    nav(r === 'admin' ? '/console' : '/')
  }

  return (
    <header className="shrink-0 bg-white">
      <div className="flex items-center justify-between px-5 pb-3 pt-2 max-sm:pt-4">
        <Link to="/" className="flex items-center gap-2" aria-label="ResolveAI home">
          <LogoMark size={36} />
          <span className="text-[21px] font-extrabold tracking-tight text-navy">
            Resolve<span className="text-cyan">AI</span>
          </span>
        </Link>
        <div className="flex items-center gap-2.5">
          <button
            onClick={() => setBellOpen(true)}
            className="relative flex h-11 w-11 items-center justify-center rounded-full bg-mist text-navy ring-1 ring-line"
            aria-label={open.length ? `${open.length} cases need attention` : 'Notifications'}
          >
            <Bell size={20} />
            {open.length > 0 && (
              <span className="absolute -right-0.5 -top-0.5 flex h-[18px] min-w-[18px] items-center justify-center rounded-full bg-navy px-1 text-[10.5px] font-extrabold text-white ring-2 ring-white">
                {open.length}
              </span>
            )}
          </button>
          <span
            className="flex h-11 w-11 items-center justify-center rounded-full bg-cyan-soft text-[14px] font-extrabold text-cyan-deep ring-1 ring-cyan/30"
            aria-hidden
          >
            RD
          </span>
        </div>
      </div>

      {/* Business and role, like a workspace switcher */}
      <div className="flex items-center justify-between border-b border-line px-5 pb-3">
        <span className="flex min-w-0 items-center gap-2 text-[11.5px] font-bold uppercase tracking-[0.12em] text-navy">
          <Shop size={15} className="shrink-0 text-cyan-deep" />
          <span className="truncate">ResolveAI demo store</span>
        </span>
        <button
          onClick={() => setRolesOpen(true)}
          className="flex shrink-0 items-center gap-1 text-[14px] font-bold text-cyan-deep"
          aria-label={`Viewing as ${SHORT[role] ?? role}. Change role`}
        >
          {SHORT[role] ?? role}
          <ChevronDown size={16} />
        </button>
      </div>

      <AnimatePresence>
        {rolesOpen && (
          <Sheet title="Switch role" onClose={() => setRolesOpen(false)}>
            <div className="space-y-2 pt-1">
              {ROLES.map(({ id, label, note, icon: Icon }) => (
                <button
                  key={id}
                  onClick={() => pick(id)}
                  className={`flex w-full items-center gap-3 rounded-2xl border p-3.5 text-left ${
                    role === id ? 'border-cyan bg-cyan-soft' : 'border-line bg-white'
                  }`}
                >
                  <span className="flex h-11 w-11 items-center justify-center rounded-full bg-white text-cyan-deep shadow-card">
                    <Icon size={20} />
                  </span>
                  <span className="flex-1">
                    <span className="block text-[15px] font-bold text-navy">{label}</span>
                    <span className="block text-[12px] text-muted">{note}</span>
                  </span>
                  {role === id && <Check size={18} className="text-cyan-deep" />}
                </button>
              ))}
            </div>
          </Sheet>
        )}
        {bellOpen && (
          <Sheet title="Needs attention" onClose={() => setBellOpen(false)}>
            {open.length === 0 ? (
              <p className="rounded-2xl bg-mist p-4 text-center text-[13px] text-muted">
                {role === 'buyer'
                  ? 'Open a case from checkout and its updates will show here for merchants.'
                  : 'Nothing is waiting on you. Every case has a verified outcome.'}
              </p>
            ) : (
              <ul className="space-y-2 pt-1">
                {open.map((c) => (
                  <li key={c.id}>
                    <button
                      onClick={() => { setBellOpen(false); nav(`/cases/${c.id}`) }}
                      className="flex w-full items-center gap-3 rounded-2xl bg-mist p-3 text-left"
                    >
                      <span className="min-w-0 flex-1">
                        <span className="block font-mono text-[13px] font-semibold text-navy">#{String(c.id).slice(0, 8)}</span>
                        <span className="mt-1 block"><StatusBadge status={c.status} /></span>
                      </span>
                      <ChevronRight size={16} className="text-cyan" />
                    </button>
                  </li>
                ))}
              </ul>
            )}
          </Sheet>
        )}
      </AnimatePresence>
    </header>
  )
}
