import React, { useEffect, useState, useRef } from 'react'
import { api, PublicConfig } from '../lib/api'
import { Card } from '../components/Card'
import { PillButton } from '../components/PillButton'
import { useNavigate } from 'react-router-dom'
import { Shield, ShoppingBag, CheckCircle, AlertTriangle, ArrowRight } from 'lucide-react'
import { useToast } from '../components/Toast'

declare global {
  interface Window {
    paypal?: any
  }
}

export function Checkout() {
  const [config, setConfig] = useState<PublicConfig | null>(null)
  const [orderId, setOrderId] = useState<string | null>(null)
  const [captured, setCaptured] = useState(false)
  const [loading, setLoading] = useState(false)
  const [buttonsRendered, setButtonsRendered] = useState(false)
  const buttonsRef = useRef<HTMLDivElement>(null)
  const nav = useNavigate()
  const { addToast } = useToast()

  useEffect(() => {
    api.getPublicConfig()
      .then((cfg) => {
        setConfig(cfg)
      })
      .catch((err) => {
        console.error('Failed to load public config', err)
        addToast('Failed to load PayPal sandbox configuration', 'warning')
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
    script.src = `https://www.paypal.com/sdk/js?client-id=${config.paypal_client_id}&currency=USD&intent=capture`
    script.async = true
    script.onload = () => {
      renderButtons()
    }
    script.onerror = () => {
      addToast('Failed to load PayPal JS SDK. Check your internet connection.', 'warning')
    }
    document.body.appendChild(script)

    return () => {
      // Don't remove script immediately to avoid reload loops
    }
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
              addToast(`Order creation failed: ${err.message}`, 'warning')
              throw err
            } finally {
              setLoading(false)
            }
          },
          onApprove: async (data: any) => {
            setLoading(true)
            try {
              await api.captureOrder(data.orderID)
              setCaptured(true)
              setOrderId(data.orderID)
              addToast('Payment captured successfully in PayPal Sandbox!', 'success')
            } catch (err: any) {
              addToast(`Capture failed or timed out: ${err.message}`, 'warning')
              // Even on timeout, retain order ID so user can open case
              setOrderId(data.orderID)
            } finally {
              setLoading(false)
            }
          },
          onError: (err: any) => {
            console.error('PayPal Smart Buttons error:', err)
            addToast('PayPal transaction error or canceled.', 'info')
          },
          style: {
            shape: 'pill',
            color: 'gold',
            layout: 'vertical',
            label: 'paypal',
          },
        })
        .render(buttonsRef.current)

      setButtonsRendered(true)
    } catch (e) {
      console.error('Error rendering PayPal buttons:', e)
    }
  }

  const openCase = async () => {
    if (!orderId) {
      addToast('No order ID found. Please create an order first.', 'warning')
      return
    }
    setLoading(true)
    try {
      const c = await api.createCase(orderId)
      addToast(`Dispute Case #${c.id.slice(0, 8)} opened.`, 'success')
      nav(`/cases/${c.id}`)
    } catch (err: any) {
      addToast(`Error opening case: ${err.message}`, 'warning')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="max-w-lg mx-auto mt-10 px-4 pb-16">
      <div className="text-center mb-6">
        <div className="w-12 h-12 bg-pp-blue/10 rounded-2xl flex items-center justify-center text-pp-blue mx-auto mb-3">
          <ShoppingBag size={24} />
        </div>
        <h1 className="text-2xl font-bold text-pp-blue-dark">PayPal Sandbox Checkout</h1>
        <p className="text-sm text-ink-soft mt-1">
          Complete a real sandbox transaction or trigger a stuck payment scenario.
        </p>
      </div>

      <Card className="border border-line">
        <div className="flex justify-between items-center mb-6 p-4 bg-surface rounded-xl border border-line">
          <div>
            <p className="font-semibold text-ink">ResolveAI Demo Item</p>
            <p className="text-xs text-ink-soft">Digital Goods · Instant Sandbox Delivery</p>
          </div>
          <div className="text-right">
            <span className="font-bold text-pp-blue-dark text-xl tabular-nums">$25.00</span>
            <p className="text-[10px] text-ink-soft uppercase font-mono">USD</p>
          </div>
        </div>

        {!captured ? (
          <div className="space-y-4">
            <div className="text-xs text-ink-soft text-center mb-2">
              Pay securely via official PayPal Smart Buttons (Sandbox mode)
            </div>

            {/* Spinner shown while PayPal SDK loads — OUTSIDE buttonsRef div to avoid DOM conflict */}
            {!buttonsRendered && (
              <div className="flex flex-col items-center gap-2 py-4 text-ink-soft text-sm">
                <div className="w-6 h-6 border-2 border-pp-blue border-t-transparent rounded-full animate-spin" />
                <span>Loading PayPal Smart Buttons...</span>
              </div>
            )}
            {/* PayPal SDK renders buttons directly into this div via DOM manipulation */}
            <div
              ref={buttonsRef}
              id="paypal-button-container"
              className={buttonsRendered ? 'min-h-[140px]' : 'hidden'}
            />

            {orderId && (
              <div className="pt-4 border-t border-line text-center space-y-2">
                <p className="text-xs text-ink-soft font-mono">
                  PayPal Order ID: <span className="font-bold text-pp-blue-dark">{orderId}</span>
                </p>
                <button
                  onClick={openCase}
                  className="text-xs text-warning hover:underline font-semibold"
                >
                  Payment stuck or unconfirmed? Open an investigation case →
                </button>
              </div>
            )}
          </div>
        ) : (
          <div className="space-y-5 py-2">
            <div className="p-4 bg-[#E6F4EC] rounded-xl text-success font-semibold text-center flex items-center justify-center gap-2">
              <CheckCircle size={20} />
              <span>✓ Payment Captured in Sandbox</span>
            </div>

            <div className="p-3 bg-surface rounded-xl text-xs space-y-1 font-mono text-ink-soft">
              <div className="flex justify-between">
                <span>PayPal Order ID:</span>
                <span className="font-bold text-pp-blue-dark">{orderId}</span>
              </div>
              <div className="flex justify-between">
                <span>Amount:</span>
                <span className="font-bold text-ink">$25.00 USD</span>
              </div>
              <div className="flex justify-between">
                <span>Environment:</span>
                <span className="text-success font-semibold">Sandbox</span>
              </div>
            </div>

            <PillButton
              variant="outline"
              className="w-full"
              onClick={openCase}
              loading={loading}
            >
              <AlertTriangle size={16} className="text-warning" />
              <span>Payment not confirmed? Open a case →</span>
            </PillButton>
          </div>
        )}
      </Card>

      <p className="text-center text-xs text-ink-soft mt-6">
        Built on the PayPal Developer Platform · Sandbox environment
      </p>
    </div>
  )
}
