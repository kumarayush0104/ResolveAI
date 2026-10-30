import React from 'react'
import { RoleSwitcher } from './RoleSwitcher'
import { Shield, ArrowRight } from 'lucide-react'
import { Link } from 'react-router-dom'

export function TopBar() {
  return (
    <header className="h-16 bg-white border-b border-line flex items-center px-6 gap-6 sticky top-0 z-40 shadow-sm">
      <Link to="/" className="flex items-center gap-2 group">
        <div className="w-8 h-8 rounded-full bg-pp-blue/10 flex items-center justify-center text-pp-blue group-hover:bg-pp-blue group-hover:text-white transition-colors duration-200">
          <Shield size={18} />
        </div>
        <span className="font-bold text-pp-blue-dark text-lg tracking-tight">ResolveAI</span>
      </Link>

      <div className="flex-1 flex justify-center">
        <RoleSwitcher />
      </div>

      <div className="flex items-center gap-4">
        <Link
          to="/checkout"
          className="hidden sm:inline-flex items-center gap-1 text-xs font-semibold text-pp-blue hover:text-pp-blue-dark transition-colors"
        >
          <span>Sandbox Checkout</span>
          <ArrowRight size={12} />
        </Link>
        <span className="text-xs font-mono bg-pp-gold/20 text-pp-blue-dark px-2.5 py-1 rounded-full font-semibold border border-pp-gold/40">
          SANDBOX
        </span>
      </div>
    </header>
  )
}
