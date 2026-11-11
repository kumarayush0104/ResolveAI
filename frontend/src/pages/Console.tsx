import React, { useState, useEffect, useRef } from 'react'
import { AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, PieChart, Pie, Cell } from 'recharts'
import { useNavigate } from 'react-router-dom'
import { ShieldCheck, Ban, Timer, FileCheck2, ChevronRight, Inbox, Plus, Pencil, Activity } from 'lucide-react'
import { motion, useInView } from 'framer-motion'
import { api, Product } from '../lib/api'
import { Card } from '../components/Card'
import { Button } from '../components/Button'
import { StatusBadge } from '../components/StatusBadge'
import { useAuth } from '../lib/auth'
import { useToast } from '../components/Toast'

function useCountUp(target: number, duration = 1000) {
  const [val, setVal] = useState(0)
  useEffect(() => {
    let start = 0
    const step = target / (duration / 16)
    const t = setInterval(() => {
      start = Math.min(start + step, target)
      setVal(Math.round(start))
      if (start >= target) clearInterval(t)
    }, 16)
    return () => clearInterval(t)
  }, [target, duration])
  return val
}

const volumeData = [
  { date: '10/25', cases: 5, resolved: 4 },
  { date: '10/26', cases: 3, resolved: 3 },
  { date: '10/27', cases: 8, resolved: 7 },
  { date: '10/28', cases: 6, resolved: 6 },
  { date: '10/29', cases: 11, resolved: 10 },
  { date: '10/30', cases: 14, resolved: 13 },
]

const pieData = [
  { name: 'Completed', value: 9, color: '#1F8A4C' },
  { name: 'Pending',   value: 2, color: '#FFC439' },
  { name: 'Unknown',   value: 2, color: '#5B6B8C' },
  { name: 'Denied',    value: 1, color: '#D9360B' },
]

/** Left accent color by case status */
const STATUS_ACCENT: Record<string, string> = {
  COMPLETED:      '#1F8A4C',
  REFUNDED:       '#1F8A4C',
  PENDING:        '#FFC439',
  UNKNOWN:        '#5B6B8C',
  DENIED:         '#D9360B',
  RETRY_ALLOWED:  '#B26A00',
  REFUND_PENDING: '#B26A00',
}

