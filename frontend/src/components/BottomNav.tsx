import React from 'react'
import { useLocation, useNavigate } from 'react-router-dom'
import { Home, ShoppingBag, FolderOpen, LayoutGrid } from 'lucide-react'

const TABS = [
  { path: '/',        label: 'Home',    Icon: Home },
  { path: '/checkout',label: 'Pay',     Icon: ShoppingBag },
  { path: '/console', label: 'Console', Icon: LayoutGrid },
  { path: '/cases',   label: 'Cases',   Icon: FolderOpen },
]

export function BottomNav() {
  const location = useLocation()
  const nav = useNavigate()

  const isActive = (path: string) => {
    if (path === '/') return location.pathname === '/'
    if (path === '/cases') return location.pathname.startsWith('/cases')
    return location.pathname === path
  }

  return (
    <nav className="bottom-nav bg-white border-t border-line safe-area-inset-bottom">
      <div className="flex items-center justify-around h-[64px] px-2">
        {TABS.map(({ path, label, Icon }) => {
          const active = isActive(path)
          return (
            <button
              key={path}
              onClick={() => nav(path)}
              className="flex flex-col items-center justify-center gap-0.5 flex-1 py-2 group"
            >
              <div
                className={`
                  flex items-center justify-center w-10 h-10 rounded-2xl transition-all duration-200
                  ${active
                    ? 'bg-pp-blue text-white shadow-float scale-110'
                    : 'text-ink-soft group-hover:text-pp-blue group-hover:bg-blue-50'}
                `}
              >
                <Icon size={20} strokeWidth={active ? 2.5 : 1.8} />
              </div>
              <span
                className={`text-[10px] font-semibold tracking-wide transition-colors ${
                  active ? 'text-pp-blue' : 'text-ink-soft'
                }`}
              >
                {label}
              </span>
            </button>
          )
        })}
      </div>
    </nav>
  )
}
