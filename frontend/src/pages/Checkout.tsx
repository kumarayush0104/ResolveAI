import React, { useEffect, useState, useRef } from 'react'
import { useNavigate } from 'react-router-dom'
import { CheckCircle2, AlertTriangle, ShoppingBag, ShieldCheck } from 'lucide-react'
import { ScreenHeader } from '../components/ScreenHeader'
import { StepTracker } from '../components/StepTracker'
import { PaymentStatusPanel, StatusReport } from '../components/PaymentStatusPanel'
import { api, PublicConfig } from '../lib/api'
import { Card } from '../components/Card'
import { Button } from '../components/Button'
import { useToast } from '../components/Toast'

declare global {
  interface Window {
    paypal?: any
  }
}

export function Checkout() {
  const [config, setConfig] = useState<PublicConfig | null>(null)
  const [configFailed, setConfigFailed] = useState(false)
  const [orderId, setOrderId] = useState<string | null>(null)
  const [captured, setCaptured] = useState(false)
  const [loading, setLoading] = useState(false)
  const [buttonsRendered, setButtonsRendered] = useState(false)
  const [statusReport, setStatusReport] = useState<StatusReport | null>(null)
  const [checking, setChecking] = useState(false)
  const buttonsRef = useRef<HTMLDivElement>(null)
  const nav = useNavigate()
  const { addToast } = useToast()

  useEffect(() => {
    api.getPublicConfig()
      .then(setConfig)
      .catch((err) => {
        console.error('Failed to load public config', err)
        setConfigFailed(true)
        addToast('Couldn’t load the PayPal sandbox settings. Check that the backend is running.', 'warning')
      })
  }, [])

  useEffect(() => {
    if (!config?.paypal_client_id || buttonsRendered) return

    const scriptId = 'paypal-js-sdk'
    if (document.getElementById(scriptId)) {
      renderButtons()
      return
    }

    const script = document.createElement('script')
    script.id = scriptId
   script.src = `https://www.paypal.com/sdk/js?client-id=${config.paypal_client_id}&currency=USD&intent=capture&disable-funding=card,credit,paylater`
    script.async = true
    script.onload = () => renderButtons()
    script.onerror = () => {
      setConfigFailed(true)
      addToast('Couldn’t load the PayPal button. Check your internet connection.', 'warning')
    }
    document.body.appendChild(script)
  }, [config])

  const renderButtons = () => {
    if (!window.paypal || !buttonsRef.current) return

    try {
      buttonsRef.current.innerHTML = ''
      window.paypal
        .Buttons({
          createOrder: async () => {
            setLoading(true)
            try {
              const res = await api.createOrder(25.0, 'USD')
              setOrderId(res.order_id)
              return res.order_id
            } catch (err: any) {
              addToast(`Couldn’t create the order: ${err.message}`, 'warning')
              throw err
            } finally {
              setLoading(false)
            }
          },
          onApprove: async (data: any) => {
            setLoading(true)
            try {
              const res = await api.captureOrder(data.orderID)
              setOrderId(data.orderID)
              if (res.status === 'COMPLETED') {
                setCaptured(true)
                addToast(
                  res.recovered
                    ? 'The confirmation was lost, but PayPal confirms your payment went through. You will not be charged again.'
                    : 'Payment captured in the PayPal sandbox.',
                  'success',
                )
              } else if (res.status === 'PENDING') {
                addToast('PayPal reports the payment as pending. Please do not pay again.', 'info')
              } else {
                // UNKNOWN: we could not confirm the outcome. Never tell the buyer it failed.
                addToast(res.message || 'We could not confirm the result yet. Do not pay again. Open a case and we will check PayPal.', 'warning')
              }
            } catch (err: any) {
              addToast(`Capture failed or timed out: ${err.message}`, 'warning')
              // Keep the order ID so a case can still be opened
              setOrderId(data.orderID)
            } finally {
              setLoading(false)
            }
          },
          onError: (err: any) => {
            console.error('PayPal Smart Buttons error:', err)
            addToast('The PayPal payment was canceled or hit an error.', 'info')
          },
          style: { shape: 'pill', color: 'gold', layout: 'vertical', label: 'paypal' },
        })
        .render(buttonsRef.current)

      setButtonsRendered(true)
    } catch (e) {
      console.error('Error rendering PayPal buttons:', e)
    }
  }

  const checkStatus = async () => {
    if (!orderId) return
    setChecking(true)
    try {
      const out = await api.getOrderStatus(orderId)
      setStatusReport(out.report)
      if (out.report?.consensus === 'COMPLETED') setCaptured(true)
    } catch (err: any) {
      addToast(`Couldn’t check PayPal: ${err.message}`, 'warning')
    } finally {
      setChecking(false)
    }
  }

  const openCase = async () => {
    if (!orderId) {
      addToast('Create an order first, then open a case.', 'warning')
      return
    }
    setLoading(true)
    try {
      const c = await api.createCase(orderId)
      addToast(`Case #${c.id.slice(0, 8)} opened.`, 'success')
      nav(`/cases/${c.id}`)
    } catch (err: any) {
      addToast(`Couldn’t open the case: ${err.message}`, 'warning')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="space-y-4 px-5 pb-8 pt-2">
      <ScreenHeader
        label="Payment checkout"
        title="Send a payment."
        subtitle="Pay with PayPal, then we confirm what PayPal actually recorded."
      />
      <StepTracker steps={['Create order', 'Approve & pay', 'Confirm']} current={captured ? 2 : orderId ? 1 : 0} />

      {/* Amount card, in the style of a send-money screen */}
      <Card className="!p-5">
        <div className="flex items-center gap-3">
          <span className="flex h-12 w-12 items-center justify-center rounded-full bg-cyan-soft text-cyan-deep">
            <ShoppingBag size={22} />
          </span>
          <div className="min-w-0 flex-1">
            <p className="truncate text-[15px] font-bold text-navy">ResolveAI demo item</p>
            <p className="text-[12.5px] text-muted">Digital goods, instant delivery</p>
          </div>
        </div>

        <div className="my-6 text-center">
          <p className="text-[13px] font-semibold text-muted">Amount</p>
          <p className="mt-1 text-[52px] font-extrabold leading-none tracking-[-0.04em] text-navy tabular-nums">
            $25.00
          </p>
          <span className="mt-2 inline-block rounded-full bg-mist px-3 py-1 text-[12px] font-bold text-cyan-deep">USD</span>
        </div>

        <dl className="space-y-2 rounded-2xl bg-mist p-3.5 text-[12.5px]">
          <div className="flex justify-between">
            <dt className="text-muted">Environment</dt>
            <dd className="font-bold text-success">Sandbox</dd>
          </div>
          <div className="flex justify-between gap-3">
            <dt className="shrink-0 text-muted">Order ID</dt>
            <dd className="truncate font-mono font-medium text-navy">{orderId ?? 'Created when you pay'}</dd>
          </div>
        </dl>
      </Card>

      {!captured ? (
        <Card className="space-y-3">
          <p className="flex items-center justify-center gap-1.5 text-center text-[12.5px] font-semibold text-muted">
            <ShieldCheck size={15} className="text-cyan-deep" />
            Pay with the official PayPal button
          </p>

          {!buttonsRendered && !configFailed && (
            <div className="flex flex-col items-center gap-2 py-4 text-[13px] text-muted">
              <div className="h-6 w-6 animate-spin rounded-full border-[3px] border-cyan border-t-transparent" />
              <span>Loading PayPal…</span>
            </div>
          )}
          {configFailed && !buttonsRendered && (
            <p className="rounded-2xl bg-[#FFF4D6] p-3 text-[12.5px] font-medium leading-snug text-warning">
              The PayPal button isn’t available right now. Check the backend and your connection, then reload.
            </p>
          )}
          {/* The PayPal SDK renders into this div directly */}
          <div ref={buttonsRef} id="paypal-button-container" className={buttonsRendered ? 'min-h-[140px]' : 'hidden'} />

          {orderId && (
            <div className="border-t border-line pt-3">
              <Button variant="outline" className="w-full" onClick={openCase} loading={loading}>
                <AlertTriangle size={16} className="text-warning" />
                Payment stuck? Open a case
              </Button>
            </div>
          )}
        </Card>
      ) : (
        <Card className="space-y-4 text-center">
          <div className="mx-auto flex h-16 w-16 items-center justify-center rounded-full bg-[#E4F5EB] text-success">
            <CheckCircle2 size={34} />
          </div>
          <div>
            <p className="text-[18px] font-extrabold text-navy">Payment captured</p>
            <p className="mt-1 text-[12.5px] text-muted">Recorded in the PayPal sandbox.</p>
          </div>
          <Button variant="outline" className="w-full" onClick={openCase} loading={loading}>
            <AlertTriangle size={16} className="text-warning" />
            Not confirmed? Open a case
          </Button>
        </Card>
      )}

      {orderId && (
        <Card>
          <PaymentStatusPanel report={statusReport} checking={checking} onCheck={checkStatus} />
        </Card>
      )}
    </div>
  )
}
