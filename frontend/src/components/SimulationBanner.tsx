import React from 'react'
import { FlaskConical } from 'lucide-react'

export function SimulationBanner({ message }: { message?: string }) {
  return (
    <div className="sim-stripe border border-pp-gold rounded-xl p-3 flex items-center gap-2 text-sm font-semibold text-[#2C2E2F] shadow-sm">
      <FlaskConical size={16} className="text-pp-gold shrink-0" />
      <span>{message || 'SIMULATION — This event was injected by the Fault-Injection Lab. Not a real PayPal transaction.'}</span>
    </div>
  )
}
