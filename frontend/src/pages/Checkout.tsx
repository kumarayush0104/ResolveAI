import React, { useEffect, useState, useRef } from 'react'
import { api, PublicConfig } from '../lib/api'
import { Card } from '../components/Card'
import { PillButton } from '../components/PillButton'
import { useNavigate } from 'react-router-dom'
import { ShoppingBag, CheckCircle, AlertTriangle, ArrowLeft, Lock } from 'lucide-react'
import { useToast } from '../components/Toast'

declare global {
  interface Window { paypal?: any }
}

export function Checkout() {
  const [config, setConfig]               = useState<PublicConfig | null>(null)
  const [orderId, setOrderId]             = useState<string | null>(null)
  const [captured, setCaptured]           = useState(false)
  const [loading, setLoading]             = useState(false)
  const [buttonsRendered, setButtonsRendered] = useState(false)
  const buttonsRef = useRef<HTMLDivElement>(null)
  const nav        = useNavigate()
  const { addToast } = useToast()

  useEffect(() => {
    api.getPublicConfig()
      .then((cfg) => setConfig(cfg))
      .catch((err) => {
        console.error('Failed to load public config', err)
        addToast('Failed to load PayPal sandbox configuration', 'warning')
      })
  }, [])

  useEffect(() => {
    if (!config?.paypal_client_id || buttonsRendered) return
    const scriptId = 'paypal-js-sdk'
    if (document.getElementById(scriptId)) { renderButtons(); return }
    const script = document.createElement('script')
    script.id    = scriptId
    script.src   = `https://www.paypal.com/sdk/js?client-id=${config.paypal_client_id}&currency=USD&intent=capture`
    script.async = true
    script.onload  = () => renderButtons()
    script.onerror = () => addToast('Failed to load PayPal JS SDK.', 'warning')
    document.body.appendChild(script)
  }, [config])

  const renderButtons = () => {
    if (!window.paypal || !buttonsRef.current) return
    try {
      buttonsRef.current.innerHTML = ''
      window.paypal.Buttons({
        createOrder: async () => {
          setLoading(true)
          try {
            const res = await api.createOrder(25.0, 'USD')
            setOrderId(res.order_id)
            return res.order_id
          } catch (err: any) {
            addToast(`Order creation failed: ${err.message}`, 'warning'); throw err
          } finally { setLoading(false) }
        },
        onApprove: async (data: any) => {
          setLoading(true)
          try {
            await api.captureOrder(data.orderID)
            setCaptured(true); setOrderId(data.orderID)
            addToast('Payment captured successfully in PayPal Sandbox!', 'success')
          } catch (err: any) {
            addToast(`Capture failed or timed out: ${err.message}`, 'warning')
            setOrderId(data.orderID)
          } finally { setLoading(false) }
        },
        onError: (err: any) => {
          console.error('PayPal Smart Buttons error:', err)
          addToast('PayPal transaction error or canceled.', 'info')
        },
        style: { shape: 'pill', color: 'gold', layout: 'vertical', label: 'paypal' },
      }).render(buttonsRef.current)
      setButtonsRendered(true)
    } catch (e) { console.error('Error rendering PayPal buttons:', e) }
  }

  const openCase = async () => {
    if (!orderId) { addToast('No order ID found. Please create an order first.', 'warning'); return }
    setLoading(true)
    try {
      const c = await api.createCase(orderId)
      addToast(`Dispute Case #${c.id.slice(0, 8)} opened.`, 'success')
      nav(`/cases/${c.id}`)
    } catch (err: any) {
      addToast(`Error opening case: ${err.message}`, 'warning')
    } finally { setLoading(false) }
  }

  return (
    <div className="min-h-full bg-surface">

      {/* ── Hero Header ── */}
      <section className="hero-gradient rounded-b-[2.5rem] px-5 pt-14 pb-8">
        <button
          onClick={() => nav('/')}
          className="flex items-center gap-2 text-white/80 text-sm font-medium mb-5"
        >
          <ArrowLeft size={16} /> Back
        </button>
        <div className="flex items-center gap-3">
          <div className="w-12 h-12 bg-white/20 backdrop-blur rounded-2xl flex items-center justify-center text-white">
            <ShoppingBag size={24} />
          </div>
          <div>
            <h1 className="text-white font-bold text-xl">Sandbox Checkout</h1>
            <p className="text-white/60 text-xs">PayPal Developer Platform</p>
          </div>
        </div>
      </section>

      <div className="px-5 -mt-4 space-y-4 pb-8">

        {/* Product card */}
        <Card className="p-5 border border-line">
          <div className="flex items-center justify-between">
            <div>
              <p className="font-bold text-ink">ResolveAI Demo Item</p>
              <p className="text-xs text-ink-soft mt-0.5">Digital Goods · Instant Sandbox Delivery</p>
            </div>
            <div className="text-right">
              <span className="font-bold text-pp-blue-dark text-2xl tabular-nums">$25</span>
              <p className="text-[10px] text-ink-soft uppercase font-mono">.00 USD</p>
            </div>
          </div>
          <div className="mt-4 pt-4 border-t border-line flex items-center justify-between text-xs text-ink-soft">
            <div className="flex items-center gap-1.5">
              <Lock size={12} /><span>Secure Payment · SSL Encrypted</span>
            </div>
            <span className="font-mono bg-pp-gold/20 text-pp-blue-dark px-2 py-0.5 rounded-full font-semibold">
              SANDBOX
            </span>
          </div>
        </Card>

        {/* PayPal Button section */}
        {!captured ? (
          <Card className="p-5 border border-line space-y-4">
            <p className="text-xs text-ink-soft text-center font-medium">
              Pay securely via official PayPal Smart Buttons
            </p>
            {!buttonsRendered && (
              <div className="flex flex-col items-center gap-2 py-6 text-ink-soft text-sm">
                <div className="w-6 h-6 border-2 border-pp-blue border-t-transparent rounded-full animate-spin" />
                <span>Loading PayPal Smart Buttons...</span>
              </div>
            )}
            <div
              ref={buttonsRef}
              id="paypal-button-container"
              className={buttonsRendered ? 'min-h-[140px]' : 'hidden'}
            />
            {orderId && (
              <div className="pt-3 border-t border-line text-center space-y-2">
                <p className="text-xs text-ink-soft font-mono">
                  Order ID: <span className="font-bold text-pp-blue-dark">{orderId.slice(0, 16)}…</span>
                </p>
                <button onClick={openCase} className="text-xs text-warning hover:underline font-semibold">
                  Payment stuck or unconfirmed? Open a case →
                </button>
              </div>
            )}
          </Card>
        ) : (
          <Card className="p-5 border border-line space-y-4">
            <div className="p-4 bg-[#E6F4EC] rounded-2xl text-success font-bold text-center flex items-center justify-center gap-2">
              <CheckCircle size={20} /><span>✓ Payment Captured in Sandbox</span>
            </div>
            <div className="bg-surface rounded-2xl p-4 text-xs space-y-2 font-mono text-ink-soft border border-line">
              <div className="flex justify-between">
                <span>PayPal Order ID:</span>
                <span className="font-bold text-pp-blue-dark">{orderId?.slice(0, 16)}…</span>
              </div>
              <div className="flex justify-between">
                <span>Amount:</span><span className="font-bold text-ink">$25.00 USD</span>
              </div>
              <div className="flex justify-between">
                <span>Environment:</span><span className="text-success font-semibold">Sandbox</span>
              </div>
            </div>
            <PillButton variant="outline" className="w-full" onClick={openCase} loading={loading}>
              <AlertTriangle size={16} className="text-warning" />
              <span>Payment not confirmed? Open a case →</span>
            </PillButton>
          </Card>
        )}

        <p className="text-center text-xs text-ink-soft">
          Built on the PayPal Developer Platform · Sandbox environment
        </p>
      </div>
    </div>
  )
}
