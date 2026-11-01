import React from 'react'
import { CheckCircle, Clock, AlertTriangle, XCircle, HelpCircle } from 'lucide-react'

const STATE_MAP: Record<string, { label: string; icon: React.ReactNode; className: string }> = {
  COMPLETED:      { label: 'Completed',        icon: <CheckCircle size={13} />,   className: 'bg-[#E4F5EB] text-success' },
  PENDING:        { label: 'Pending',          icon: <Clock size={13} />,         className: 'bg-[#FFF4D6] text-warning' },
  UNKNOWN:        { label: 'Unknown',          icon: <HelpCircle size={13} />,    className: 'bg-[#E9EDF5] text-unknown' },
  DENIED:         { label: 'Denied',           icon: <XCircle size={13} />,       className: 'bg-[#FDEBE6] text-danger'  },
  CREATED:        { label: 'Created',          icon: <Clock size={13} />,         className: 'bg-[#E9EDF5] text-unknown' },
  RETRY_ALLOWED:  { label: 'Retry allowed',    icon: <AlertTriangle size={13} />, className: 'bg-[#FFF4D6] text-warning' },
  REFUND_PENDING: { label: 'Refund requested', icon: <Clock size={13} />,         className: 'bg-[#FFF4D6] text-warning' },
  REFUNDED:       { label: 'Refunded',         icon: <CheckCircle size={13} />,   className: 'bg-[#E4F5EB] text-success' },
}

export function StatusBadge({ status, onDark }: { status: string; onDark?: boolean }) {
  const cfg = STATE_MAP[status] ?? { label: status, icon: <HelpCircle size={13} />, className: 'bg-[#E9EDF5] text-unknown' }
  return (
    <span
      className={`inline-flex items-center gap-1.5 whitespace-nowrap rounded-full px-2.5 py-1 text-[12px] font-bold ${
        onDark ? 'bg-white text-navy' : cfg.className
      }`}
    >
      {cfg.icon}
      {cfg.label}
    </span>
  )
}
