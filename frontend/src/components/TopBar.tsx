import React from 'react'
import { Shield, Bell } from 'lucide-react'
import { Link } from 'react-router-dom'
import { useAuth } from '../lib/auth'

interface TopBarProps {
  title?: string
  showBack?: boolean
  onBack?: () => void
  rightElement?: React.ReactNode
}

export function TopBar({ title, showBack, onBack, rightElement }: TopBarProps) {
  const { role } = useAuth()

  const roleInitial = role === 'admin' ? 'A' : role === 'seller' ? 'S' : 'B'
  const roleColor =
    role === 'admin'  ? 'bg-pp-gold text-pp-navy' :
    role === 'seller' ? 'bg-success text-white'   :
                        'bg-pp-blue text-white'

  return (
    <header className="flex items-center justify-between px-5 pt-12 pb-4 bg-transparent">
      {/* Logo or Back */}
      {showBack ? (
        <button
          onClick={onBack}
          className="w-10 h-10 rounded-2xl bg-white/20 backdrop-blur flex items-center justify-center text-white"
        >
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none"
            stroke="currentColor" strokeWidth="2.5" strokeLinecap="round">
            <path d="M15 18l-6-6 6-6" />
          </svg>
        </button>
      ) : (
        <Link to="/" className="flex items-center gap-2">
          <div className="w-9 h-9 rounded-2xl bg-white/20 backdrop-blur flex items-center justify-center text-white">
            <Shield size={18} strokeWidth={2.5} />
          </div>
          <span className="font-bold text-white text-lg tracking-tight">ResolveAI</span>
        </Link>
      )}

      {title && (
        <span className="font-bold text-white text-base">{title}</span>
      )}

      {/* Right: notifications + avatar */}
      <div className="flex items-center gap-2">
        {rightElement ?? (
          <>
            <button className="w-10 h-10 rounded-2xl bg-white/20 backdrop-blur flex items-center justify-center text-white relative">
              <Bell size={18} />
              <span className="absolute top-1.5 right-1.5 w-2 h-2 rounded-full bg-pp-gold border border-white" />
            </button>
            <div className={`w-10 h-10 rounded-2xl ${roleColor} flex items-center justify-center font-bold text-sm`}>
              {roleInitial}
            </div>
          </>
        )}
      </div>
    </header>
  )
}
