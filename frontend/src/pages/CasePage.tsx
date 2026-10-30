import React, { useState, useEffect, useRef, useCallback } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { motion, AnimatePresence } from 'framer-motion'
import confetti from 'canvas-confetti'
import {
  Shield,
  AlertTriangle,
  Send,
  Sparkles,
  RefreshCw,
  RotateCcw,
  CreditCard,
  Lock,
  X,
  ExternalLink,
  FlaskConical,
  CheckCircle2,
} from 'lucide-react'

import { api, streamInvestigation } from '../lib/api'
import { useCaseStream } from '../lib/useCaseStream'
import { StatusBadge } from '../components/StatusBadge'
import { PillButton } from '../components/PillButton'
import { Card } from '../components/Card'
import { Skeleton } from '../components/Skeleton'
import { SimulationBanner } from '../components/SimulationBanner'
import { StateMachineViz } from '../components/StateMachineViz'
import { EvidenceTimeline, TimelineEvent } from '../components/EvidenceTimeline'
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
        colors: ['#0070E0', '#FFC439'],
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

  // Handle Action Click (e.g., RETRY, REFUND, RECONCILE)
  const handleActionClick = async (action: string) => {
    if (!caseData || !caseId) return

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
      <div className="max-w-5xl mx-auto px-4 sm:px-6 lg:px-8 py-6 space-y-6">
        <Skeleton className="h-10 w-1/3" />
        <Skeleton className="h-64 w-full" />
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          <Skeleton className="h-80 w-full" />
          <Skeleton className="h-80 w-full" />
        </div>
      </div>
    )
  }

  if (error || !caseData) {
    return (
      <div className="max-w-md mx-auto mt-20 text-center space-y-4 px-4">
        <AlertTriangle size={36} className="text-warning mx-auto" />
        <h2 className="text-xl font-bold text-pp-blue-dark">{error ? 'Failed to Load Case' : 'Case Not Found'}</h2>
        <p className="text-sm text-ink-soft">
          {error || "We couldn't locate the dispute or investigation case you requested."}
        </p>
        <div className="flex items-center justify-center gap-3">
          <PillButton
            variant="outline"
            onClick={() => {
              setLoading(true)
              setError(null)
              loadCase()
            }}
          >
            <RotateCcw size={14} />
            <span>Retry</span>
          </PillButton>
          <PillButton variant="blue" onClick={() => nav('/')}>
            Back to Home
          </PillButton>
        </div>
      </div>
    )
  }

  const isSimulated = caseData.events?.some((e: any) => e.is_simulated)
  const currentState = caseData.current_policy_state || caseData.status
  const permittedActions = caseData.permitted_actions || []

  return (
    <div className="min-h-screen bg-surface pb-24">
      {/* Simulation Banner if simulated events exist */}
      {isSimulated && (
        <div className="bg-white border-b border-line px-4 sm:px-6 lg:px-8 py-2.5">
          <div className="max-w-5xl mx-auto">
            <SimulationBanner message="SIMULATION — This case contains simulated events injected via the Fault-Injection Lab." />
          </div>
        </div>
      )}

      {/* Header Info Bar */}
      <section className="bg-white border-b border-line px-4 sm:px-6 lg:px-8 py-6 shadow-sm">
        <div className="max-w-5xl mx-auto flex flex-wrap items-center justify-between gap-4">
          <div>
            <div className="flex items-center gap-3">
              <h1 className="text-2xl font-bold text-pp-blue-dark">
                Dispute Case #{caseData.id.slice(0, 8)}
              </h1>
              <StatusBadge status={currentState} />
            </div>
            <p className="text-xs text-ink-soft mt-1 font-mono">
              PayPal Order ID: <span className="font-semibold text-pp-blue">{caseData.order_id}</span>
              {caseData.evidence_bundle?.order?.amount && (
                <span className="ml-3 font-sans">
                  · Amount: <strong className="text-ink">${caseData.evidence_bundle.order.amount} {caseData.evidence_bundle.order.currency}</strong>
                </span>
              )}
            </p>
          </div>

          <div className="flex items-center gap-3">
            <PillButton
              variant="outline"
              onClick={() => setIsLabOpen(true)}
              className="text-xs border-pp-gold text-[#2C2E2F] hover:bg-pp-gold/10"
            >
              <FlaskConical size={14} className="text-pp-gold" />
              <span>Fault-Injection Lab</span>
            </PillButton>
            <PillButton
              variant="gold"
              onClick={handleStartInvestigation}
              loading={isInvestigating}
            >
              <Sparkles size={16} />
              <span>{isInvestigating ? 'Investigating...' : 'Run AI Investigation'}</span>
            </PillButton>
          </div>
        </div>
      </section>

      {/* Main Workspace Grid */}
      <main className="max-w-5xl mx-auto px-4 sm:px-6 lg:px-8 py-6 space-y-6">
        {/* 1. State Machine Visual Diagram */}
        <Card className="border border-line shadow-card overflow-hidden">
          <div className="flex items-center justify-between mb-2">
            <div className="flex items-center gap-2">
              <Shield size={18} className="text-pp-blue" />
              <h2 className="font-bold text-pp-blue-dark text-base">
                Authoritative State Machine & Policy Gates
              </h2>
            </div>
            <span className="text-xs font-mono text-ink-soft">
              Active State: <strong className="text-pp-blue-dark">{currentState}</strong>
            </span>
          </div>

          <StateMachineViz
            currentState={currentState}
            blockedRules={caseData.policy_decision?.blocked_actions}
          />
        </Card>

        {/* 2. Middle Row: AI Investigator & Allowed Policy Actions */}
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* AI Investigator Panel (2 cols on large screen) */}
          <div className="lg:col-span-2 space-y-6">
            <Card className="border border-line h-full flex flex-col justify-between">
              <div>
                <div className="flex items-center justify-between mb-4 pb-3 border-b border-line">
                  <div className="flex items-center gap-2">
                    <Sparkles size={18} className="text-pp-gold" />
                    <h3 className="font-bold text-pp-blue-dark text-base">
                      AI Investigator & Grounded Evidence
                    </h3>
                  </div>
                  {isInvestigating ? (
                    <span className="inline-flex items-center gap-1.5 text-xs text-pp-blue font-semibold">
                      <span className="w-2 h-2 rounded-full bg-pp-blue animate-ping" />
                      Analyzing Live PayPal APIs...
                    </span>
                  ) : finalResult ? (
                    <span className="text-xs font-semibold text-success bg-[#E6F4EC] px-2.5 py-0.5 rounded-full">
                      ✓ Diagnosis Ready
                    </span>
                  ) : (
                    <span className="text-xs text-ink-soft">Click "Run AI Investigation" to diagnose</span>
                  )}
                </div>

                {/* Shimmer loading state */}
                {isInvestigating && !streamedSummary && toolChips.length === 0 && (
                  <div className="py-8 space-y-3">
                    <div className="h-4 bg-gray-200 rounded animate-pulse w-3/4" />
                    <div className="h-4 bg-gray-200 rounded animate-pulse w-5/6" />
                    <div className="h-4 bg-gray-200 rounded animate-pulse w-1/2" />
                  </div>
                )}

                {/* Tool-call chips stream */}
                {toolChips.length > 0 && (
                  <div className="mb-4 space-y-2">
                    <p className="text-xs font-semibold text-ink-soft uppercase tracking-wider">
                      Authoritative Read-Only Tool Calls:
                    </p>
                    <div className="flex flex-wrap gap-2">
                      {toolChips.map((chip) => (
                        <span
                          key={chip.id}
                          className={`inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-mono font-medium border ${
                            chip.status === 'running'
                              ? 'bg-blue-50 border-pp-blue text-pp-blue animate-pulse'
                              : chip.status === 'done'
                              ? 'bg-[#E6F4EC] border-success text-success'
                              : 'bg-[#FDEBE6] border-danger text-danger'
                          }`}
                        >
                          <span>🔎 {chip.name}</span>
                          {chip.status === 'running' && (
                            <span className="w-2 h-2 border border-current border-t-transparent rounded-full animate-spin" />
                          )}
                          {chip.status === 'done' && (
                            <span>✓ 200 OK {chip.ms ? `· ${chip.ms}ms` : ''}</span>
                          )}
                        </span>
                      ))}
                    </div>
                  </div>
                )}

                {/* Typed Summary Output */}
                {(streamedSummary || finalResult?.summary || caseData.latest_agent_run) && (
                  <div className="space-y-4">
                    <div className="p-4 bg-surface rounded-xl border border-line text-sm text-ink leading-relaxed">
                      <p className="font-medium">
                        {streamedSummary || finalResult?.summary || caseData.latest_agent_run}
                      </p>

                      {/* Evidence Chips */}
                      {(finalResult?.evidence_refs || ['api_snapshot.capture_status']).length > 0 && (
                        <div className="mt-3 pt-3 border-t border-line/60 flex flex-wrap items-center gap-1.5">
                          <span className="text-[11px] text-ink-soft font-semibold">Evidence Cites:</span>
                          {(finalResult?.evidence_refs || ['api_snapshot.capture_status']).map(
                            (refStr: string, idx: number) => (
                              <button
                                key={idx}
                                onMouseEnter={() => setHighlightedRef(refStr)}
                                onMouseLeave={() => setHighlightedRef(null)}
                                className="px-2 py-0.5 rounded bg-pp-blue/10 hover:bg-pp-blue hover:text-white text-pp-blue text-[11px] font-mono transition-colors"
                              >
                                [{refStr}]
                              </button>
                            )
                          )}
                        </div>
                      )}
                    </div>

                    {/* Buyer & Seller Guidance Cards */}
                    {finalResult && (
                      <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                        <div className="p-3 bg-blue-50/50 rounded-xl border border-blue-100 text-xs">
                          <strong className="text-pp-blue-dark block mb-1">Buyer Guidance:</strong>
                          <p className="text-ink-soft">{finalResult.buyer_message}</p>
                        </div>
                        <div className="p-3 bg-surface rounded-xl border border-line text-xs">
                          <strong className="text-ink block mb-1">Seller Guidance:</strong>
                          <p className="text-ink-soft">{finalResult.seller_message}</p>
                        </div>
                      </div>
                    )}

                    {/* Unknowns warning */}
                    {finalResult?.unknowns?.length > 0 && (
                      <div className="p-3 rounded-xl border-2 border-dashed border-gray-300 bg-surface/50 text-xs">
                        <strong className="text-ink-soft block mb-1">What We Don't Know Yet:</strong>
                        <ul className="list-disc list-inside space-y-0.5 text-gray-500">
                          {finalResult.unknowns.map((u: string, idx: number) => (
                            <li key={idx}>{u}</li>
                          ))}
                        </ul>
                      </div>
                    )}
                  </div>
                )}
              </div>

              {/* Policy adjusted note */}
              {aiOverridden && (
                <div className="mt-4 p-3 bg-[#FFF4D6] rounded-xl text-xs text-warning font-medium flex items-center gap-2">
                  <Shield size={14} />
                  <span>Policy Gate adjusted AI recommendation to ensure mathematical safety.</span>
                </div>
              )}
            </Card>
          </div>

          {/* Allowed Actions & Policy Gate Card */}
          <div className="space-y-6">
            <Card
              className={`border border-line h-full flex flex-col justify-between transition-transform duration-200 ${
                shakeGate ? 'animate-bounce border-danger ring-2 ring-danger/20' : ''
              }`}
            >
              <div>
                <div className="flex items-center gap-2 mb-4 pb-3 border-b border-line">
                  <Shield size={18} className="text-pp-blue" />
                  <h3 className="font-bold text-pp-blue-dark text-base">Policy Actions</h3>
                </div>

                <p className="text-xs text-ink-soft mb-4">
                  Actions are permitted strictly according to verified PayPal evidence and rules R01–R09.
                </p>

                <div className="space-y-3">
                  {/* Action 1: Retry Payment */}
                  <div className="relative group">
                    <PillButton
                      variant={permittedActions.includes('RETRY') || permittedActions.includes('ALLOW_RETRY') ? 'gold' : 'outline'}
                      className="w-full text-xs"
                      onClick={() => handleActionClick('RETRY')}
                      disabled={!permittedActions.includes('RETRY') && !permittedActions.includes('ALLOW_RETRY')}
                    >
                      <RotateCcw size={14} />
                      <span>Retry Payment</span>
                    </PillButton>
                    {!permittedActions.includes('RETRY') && !permittedActions.includes('ALLOW_RETRY') && (
                      <span className="hidden group-hover:block absolute bottom-full left-1/2 -translate-x-1/2 mb-1 p-2 bg-ink text-white text-[11px] rounded-lg shadow-lg z-10 w-48 text-center pointer-events-none">
                        Blocked by policy: Cannot retry when original payment is completed or pending.
                      </span>
                    )}
                  </div>

                  {/* Action 2: Refund Payment */}
                  <div className="relative group">
                    <PillButton
                      variant={permittedActions.includes('REFUND') ? 'blue' : 'outline'}
                      className="w-full text-xs"
                      onClick={() => handleActionClick('REFUND')}
                      disabled={!permittedActions.includes('REFUND')}
                    >
                      <CreditCard size={14} />
                      <span>Request PayPal Refund</span>
                    </PillButton>
                    {!permittedActions.includes('REFUND') && (
                      <span className="hidden group-hover:block absolute bottom-full left-1/2 -translate-x-1/2 mb-1 p-2 bg-ink text-white text-[11px] rounded-lg shadow-lg z-10 w-48 text-center pointer-events-none">
                        Blocked by policy: Refund requires authoritative COMPLETED capture status.
                      </span>
                    )}
                  </div>

                  {/* Action 3: Reconcile with PayPal */}
                  <PillButton
                    variant="outline"
                    className="w-full text-xs"
                    onClick={() => handleActionClick('RECONCILE')}
                  >
                    <RefreshCw size={14} />
                    <span>Re-query PayPal Authoritative API</span>
                  </PillButton>
                </div>
              </div>

              {/* Policy Safety Invariant Note */}
              <div className="mt-6 pt-4 border-t border-line text-[11px] text-ink-soft flex items-start gap-1.5">
                <Lock size={12} className="text-pp-blue-dark mt-0.5 shrink-0" />
                <span>Fail-Closed Safety: Timeouts are never mapped to failure. Retries require verified terminal failure.</span>
              </div>
            </Card>
          </div>
        </div>

        {/* 3. Bottom Row: Evidence Timeline & Messages */}
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* Evidence Timeline (2 cols) */}
          <div className="lg:col-span-2">
            <Card className="border border-line">
              <div className="flex items-center justify-between mb-4 pb-3 border-b border-line">
                <div className="flex items-center gap-2">
                  <Shield size={18} className="text-pp-blue" />
                  <h3 className="font-bold text-pp-blue-dark text-base">Evidence Timeline</h3>
                </div>
                <span className="text-xs text-ink-soft">
                  {caseData.events?.length || 0} authoritative events
                </span>
              </div>

              <EvidenceTimeline
                events={caseData.events as TimelineEvent[]}
                highlightedRef={highlightedRef}
              />
            </Card>
          </div>

          {/* Context Messages Box (1 col) */}
          <div>
            <Card className="border border-line h-full flex flex-col justify-between">
              <div>
                <h3 className="font-bold text-pp-blue-dark text-base mb-1">Case Notes & Context</h3>
                <p className="text-[11px] text-ink-soft mb-4">
                  Untrusted user text — sanitized with boundary tags. Does not affect policy decisions.
                </p>

                <div className="max-h-72 overflow-y-auto space-y-3 mb-4 pr-1">
                  {caseData.events
                    ?.filter((e: any) => e.source === 'USER' && e.event_type === 'CASE_MESSAGE')
                    .map((msgEv: any) => (
                      <div key={msgEv.id} className="p-3 bg-surface rounded-xl text-xs border border-line">
                        <p className="text-ink whitespace-pre-wrap">{msgEv.description}</p>
                        <span className="text-[10px] text-ink-soft font-mono mt-1 block">
                          {new Date(msgEv.created_at).toLocaleTimeString()}
                        </span>
                      </div>
                    ))}
                </div>
              </div>

              <form onSubmit={handleSendMessage} className="space-y-2">
                <textarea
                  value={newMessage}
                  onChange={(e) => setNewMessage(e.target.value)}
                  placeholder="Add context note (max 1000 chars)..."
                  maxLength={1000}
                  rows={3}
                  className="w-full text-xs p-3 rounded-xl border border-line focus:ring-2 focus:ring-pp-blue outline-none resize-none"
                />
                <PillButton
                  type="submit"
                  variant="blue"
                  className="w-full text-xs"
                  loading={sendingMessage}
                  disabled={!newMessage.trim()}
                >
                  <Send size={13} />
                  <span>Send Context Note</span>
                </PillButton>
              </form>
            </Card>
          </div>
        </div>
      </main>

      {/* Blocked Policy Rule Modal */}
      <AnimatePresence>
        {blockedModal && (
          <div className="fixed inset-0 bg-black/50 backdrop-blur-sm z-50 flex items-center justify-center p-4">
            <motion.div
              initial={{ opacity: 0, scale: 0.9 }}
              animate={{ opacity: 1, scale: 1 }}
              exit={{ opacity: 0, scale: 0.9 }}
              className="bg-white rounded-2xl max-w-md w-full p-6 shadow-2xl border border-danger/30 space-y-4"
            >
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2 text-danger font-bold text-base">
                  <Shield size={20} />
                  <span>Action Blocked by Policy Gate</span>
                </div>
                <button
                  onClick={() => setBlockedModal(null)}
                  className="text-ink-soft hover:text-ink"
                >
                  <X size={18} />
                </button>
              </div>

              <div className="p-3 bg-[#FDEBE6] rounded-xl text-xs text-danger font-mono font-semibold">
                Rule ID: {blockedModal.rule_id}
              </div>

              <p className="text-sm text-ink leading-relaxed">
                {blockedModal.reason}
              </p>

              <div className="text-xs text-ink-soft bg-surface p-3 rounded-xl border border-line">
                ResolveAI prevents duplicate charging and illegal transitions by strictly requiring verified provider terminal records.
              </div>

              <PillButton
                variant="outline"
                className="w-full"
                onClick={() => setBlockedModal(null)}
              >
                Understood
              </PillButton>
            </motion.div>
          </div>
        )}
      </AnimatePresence>

      {/* Fault-Injection Lab Drawer */}
      <AnimatePresence>
        {isLabOpen && caseData && (
          <LabDrawer
            orderId={caseData.order_id}
            caseId={caseData.id}
            onClose={() => setIsLabOpen(false)}
          />
        )}
      </AnimatePresence>
    </div>
  )
}
