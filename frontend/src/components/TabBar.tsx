import React from 'react'
import { NavLink } from 'react-router-dom'
import { Home, CreditCard, LayoutDashboard } from 'lucide-react'

const TABS = [
  { to: '/',         label: 'Home',    icon: Home,            end: true },
  { to: '/checkout', label: 'Pay',     icon: CreditCard,      end: false },
  { to: '/console',  label: 'Console', icon: LayoutDashboard, end: false },
]

export function TabBar() {
  return (
    <nav
      aria-label="Main"
      className="relative z-10 flex shrink-0 items-stretch justify-around border-t border-line bg-white px-4 pb-4 pt-2 max-sm:pb-[max(1rem,env(safe-area-inset-bottom))]"
    >
      {TABS.map(({ to, label, icon: Icon, end }) => (
        <NavLink
          key={to}
          to={to}
          end={end}
          className={({ isActive }) =>
            `flex w-24 flex-col items-center gap-1 rounded-2xl py-1.5 text-[11px] font-bold ${
              isActive ? 'text-cyan-deep' : 'text-muted'
            }`
          }
        >
          {({ isActive }) => (
            <>
              <span
                className={`flex h-8 w-14 items-center justify-center rounded-full transition-colors ${
                  isActive ? 'bg-cyan-soft' : ''
                }`}
              >
                <Icon size={20} strokeWidth={isActive ? 2.4 : 2} />
              </span>
              {label}
            </>
          )}
        </NavLink>
      ))}
    </nav>
  )
}
