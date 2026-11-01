import React, { useState, useEffect, useCallback } from 'react'
import { useParams, useNavigate, Link } from 'react-router-dom'
import { AnimatePresence } from 'framer-motion'
import confetti from 'canvas-confetti'
import {
  Shield, AlertTriangle, Send, Sparkles, RefreshCw, RotateCcw, CreditCard, Lock,
  FlaskConical, ChevronLeft, ChevronRight, ShieldAlert,
} from 'lucide-react'

import { api, streamInvestigation } from '../lib/api'
import { useCaseStream } from '../lib/useCaseStream'
import { StatusBadge } from '../components/StatusBadge'
import { Button } from '../components/Button'
import { Card } from '../components/Card'
import { Skeleton } from '../components/Skeleton'
import { Sheet } from '../components/Sheet'
import { SimulationBanner } from '../components/SimulationBanner'
import { StateMachineViz } from '../components/StateMachineViz'
import { EvidenceTimeline, TimelineEvent } from '../components/EvidenceTimeline'
import { PaymentStatusPanel } from '../components/PaymentStatusPanel'
import { StepTracker } from '../components/StepTracker'
import { LabDrawer } from './Lab'
import { useToast } from '../components/Toast'

interface ToolCallChip {
  id: string
  name: string
  args: any
  status: 'running' | 'done' | 'error'
  result?: any
  ms?: number
}

interface BlockedPolicyModal {
  action: string
  rule_id: string
  reason: string
}

function SectionTitle({ icon, children, aside }: { icon: React.ReactNode; children: React.ReactNode; aside?: React.ReactNode }) {
  return (
    <div className="mb-3 flex items-center justify-between gap-2">
      <h2 className="flex items-center gap-2 text-[15px] font-extrabold text-navy">
        <span className="flex h-8 w-8 items-center justify-center rounded-full bg-cyan-soft text-cyan-deep">{icon}</span>
        {children}
      </h2>
      {aside}
    </div>
  )
}

