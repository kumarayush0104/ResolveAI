import React from 'react'
import { useAuth } from '../lib/auth'
import { useNavigate } from 'react-router-dom'

const ROLES = ['buyer', 'seller', 'admin'] as const
const LABELS: Record<string, string> = { buyer: 'Buyer', seller: 'Seller', admin: 'Merchant Console' }

export function RoleSwitcher() {
  const { role, switchRole } = useAuth()
  const nav = useNavigate()

  const handleSwitch = (r: 'buyer' | 'seller' | 'admin') => {
    switchRole(r)
    if (r === 'admin') {
      nav('/console')
    }
  }

  return (
    <div className="flex items-center bg-surface rounded-full p-1 border border-line shadow-inner">
      {ROLES.map((r) => (
        <button
          key={r}
          onClick={() => handleSwitch(r)}
          className={`px-4 py-1.5 rounded-full text-sm font-medium transition-all duration-200 ${
            role === r
              ? 'bg-pp-blue-dark text-white shadow-sm'
              : 'text-ink-soft hover:text-ink'
          }`}
        >
          {LABELS[r]}
        </button>
      ))}
    </div>
  )
}
