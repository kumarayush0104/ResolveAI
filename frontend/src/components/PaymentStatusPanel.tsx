import React from 'react'
import { CheckCircle2, AlertTriangle, Clock, XCircle, HelpCircle, RefreshCw, ShieldAlert } from 'lucide-react'
import { Button } from './Button'

export interface StatusSource {
  source: string
  ok: boolean
  normalized: string
  raw_status?: string | null
  detail?: string
  resource_id?: string | null
  availability?: string
  authoritative?: boolean
}

export interface StatusReport {
  consensus: string
  agrees: boolean
  sources: StatusSource[]
  conflicts: string[]
  notes: string[]
  checked_at: string
  reachable: boolean
}

const LABELS: Record<string, { name: string; sub: string }> = {
  ORDERS_API: { name: 'Orders API', sub: 'GET /v2/checkout/orders' },
  PAYMENTS_API: { name: 'Payments API', sub: 'GET /v2/payments/captures' },
  TRANSACTION_SEARCH: { name: 'Transaction Search', sub: 'GET /v1/reporting/transactions' },
  WEBHOOKS: { name: 'Webhooks', sub: 'Verified events, context only' },
}

const TONE: Record<string, { icon: React.ReactNode; cls: string }> = {
  COMPLETED: { icon: <CheckCircle2 size={13} />, cls: 'bg-[#E4F5EB] text-success' },
  PENDING: { icon: <Clock size={13} />, cls: 'bg-[#FFF4D6] text-warning' },
  DENIED: { icon: <XCircle size={13} />, cls: 'bg-[#FDEBE6] text-danger' },
  REVERSED: { icon: <AlertTriangle size={13} />, cls: 'bg-[#FDEBE6] text-danger' },
  UNKNOWN: { icon: <HelpCircle size={13} />, cls: 'bg-[#E9EDF5] text-unknown' },
}

function sourceLabel(s: StatusSource): string {
  if (s.ok) return s.raw_status || s.normalized
  if (s.availability === 'not_enabled') return 'Not enabled'
  if (s.availability === 'not_indexed_yet') return 'Not listed yet'
  if (s.availability === 'not_found') return 'Not found'
  return 'No answer'
}

export function PaymentStatusPanel({
  report,
  checking,
  onCheck,
}: {
  report?: StatusReport | null
  checking: boolean
  onCheck: () => void
}) {
  const conflict = report?.consensus === 'CONFLICT' || (report?.conflicts?.length ?? 0) > 0

  return (
    <div>
      <div className="mb-3">
        <h2 className="text-[15px] font-extrabold text-navy">Payment status check</h2>
        <p className="mt-0.5 text-[12px] leading-snug text-muted">
          We ask PayPal three ways. Only verified PayPal responses count.
        </p>
      </div>

      {!report ? (
        <p className="rounded-2xl bg-mist p-3.5 text-[12.5px] text-muted">No check has run yet.</p>
      ) : (
        <>
          <div
            className={`mb-3 flex items-start gap-2 rounded-2xl px-3 py-2.5 text-[12.5px] font-bold leading-snug ${
              conflict
                ? 'bg-[#FDEBE6] text-danger'
                : report.reachable
                ? 'bg-[#E4F5EB] text-success'
                : 'bg-[#E9EDF5] text-unknown'
            }`}
          >
            {conflict ? (
              <ShieldAlert size={16} className="mt-0.5 shrink-0" />
            ) : report.reachable ? (
              <CheckCircle2 size={16} className="mt-0.5 shrink-0" />
            ) : (
              <HelpCircle size={16} className="mt-0.5 shrink-0" />
            )}
            <span>
              {conflict
                ? 'Sources disagree. Retry, refund and fulfillment stay locked until this is resolved.'
                : report.reachable
                ? `All reachable sources agree: ${report.consensus}.`
                : 'PayPal couldn’t be reached. The outcome is unknown, not failed.'}
            </span>
          </div>

          <ul className="space-y-2">
            {report.sources.map((s) => {
              const meta = LABELS[s.source] ?? { name: s.source, sub: '' }
              const tone = TONE[s.ok ? s.normalized : 'UNKNOWN'] ?? TONE.UNKNOWN
              return (
                <li key={s.source} className="flex items-start justify-between gap-2 rounded-2xl bg-mist p-3">
                  <div className="min-w-0">
                    <div className="text-[13px] font-bold text-navy">{meta.name}</div>
                    <div className="break-all font-mono text-[10.5px] text-muted">{meta.sub}</div>
                    {s.detail && <div className="mt-1 text-[11.5px] leading-snug text-muted">{s.detail}</div>}
                  </div>
                  <span className={`inline-flex shrink-0 items-center gap-1 rounded-full px-2.5 py-1 text-[11.5px] font-bold ${tone.cls}`}>
                    {tone.icon}
                    {sourceLabel(s)}
                  </span>
                </li>
              )
            })}
          </ul>

          {report.conflicts.map((c, i) => (
            <p key={i} className="mt-2.5 text-[12px] leading-snug text-danger">{c}</p>
          ))}
          {report.notes.map((n, i) => (
            <p key={i} className="mt-2 text-[12px] leading-snug text-muted">{n}</p>
          ))}
          <p className="mt-2.5 text-[11px] text-muted">Checked {new Date(report.checked_at).toLocaleTimeString()}</p>
        </>
      )}

      <Button variant="outline" className="mt-3 w-full" onClick={onCheck} loading={checking}>
        <RefreshCw size={15} />
        Check PayPal now
      </Button>
    </div>
  )
}