export function CasePage() {
  const { id: caseId } = useParams<{ id: string }>()
  const nav = useNavigate()
  const { addToast } = useToast()

  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [caseData, setCaseData] = useState<any>(null)
  const [newMessage, setNewMessage] = useState('')
  const [sendingMessage, setSendingMessage] = useState(false)
  const [highlightedRef, setHighlightedRef] = useState<string | null>(null)

  // AI Investigator State
  const [isInvestigating, setIsInvestigating] = useState(false)
  const [toolChips, setToolChips] = useState<ToolCallChip[]>([])
  const [streamedSummary, setStreamedSummary] = useState('')
  const [finalResult, setFinalResult] = useState<any>(null)
  const [aiOverridden, setAiOverridden] = useState(false)

  // Policy Gate Modal & Shake Animation
  const [blockedModal, setBlockedModal] = useState<BlockedPolicyModal | null>(null)
  const [shakeGate, setShakeGate] = useState(false)

  // Fault-Injection Lab Drawer
  const [isLabOpen, setIsLabOpen] = useState(false)

  // Load initial case data
  const loadCase = useCallback(async () => {
    if (!caseId) return
    setError(null)
    try {
      const data = await api.getCase(caseId)
      setCaseData(data)
    } catch (err: any) {
      setError(err.message || 'Error loading case')
      addToast(`Error loading case: ${err.message}`, 'warning')
    } finally {
      setLoading(false)
    }
  }, [caseId, addToast])

  useEffect(() => {
    loadCase()
  }, [loadCase])

  // Fire confetti on COMPLETED (if not reduced motion)
  const triggerConfetti = useCallback(() => {
    const prefersReducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches
    if (!prefersReducedMotion) {
      confetti({
        particleCount: 80,
        spread: 60,
        origin: { y: 0.6 },
        colors: ['#0396D8', '#FFC439', '#0A2A66'],
      })
    }
  }, [])

  // Handle SSE live stream events
  const handleRealtimeEvent = useCallback(
    (event: any) => {
      console.log('Realtime event received:', event)

      if (event.type === 'action_approved' || event.type === 'investigation_completed' || event.type === 'reconciliation_update') {
        loadCase()
        if (event.state === 'COMPLETED' || event.new_state === 'COMPLETED') {
          triggerConfetti()
          addToast('Payment state transitioned to COMPLETED!', 'success')
        }
      } else if (event.type === 'new_message') {
        loadCase()
        addToast(`New message from ${event.sender}`, 'info')
      } else if (event.type === 'delayed_event_delivered' || event.type === 'simulated_webhook') {
        loadCase()
        addToast(`Simulated event delivered: ${event.event_type}`, 'warning')
      }
    },
    [loadCase, triggerConfetti, addToast]
  )

  useCaseStream(caseId, handleRealtimeEvent)

  // Trigger AI Investigation
  const handleStartInvestigation = async () => {
    if (!caseId || isInvestigating) return
    setIsInvestigating(true)
    setToolChips([])
    setStreamedSummary('')
    setFinalResult(null)
    setAiOverridden(false)

    try {
      await streamInvestigation(
        caseId,
        (sseEvent) => {
          if (sseEvent.type === 'tool_call') {
            setToolChips((prev) => [
              ...prev,
              {
                id: `${sseEvent.name}-${Date.now()}`,
                name: sseEvent.name,
                args: sseEvent.args,
                status: 'running',
              },
            ])
          } else if (sseEvent.type === 'tool_result') {
            setToolChips((prev) =>
              prev.map((c) =>
                c.name === sseEvent.name && c.status === 'running'
                  ? { ...c, status: 'done', result: sseEvent.result, ms: sseEvent.ms }
                  : c
              )
            )
          } else if (sseEvent.type === 'summary_delta') {
            setStreamedSummary((prev) => prev + sseEvent.text)
          } else if (sseEvent.type === 'final') {
            setFinalResult(sseEvent.result)
            loadCase()
          }
        },
        () => {
          setIsInvestigating(false)
          loadCase()
          addToast('Investigation finished with policy evaluation.', 'success')
        },
        (err) => {
          setIsInvestigating(false)
          addToast(`Investigation error: ${err.message}`, 'warning')
        }
      )
    } catch (err: any) {
      setIsInvestigating(false)
      addToast(`Investigation failed to start: ${err.message}`, 'warning')
    }
  }

  // Send message
  const handleSendMessage = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!newMessage.trim() || !caseId || sendingMessage) return

    setSendingMessage(true)
    try {
      await api.addMessage(caseId, newMessage.trim())
      setNewMessage('')
      loadCase()
      addToast('Message posted (sanitized as untrusted text).', 'success')
    } catch (err: any) {
      addToast(`Failed to post message: ${err.message}`, 'warning')
    } finally {
      setSendingMessage(false)
    }
  }

  // "Check PayPal now": real Orders API + Payments API + Transaction Search check. Read-only, always allowed.
  const [checking, setChecking] = useState(false)
  const handleCheckNow = async () => {
    if (!caseId) return
    setChecking(true)
    try {
      const out = await api.approveAction(caseId, 'RECONCILE', 'Checked from Case Page UI')
      addToast(
        out.state_changed ? `PayPal says ${out.state}. Case updated.` : 'Checked PayPal. Nothing has changed.',
        out.state_changed ? 'success' : 'info',
      )
      await loadCase()
    } catch (err: any) {
      addToast(`Couldn’t check PayPal: ${err.message}`, 'warning')
    } finally {
      setChecking(false)
    }
  }

  // Handle Action Click (e.g., RETRY, REFUND, RECONCILE)
  const handleActionClick = async (action: string) => {
    if (!caseData || !caseId) return
    if (action === 'RECONCILE') return handleCheckNow()

    const isPermitted = caseData.permitted_actions?.includes(action)

    if (!isPermitted) {
      // Find matching blocked action rule
      const blocked = caseData.policy_decision?.blocked_actions?.find(
        (b: any) => b.action === action
      )
      setBlockedModal({
        action,
        rule_id: blocked?.rule_id || 'R03_UNKNOWN_FAILS_CLOSED',
        reason: blocked?.reason || `Action '${action}' is strictly blocked by the deterministic policy engine.`,
      })
      setShakeGate(true)
      setTimeout(() => setShakeGate(false), 500)
      return
    }

    try {
      await api.approveAction(caseId, action, `Approved from Case Page UI`)
      addToast(`Action ${action} approved and submitted.`, 'success')
      loadCase()
    } catch (err: any) {
      addToast(`Action execution failed: ${err.message}`, 'warning')
    }
  }

  if (loading) {
    return (
      <div className="space-y-3 px-5 pt-2">
        <Skeleton className="h-40 w-full" />
        <Skeleton className="h-14 w-full" />
        <Skeleton className="h-48 w-full" />
      </div>
    )
  }

  if (error || !caseData) {
    return (
      <div className="mx-auto mt-16 space-y-4 px-8 text-center">
        <span className="mx-auto flex h-16 w-16 items-center justify-center rounded-full bg-[#FFF4D6] text-warning">
          <AlertTriangle size={30} />
        </span>
        <h2 className="text-[20px] font-extrabold text-navy">{error ? 'Couldn’t load this case' : 'Case not found'}</h2>
        <p className="text-[13px] text-muted">{error || 'We couldn’t find the case you asked for.'}</p>
        <div className="flex items-center justify-center gap-2.5">
          <Button
            variant="outline"
            onClick={() => {
              setLoading(true)
              setError(null)
              loadCase()
            }}
          >
            <RotateCcw size={14} /> Try again
          </Button>
          <Button onClick={() => nav('/')}>Go home</Button>
        </div>
      </div>
    )
  }

  const isSimulated = caseData.events?.some((e: any) => e.is_simulated)
  const currentState = caseData.current_policy_state || caseData.status
  const permittedActions: string[] = caseData.permitted_actions || []
  const retryOk = permittedActions.includes('RETRY') || permittedActions.includes('ALLOW_RETRY')
  const refundOk = permittedActions.includes('REFUND')
  const order = caseData.evidence_bundle?.order

  return (
    <div className="space-y-4 px-5 pb-8 pt-1">
      <Link to="/console" className="-ml-1 inline-flex items-center gap-0.5 py-1 pr-2 text-[14px] font-bold text-cyan-deep">
        <ChevronLeft size={18} strokeWidth={2.5} /> Cases
      </Link>

      {isSimulated && (
        <SimulationBanner message="Simulation: this case includes events injected by the fault lab." />
      )}

      {/* Case summary, styled like a wallet card */}
      <section className="rounded-[28px] bg-gradient-to-br from-cyan via-[#0A74C8] to-navy p-5 text-white shadow-card">
        <div className="flex items-start justify-between gap-3">
          <div className="min-w-0">
            <p className="text-[12.5px] font-semibold text-white/75">Case #{caseData.id.slice(0, 8)}</p>
            <p className="mt-1 text-[38px] font-extrabold leading-none tracking-[-0.03em] tabular-nums">
              {order?.amount ? `$${order.amount}` : '$25.00'}
              <span className="ml-1.5 text-[14px] font-bold text-white/75">{order?.currency ?? 'USD'}</span>
            </p>
          </div>
          <StatusBadge status={currentState} onDark />
        </div>
        <p className="mt-4 truncate rounded-xl bg-white/12 px-3 py-2 font-mono text-[11.5px] text-white/90">
          PayPal order {caseData.order_id}
        </p>
        <div className="mt-4 grid grid-cols-5 gap-2">
          <Button variant="white" className="col-span-3 !text-[13.5px]" onClick={handleStartInvestigation} loading={isInvestigating}>
            <Sparkles size={16} className="text-cyan" />
            {isInvestigating ? 'Investigating…' : 'Run AI check'}
          </Button>
          <button
            onClick={() => setIsLabOpen(true)}
            className="col-span-2 flex min-h-[50px] items-center justify-center gap-1.5 rounded-full bg-white/15 text-[13.5px] font-bold text-white ring-1 ring-white/30"
          >
            <FlaskConical size={15} /> Fault lab
          </button>
        </div>
      </section>

      <StepTracker
        steps={['Evidence', 'Verify', 'Act']}
        current={finalResult || caseData.latest_agent_run ? 2 : caseData.evidence_bundle?.status_report?.reachable ? 1 : 0}
      />

      {/* Payment status check across PayPal's APIs */}
      <Card>
        <PaymentStatusPanel
          report={caseData.evidence_bundle?.status_report}
          checking={checking}
          onCheck={handleCheckNow}
        />
      </Card>

      {/* Where the payment stands */}
      <Card>
        <SectionTitle icon={<Shield size={16} />}>Where it stands</SectionTitle>
        <StateMachineViz currentState={currentState} blockedRules={caseData.policy_decision?.blocked_actions} />
      </Card>

      {/* Actions, gated by the policy engine */}
      <Card className={shakeGate ? 'ring-2 ring-danger/40' : ''}>
        <SectionTitle icon={<Lock size={16} />}>What you can do</SectionTitle>
        <p className="mb-3 text-[12.5px] leading-snug text-muted">
          Only actions that PayPal’s records allow are unlocked. Tap a locked one to see why.
        </p>
        <div className="space-y-2.5">
          <Button
            className="w-full"
            variant={retryOk ? 'primary' : 'outline'}
            locked={!retryOk}
            onClick={() => handleActionClick('RETRY')}
          >
            {retryOk ? <RotateCcw size={16} /> : <Lock size={15} />}
            Retry payment
          </Button>
          <Button
            className="w-full"
            variant={refundOk ? 'primary' : 'outline'}
            locked={!refundOk}
            onClick={() => handleActionClick('REFUND')}
          >
            {refundOk ? <CreditCard size={16} /> : <Lock size={15} />}
            Request refund
          </Button>
          <Button className="w-full" variant="outline" onClick={() => handleActionClick('RECONCILE')}>
            <RefreshCw size={15} /> Check PayPal again
          </Button>
        </div>
        <p className="mt-3 flex items-start gap-1.5 border-t border-line pt-3 text-[11.5px] leading-snug text-muted">
          <Lock size={12} className="mt-0.5 shrink-0 text-navy" />
          A timeout is never treated as a failure. A retry needs a verified failure from PayPal.
        </p>
      </Card>

      {/* AI investigator */}
      <Card>
        <SectionTitle
          icon={<Sparkles size={16} />}
          aside={
            isInvestigating ? (
              <span className="flex items-center gap-1.5 text-[11.5px] font-bold text-cyan-deep">
                <span className="h-2 w-2 animate-ping rounded-full bg-cyan" /> Checking PayPal
              </span>
            ) : finalResult ? (
              <span className="rounded-full bg-[#E4F5EB] px-2.5 py-1 text-[11.5px] font-bold text-success">Ready</span>
            ) : null
          }
        >
          AI investigator
        </SectionTitle>

        {!isInvestigating && !streamedSummary && !finalResult && !caseData.latest_agent_run && (
          <p className="rounded-2xl bg-mist p-3.5 text-[12.5px] leading-relaxed text-muted">
            Tap <strong className="text-navy">Run AI check</strong> and the investigator reads the PayPal records and
            explains what happened in plain language.
          </p>
        )}

        {isInvestigating && !streamedSummary && toolChips.length === 0 && (
          <div className="space-y-2.5 py-2">
            <div className="h-3.5 w-3/4 animate-pulse rounded bg-[#DCE7F1]" />
            <div className="h-3.5 w-5/6 animate-pulse rounded bg-[#DCE7F1]" />
            <div className="h-3.5 w-1/2 animate-pulse rounded bg-[#DCE7F1]" />
          </div>
        )}

        {toolChips.length > 0 && (
          <div className="mb-3">
            <p className="mb-1.5 text-[11.5px] font-bold text-muted">Read-only PayPal lookups</p>
            <div className="flex flex-wrap gap-1.5">
              {toolChips.map((chip) => (
                <span
                  key={chip.id}
                  className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 font-mono text-[11px] font-medium ${
                    chip.status === 'running'
                      ? 'animate-pulse bg-cyan-soft text-cyan-deep'
                      : chip.status === 'done'
                      ? 'bg-[#E4F5EB] text-success'
                      : 'bg-[#FDEBE6] text-danger'
                  }`}
                >
                  {chip.name}
                  {chip.status === 'running' && (
                    <span className="h-2.5 w-2.5 animate-spin rounded-full border border-current border-t-transparent" />
                  )}
                  {chip.status === 'done' && <span>ok{chip.ms ? ` · ${chip.ms}ms` : ''}</span>}
                </span>
              ))}
            </div>
          </div>
        )}

        {(streamedSummary || finalResult?.summary || caseData.latest_agent_run) && (
          <div className="space-y-3">
            <div className="rounded-2xl bg-mist p-3.5 text-[13px] leading-relaxed text-ink">
              <p className="font-medium">{streamedSummary || finalResult?.summary || caseData.latest_agent_run}</p>

              {(finalResult?.evidence_refs || ['api_snapshot.capture_status']).length > 0 && (
                <div className="mt-3 flex flex-wrap items-center gap-1.5 border-t border-line pt-3">
                  <span className="text-[11.5px] font-bold text-muted">Evidence</span>
                  {(finalResult?.evidence_refs || ['api_snapshot.capture_status']).map((refStr: string, idx: number) => (
                    <button
                      key={idx}
                      onClick={() => setHighlightedRef((h) => (h === refStr ? null : refStr))}
                      className={`rounded-full px-2 py-0.5 font-mono text-[11px] ${
                        highlightedRef === refStr ? 'bg-cyan text-white' : 'bg-cyan-soft text-cyan-deep'
                      }`}
                    >
                      {refStr}
                    </button>
                  ))}
                </div>
              )}
            </div>

            {finalResult && (
              <div className="space-y-2">
                <div className="rounded-2xl bg-cyan-soft p-3.5 text-[12.5px]">
                  <strong className="mb-0.5 block text-navy">For the buyer</strong>
                  <p className="leading-snug text-ink/80">{finalResult.buyer_message}</p>
                </div>
                <div className="rounded-2xl bg-mist p-3.5 text-[12.5px]">
                  <strong className="mb-0.5 block text-navy">For the seller</strong>
                  <p className="leading-snug text-ink/80">{finalResult.seller_message}</p>
                </div>
              </div>
            )}

            {finalResult?.unknowns?.length > 0 && (
              <div className="rounded-2xl border-2 border-dashed border-[#C3D0E0] p-3.5 text-[12.5px]">
                <strong className="mb-1 block text-muted">Still unknown</strong>
                <ul className="list-inside list-disc space-y-0.5 text-muted">
                  {finalResult.unknowns.map((u: string, idx: number) => (
                    <li key={idx}>{u}</li>
                  ))}
                </ul>
              </div>
            )}
          </div>
        )}

        {aiOverridden && (
          <div className="mt-3 flex items-center gap-2 rounded-2xl bg-[#FFF4D6] p-3 text-[12px] font-semibold text-warning">
            <Shield size={14} /> The policy gate adjusted the AI’s recommendation to keep this safe.
          </div>
        )}
      </Card>

      {/* Evidence timeline */}
      <Card>
        <SectionTitle
          icon={<Shield size={16} />}
          aside={<span className="text-[12px] font-semibold text-muted">{caseData.events?.length || 0} events</span>}
        >
          Evidence timeline
        </SectionTitle>
        <EvidenceTimeline events={caseData.events as TimelineEvent[]} highlightedRef={highlightedRef} />
      </Card>

      {/* Notes */}
      <Card>
        <h2 className="text-[15px] font-extrabold text-navy">Case notes</h2>
        <p className="mb-3 mt-0.5 text-[12px] leading-snug text-muted">
          Free text from people. It’s sanitized and never changes a policy decision.
        </p>

        <div className="mb-3 space-y-2">
          {caseData.events
            ?.filter((e: any) => e.source === 'USER' && e.event_type === 'CASE_MESSAGE')
            .map((msgEv: any) => (
              <div key={msgEv.id} className="rounded-2xl bg-cyan-soft p-3 text-[12.5px]">
                <p className="whitespace-pre-wrap text-ink">{msgEv.description}</p>
                <span className="mt-1 block font-mono text-[10.5px] text-muted">
                  {new Date(msgEv.created_at).toLocaleTimeString()}
                </span>
              </div>
            ))}
        </div>

        <form onSubmit={handleSendMessage} className="flex items-end gap-2">
          <textarea
            value={newMessage}
            onChange={(e) => setNewMessage(e.target.value)}
            placeholder="Add a note…"
            aria-label="Add a note to this case"
            maxLength={1000}
            rows={2}
            className="min-h-[50px] flex-1 resize-none rounded-2xl border border-line bg-mist p-3 text-[13px] outline-none focus:border-cyan"
          />
          <button
            type="submit"
            disabled={!newMessage.trim() || sendingMessage}
            aria-label="Send note"
            className="flex h-[50px] w-[50px] shrink-0 items-center justify-center rounded-full bg-cyan text-white disabled:opacity-40"
          >
            {sendingMessage ? (
              <span className="h-4 w-4 animate-spin rounded-full border-2 border-white border-t-transparent" />
            ) : (
              <Send size={18} />
            )}
          </button>
        </form>
      </Card>

      {/* Blocked action sheet */}
      <AnimatePresence>
        {blockedModal && (
          <Sheet
            onClose={() => setBlockedModal(null)}
            title={
              <span className="flex items-center gap-2 text-danger">
                <ShieldAlert size={18} /> Action locked
              </span>
            }
          >
            <div className="space-y-3 pt-1">
              <p className="rounded-xl bg-[#FDEBE6] px-3 py-2 font-mono text-[12px] font-semibold text-danger">
                {blockedModal.rule_id}
              </p>
              <p className="text-[14px] leading-relaxed text-ink">{blockedModal.reason}</p>
              <p className="rounded-2xl bg-mist p-3 text-[12px] leading-relaxed text-muted">
                ResolveAI blocks duplicate charges and invalid state changes until PayPal has confirmed a final outcome.
              </p>
              <Button className="w-full" onClick={() => setBlockedModal(null)}>Got it</Button>
            </div>
          </Sheet>
        )}
      </AnimatePresence>

      {/* Fault lab */}
      <AnimatePresence>
        {isLabOpen && caseData && (
          <LabDrawer orderId={caseData.order_id} caseId={caseData.id} onClose={() => setIsLabOpen(false)} />
        )}
      </AnimatePresence>
    </div>
  )
}
