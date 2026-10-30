import React from 'react'
import { CheckCircle, Clock, AlertTriangle, XCircle, HelpCircle } from 'lucide-react'

const STATE_MAP: Record<string, { label: string; icon: React.ReactNode; className: string }> = {
  COMPLETED:      { label: 'Completed',        icon: <CheckCircle size={14} />,   className: 'bg-[#E6F4EC] text-success' },
  PENDING:        { label: 'Pending',          icon: <Clock size={14} />,         className: 'bg-[#FFF4D6] text-warning' },
  UNKNOWN:        { label: 'Unknown',          icon: <HelpCircle size={14} />,    className: 'bg-[#E9EDF5] text-unknown' },
  DENIED:         { label: 'Denied',           icon: <XCircle size={14} />,       className: 'bg-[#FDEBE6] text-danger'  },
  CREATED:        { label: 'Created',          icon: <Clock size={14} />,         className: 'bg-[#E9EDF5] text-unknown' },
  RETRY_ALLOWED:  { label: 'Retry Allowed',    icon: <AlertTriangle size={14} />, className: 'bg-[#FFF4D6] text-warning' },
  REFUND_PENDING: { label: 'Refund Requested', icon: <Clock size={14} />,         className: 'bg-[#FFF4D6] text-warning' },
  REFUNDED:       { label: 'Refunded',         icon: <CheckCircle size={14} />,   className: 'bg-[#E6F4EC] text-success' },
}

export function StatusBadge({ status }: { status: string }) {
  const cfg = STATE_MAP[status] ?? { label: status, icon: <HelpCircle size={14} />, className: 'bg-[#E9EDF5] text-unknown' }
  return (
    <span className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-semibold ${cfg.className}`}>
      {cfg.icon}
      {cfg.label}
    </span>
  )
}
