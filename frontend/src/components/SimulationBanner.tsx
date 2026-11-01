import React from 'react'
import { FlaskConical } from 'lucide-react'

export function SimulationBanner({ message }: { message?: string }) {
  return (
    <div className="sim-stripe flex items-start gap-2 rounded-2xl border border-pp-gold p-3 text-[12px] font-bold leading-snug text-ink">
      <FlaskConical size={16} className="mt-0.5 shrink-0 text-warning" />
      <span>{message || 'Simulation: this event was injected by the fault lab. It is not a real PayPal transaction.'}</span>
    </div>
  )
}