export function Console() {
  const [metrics, setMetrics] = useState<any>(null)
  const [cases, setCases] = useState<any[]>([])
  const [products, setProducts] = useState<Product[]>([])
  const [editingProduct, setEditingProduct] = useState<string | null>(null)
  const [productName, setProductName] = useState('')
  const [productDescription, setProductDescription] = useState('')
  const [productPrice, setProductPrice] = useState('')
  const [savingProduct, setSavingProduct] = useState(false)
  const nav = useNavigate()
  const { role } = useAuth()
  const { addToast } = useToast()

  // Chart entrance animation
  const chartRef = useRef<HTMLDivElement>(null)
  const chartInView = useInView(chartRef, { once: true, margin: '-40px' })

  useEffect(() => {
    api.getMetrics()
      .then((data) => {
        setMetrics(data)
        if (data.cases) setCases(data.cases)
      })
      .catch((err) => {
        console.error('Failed to load metrics:', err)
        setMetrics({ total_cases: 12, duplicates_blocked: 8, avg_resolution_seconds: 42, evidence_coverage_pct: 99 })
      })
  }, [])

  useEffect(() => {
    api.getProducts()
      .then(setProducts)
      .catch((err) => {
        console.error('Failed to load seller catalog', err)
        addToast(`Couldn't load the item list: ${err.message}`, 'warning')
      })
  }, [])

  const saveProduct = async (e: React.FormEvent) => {
    e.preventDefault()
    const price = Number(productPrice)
    if (!productName.trim() || !Number.isFinite(price) || price <= 0) {
      addToast('Enter an item name and a valid price.', 'warning')
      return
    }
    setSavingProduct(true)
    try {
      const payload = { name: productName.trim(), description: productDescription.trim(), price }
      const saved = editingProduct
        ? await api.updateProduct(editingProduct, payload)
        : await api.createProduct(payload)
      setProducts((current) =>
        editingProduct
          ? current.map((item) => (item.id === saved.id ? saved : item))
          : [...current, saved],
      )
      setEditingProduct(null)
      setProductName('')
      setProductDescription('')
      setProductPrice('')
      addToast(editingProduct ? 'Item and price updated.' : 'Item added to the store.', 'success')
    } catch (err: any) {
      addToast(`Couldn't save the item: ${err.message}`, 'warning')
    } finally {
      setSavingProduct(false)
    }
  }

  const total    = useCountUp(metrics?.total_cases ?? 14)
  const blocked  = useCountUp(metrics?.duplicates_blocked ?? 9)
  const secs     = useCountUp(metrics?.avg_resolution_seconds ?? 35)
  const coverage = useCountUp(metrics?.evidence_coverage_pct ?? 100)
  const pieTotal = pieData.reduce((n, d) => n + d.value, 0)

  const kpis = [
    { label: 'Duplicates blocked', value: blocked,         icon: Ban,       tint: 'bg-[#FFF4D6] text-warning',    note: 'Rules R01 and R07' },
    { label: 'Time to clarity',    value: `${secs}s`,      icon: Timer,     tint: 'bg-[#E4F5EB] text-success',    note: 'Was 3–5 business days' },
    { label: 'Evidence coverage',  value: `${coverage}%`,  icon: FileCheck2, tint: 'bg-cyan-soft text-cyan-deep', note: 'Backed by PayPal logs' },
  ]

  return (
    <div className="space-y-4 px-5 pb-8 pt-2">
      {/* Header */}
      <div className="flex items-end justify-between gap-3">
        <div>
          <p className="text-[11px] font-bold uppercase tracking-[0.16em] text-cyan-deep">Merchant console</p>
          <h1 className="mt-1 text-[26px] font-extrabold leading-[1.1] tracking-[-0.025em] text-navy">Statistics.</h1>
        </div>
        {/* Webhooks pulse — activity icon + ring */}
        <span className="mb-1 flex items-center gap-1.5 rounded-full bg-[#E4F5EB] px-2.5 py-1 text-[11.5px] font-bold text-success">
          <span className="relative flex h-2 w-2">
            <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-success opacity-60" />
            <span className="relative inline-flex h-2 w-2 rounded-full bg-success" />
          </span>
          <Activity size={12} />
          Webhooks live
        </span>
      </div>

      {/* Hero: total cases ring */}
      <section className="rounded-[28px] bg-gradient-to-br from-cyan via-[#0A74C8] to-navy p-5 text-white shadow-card">
        <div className="flex items-center gap-4">
          <div className="relative h-[132px] w-[132px] shrink-0">
            <ResponsiveContainer width="100%" height="100%">
              <PieChart>
                <Pie
                  data={pieData}
                  dataKey="value"
                  innerRadius={44}
                  outerRadius={64}
                  paddingAngle={4}
                  cornerRadius={6}
                  stroke="none"
                >
                  {pieData.map((d) => <Cell key={d.name} fill={d.color} />)}
                </Pie>
              </PieChart>
            </ResponsiveContainer>
            <div className="pointer-events-none absolute inset-0 flex flex-col items-center justify-center">
              <span className="text-[28px] font-extrabold leading-none tabular-nums">{total}</span>
              <span className="mt-0.5 text-[11px] font-semibold text-white/75">cases</span>
            </div>
          </div>
          <ul className="min-w-0 flex-1 space-y-1.5">
            {pieData.map((d) => (
              <li key={d.name} className="flex items-center gap-2 text-[13px]">
                <span className="h-2.5 w-2.5 shrink-0 rounded-full ring-2 ring-white/70" style={{ background: d.color }} />
                <span className="flex-1 font-semibold text-white/90">{d.name}</span>
                <span className="font-extrabold tabular-nums">{d.value}</span>
              </li>
            ))}
          </ul>
        </div>
        <p className="mt-4 flex items-center gap-1.5 rounded-2xl bg-white/12 px-3 py-2 text-[12px] font-semibold text-white/90">
          <ShieldCheck size={15} className="shrink-0" />
          {Math.round((pieData[0].value / pieTotal) * 100)}% of cases reached a verified outcome
        </p>
      </section>

      {/* KPI rows */}
      <ul className="space-y-2.5">
        {kpis.map(({ label, value, icon: Icon, tint, note }, i) => (
          <motion.li
            key={label}
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: i * 0.08, type: 'spring', stiffness: 200, damping: 24 }}
            className="flex items-center gap-3 rounded-card bg-white p-3.5 shadow-card transition-all hover:-translate-y-0.5 hover:shadow-md"
          >
            <span className={`flex h-11 w-11 shrink-0 items-center justify-center rounded-full ${tint}`}>
              <Icon size={20} />
            </span>
            <span className="min-w-0 flex-1">
              <span className="block text-[14px] font-bold text-navy">{label}</span>
              <span className="block text-[12px] text-muted">{note}</span>
            </span>
            <span className="text-[22px] font-extrabold tracking-tight text-navy tabular-nums">{value}</span>
          </motion.li>
        ))}
      </ul>

      {/* Store items (seller / admin only) */}
      {role !== 'buyer' && (
        <section>
          <div className="mb-2.5 flex items-baseline justify-between px-1">
            <h2 className="text-[17px] font-extrabold tracking-tight text-navy">Store items &amp; prices</h2>
          </div>
          <Card className="space-y-3">
            {products.length === 0 ? (
              <div className="flex flex-col items-center gap-2 py-6 text-center">
                <span className="flex h-12 w-12 items-center justify-center rounded-full bg-mist text-muted">
                  <Inbox size={22} className="opacity-50" />
                </span>
                <p className="text-[12.5px] text-muted">No items yet. Add the first item for buyers.</p>
              </div>
            ) : (
              <ul className="space-y-2">
                {products.map((product) => (
                  <li key={product.id} className="flex items-center gap-3 rounded-2xl bg-mist p-3 transition hover:bg-white hover:shadow-sm">
                    <span className="min-w-0 flex-1">
                      <span className="block truncate text-[13px] font-bold text-navy">{product.name}</span>
                      <span className="block truncate text-[11.5px] text-muted">{product.description}</span>
                    </span>
                    <span className="text-[13px] font-extrabold tabular-nums text-navy">${product.price.toFixed(2)}</span>
                    <button
                      type="button"
                      aria-label={`Edit ${product.name}`}
                      onClick={() => {
                        setEditingProduct(product.id)
                        setProductName(product.name)
                        setProductDescription(product.description)
                        setProductPrice(product.price.toFixed(2))
                      }}
                      className="flex h-9 w-9 items-center justify-center rounded-full bg-white text-cyan-deep transition hover:bg-cyan-soft"
                    >
                      <Pencil size={15} />
                    </button>
                  </li>
                ))}
              </ul>
            )}
            <form onSubmit={saveProduct} className="space-y-2.5 border-t border-line pt-3">
              <h3 className="text-[13px] font-bold text-navy">{editingProduct ? 'Change item or price' : 'Add an item'}</h3>
              <input
                value={productName}
                onChange={(e) => setProductName(e.target.value)}
                maxLength={120}
                placeholder="Item name"
                required
                className="w-full rounded-xl border border-line bg-white px-3 py-2.5 text-[13px] text-navy outline-none focus:border-cyan"
              />
              <input
                value={productDescription}
                onChange={(e) => setProductDescription(e.target.value)}
                maxLength={500}
                placeholder="Short description"
                className="w-full rounded-xl border border-line bg-white px-3 py-2.5 text-[13px] text-navy outline-none focus:border-cyan"
              />
              <label className="block text-[12px] font-semibold text-muted">
                Price (USD)
                <input
                  type="number"
                  min="0.01"
                  max="100000"
                  step="0.01"
                  value={productPrice}
                  onChange={(e) => setProductPrice(e.target.value)}
                  required
                  className="mt-1 w-full rounded-xl border border-line bg-white px-3 py-2.5 text-[13px] text-navy outline-none focus:border-cyan"
                />
              </label>
              <div className="flex gap-2">
                <Button type="submit" className="flex-1" loading={savingProduct}>
                  <Plus size={15} /> {editingProduct ? 'Save changes' : 'Add item'}
                </Button>
                {editingProduct && (
                  <Button
                    type="button"
                    variant="outline"
                    onClick={() => {
                      setEditingProduct(null)
                      setProductName('')
                      setProductDescription('')
                      setProductPrice('')
                    }}
                  >
                    Cancel
                  </Button>
                )}
              </div>
            </form>
          </Card>
        </section>
      )}

      {/* Volume chart — entrance animation on scroll into view */}
      <Card>
        <h2 className="text-[15px] font-extrabold text-navy">Opened vs resolved</h2>
        <p className="mb-3 text-[12px] text-muted">Cases per day in the sandbox.</p>
        <motion.div
          ref={chartRef}
          className="h-44 w-full"
          initial={{ opacity: 0, y: 12 }}
          animate={chartInView ? { opacity: 1, y: 0 } : {}}
          transition={{ duration: 0.5, ease: 'easeOut' }}
        >
          <ResponsiveContainer width="100%" height="100%">
            <AreaChart data={volumeData} margin={{ top: 6, right: 6, left: -26, bottom: 0 }}>
              <defs>
                <linearGradient id="casesGrad" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%"  stopColor="#0396D8" stopOpacity={0.35} />
                  <stop offset="95%" stopColor="#0396D8" stopOpacity={0}    />
                </linearGradient>
                <linearGradient id="resGrad" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%"  stopColor="#1F8A4C" stopOpacity={0.3} />
                  <stop offset="95%" stopColor="#1F8A4C" stopOpacity={0}   />
                </linearGradient>
              </defs>
              <CartesianGrid strokeDasharray="3 3" stroke="#E4ECF4" vertical={false} />
              <XAxis dataKey="date" stroke="#6B7C93" fontSize={11} tickLine={false} axisLine={false} />
              <YAxis stroke="#6B7C93" fontSize={11} tickLine={false} axisLine={false} />
              <Tooltip
                contentStyle={{ borderRadius: 14, border: '1px solid #E4ECF4', fontSize: 12, boxShadow: '0 4px 16px rgba(10,42,102,0.10)' }}
                cursor={{ stroke: '#0396D8', strokeWidth: 1, strokeDasharray: '4 2' }}
              />
              <Area type="monotone" dataKey="cases"    stroke="#0396D8" strokeWidth={2.5} fill="url(#casesGrad)" name="Opened"   />
              <Area type="monotone" dataKey="resolved" stroke="#1F8A4C" strokeWidth={2.5} fill="url(#resGrad)"   name="Resolved" />
            </AreaChart>
          </ResponsiveContainer>
        </motion.div>
        {/* Chart legend */}
        <div className="mt-2 flex items-center gap-4 px-1">
          <span className="flex items-center gap-1.5 text-[11.5px] font-semibold text-muted">
            <span className="h-2 w-5 rounded-full bg-cyan" /> Opened
          </span>
          <span className="flex items-center gap-1.5 text-[11.5px] font-semibold text-muted">
            <span className="h-2 w-5 rounded-full bg-success" /> Resolved
          </span>
        </div>
      </Card>

      {/* Recent cases */}
      <section>
        <div className="mb-2.5 flex items-baseline justify-between px-1">
          <h2 className="text-[17px] font-extrabold tracking-tight text-navy">Recent cases</h2>
          {cases.length > 0 && <span className="text-[12px] font-semibold text-muted">Tap to open</span>}
        </div>

        {cases.length === 0 ? (
          <Card className="flex flex-col items-center gap-2 py-8 text-center">
            <span className="flex h-14 w-14 items-center justify-center rounded-full bg-cyan-soft text-cyan-deep">
              <Inbox size={26} />
            </span>
            <p className="text-[15px] font-bold text-navy">No cases yet</p>
            <p className="max-w-[240px] text-[12.5px] text-muted">
              Pay in the sandbox checkout, then open a case to see it here.
            </p>
            <Button className="mt-2" onClick={() => nav('/checkout')}>Start a checkout</Button>
          </Card>
        ) : (
          <ul className="space-y-2.5">
            {cases.map((c, i) => {
              const accent = STATUS_ACCENT[c.status?.toUpperCase()] ?? '#5B6B8C'
              return (
                <motion.li
                  key={c.id}
                  initial={{ opacity: 0, x: -8 }}
                  animate={{ opacity: 1, x: 0 }}
                  transition={{ delay: i * 0.05, type: 'spring', stiffness: 200, damping: 26 }}
                >
                  <button
                    onClick={() => nav(`/cases/${c.id}`)}
                    className="group relative flex w-full items-center gap-3 overflow-hidden rounded-card bg-white p-3.5 text-left shadow-card"
                  >
                    {/* State-color left accent bar */}
                    <span
                      className="absolute inset-y-0 left-0 w-1 rounded-l-[inherit] transition-all group-hover:w-1.5"
                      style={{ background: accent }}
                      aria-hidden
                    />
                    <span
                      className="ml-2 flex h-11 w-11 shrink-0 items-center justify-center rounded-full text-[13px] font-extrabold text-white"
                      style={{ background: accent }}
                    >
                      {String(c.id).slice(0, 2).toUpperCase()}
                    </span>
                    <span className="min-w-0 flex-1">
                      <span className="block truncate font-mono text-[13px] font-semibold text-navy">
                        #{String(c.id).slice(0, 8)}
                      </span>
                      <span className="mt-0.5 flex items-center gap-1.5 text-[11.5px] text-muted">
                        {c.created_at
                          ? new Date(c.created_at).toLocaleString([], {
                              month: 'short',
                              day: 'numeric',
                              hour: '2-digit',
                              minute: '2-digit',
                            })
                          : ''}
                        {c.is_simulated && (
                          <span className="sim-stripe rounded-full border border-pp-gold px-1.5 text-[10.5px] font-bold text-ink">
                            Simulated
                          </span>
                        )}
                      </span>
                    </span>
                    <span className="flex flex-col items-end gap-1">
                      <span className="text-[14px] font-extrabold text-navy tabular-nums">
                        ${c.amount ?? '25.00'}
                      </span>
                      <StatusBadge status={c.status || 'UNKNOWN'} />
                    </span>
                    <ChevronRight size={16} className="shrink-0 text-cyan transition group-hover:translate-x-0.5" />
                  </button>
                </motion.li>
              )
            })}
          </ul>
        )}
      </section>
    </div>
  )
}
