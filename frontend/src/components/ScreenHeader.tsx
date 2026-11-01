import React from 'react'
import { Link } from 'react-router-dom'
import { ChevronLeft } from 'lucide-react'

export function ScreenHeader({
  label,
  title,
  subtitle,
  back,
}: {
  label: string
  title: string
  subtitle?: React.ReactNode
  back?: { to: string; label?: string }
}) {
  return (
    <div className="space-y-3">
      {back && (
        <Link
          to={back.to}
          className="inline-flex items-center gap-1 text-[14px] font-bold text-cyan-deep -ml-1 pr-2 py-1 rounded-lg"
        >
          <ChevronLeft size={18} strokeWidth={2.5} />
          {back.label ?? 'Back'}
        </Link>
      )}
      <div>
        <p className="text-[11px] font-bold uppercase tracking-[0.16em] text-cyan-deep">{label}</p>
        <h1 className="mt-1.5 text-[26px] leading-[1.1] font-extrabold tracking-[-0.025em] text-navy">{title}</h1>
        {subtitle && <div className="mt-2 text-[14px] leading-relaxed text-muted">{subtitle}</div>}
      </div>
    </div>
  )
}
