import React, { useState } from 'react'
import { motion } from 'framer-motion'
import { useNavigate } from 'react-router-dom'
import { Shield, AlertTriangle, Clock, ArrowRight, User, Building2, CreditCard, Check } from 'lucide-react'
import { PillButton } from '../components/PillButton'
import { Card } from '../components/Card'

// Animated hero scene: Buyer -> PayPal (with ?/✓ morphing bubble) -> Seller
function HeroScene() {
  const [resolved, setResolved] = useState(false)

  return (
    <div
      className="relative w-full max-w-3xl mx-auto h-72 flex items-center justify-center p-4 cursor-pointer select-none"
      onMouseEnter={() => setResolved(true)}
      onMouseLeave={() => setResolved(false)}
      onClick={() => setResolved(!resolved)}
      title="Hover or click to resolve payment"
    >
      <svg viewBox="0 0 700 220" className="w-full h-full overflow-visible">
        <defs>
          <linearGradient id="pathGradient" x1="0%" y1="0%" x2="100%" y2="0%">
            <stop offset="0%" stopColor="#009CDE" />
            <stop offset="50%" stopColor="#FFC439" />
            <stop offset="100%" stopColor="#1F8A4C" />
          </linearGradient>

          <filter id="heroShadow" x="-20%" y="-20%" width="140%" height="140%">
            <feDropShadow dx="0" dy="4" stdDeviation="6" floodOpacity="0.15" />
          </filter>
        </defs>

        {/* Path: Buyer to Center */}
        <path
          id="buyerToPaypal"
          d="M 120 110 L 300 110"
          fill="none"
          stroke="url(#pathGradient)"
          strokeWidth="3"
          strokeDasharray="6 6"
          opacity="0.8"
        />

        {/* Path: Center to Seller */}
        <path
          id="paypalToSeller"
          d="M 400 110 L 580 110"
          fill="none"
          stroke={resolved ? '#1F8A4C' : '#CAD1D8'}
          strokeWidth="3"
          strokeDasharray={resolved ? '6 6' : '3 3'}
          className="transition-colors duration-500"
          opacity="0.8"
        />

        {/* Traveling money dots: Buyer -> Center */}
        <circle r="5" fill="#FFC439">
          <animateMotion dur="2s" repeatCount="indefinite" path="M 120 110 L 300 110" />
        </circle>
        <circle r="4" fill="#009CDE">
          <animateMotion dur="2s" begin="0.8s" repeatCount="indefinite" path="M 120 110 L 300 110" />
        </circle>

        {/* Traveling money dots: Center -> Seller (only when resolved) */}
        {resolved && (
          <circle r="5" fill="#1F8A4C">
            <animateMotion dur="2s" repeatCount="indefinite" path="M 400 110 L 580 110" />
          </circle>
        )}

        {/* Left Node: Buyer */}
        <g transform="translate(80, 110)" filter="url(#heroShadow)">
          <circle r="36" fill="#001C64" stroke="#009CDE" strokeWidth="2.5" />
          <foreignObject x="-16" y="-16" width="32" height="32">
            <div className="w-full h-full flex items-center justify-center text-white">
              <User size={20} />
            </div>
          </foreignObject>
          <text y="52" textAnchor="middle" fill="#FFFFFF" fontSize="12" fontWeight="600" className="tracking-wide">
            Buyer
          </text>
        </g>

        {/* Center Node: PayPal Engine */}
        <g transform="translate(350, 110)" filter="url(#heroShadow)">
          <circle r="48" fill="#FFFFFF" stroke={resolved ? '#1F8A4C' : '#0070E0'} strokeWidth="3" className="transition-colors duration-500" />
          <foreignObject x="-24" y="-24" width="48" height="48">
            <div className="w-full h-full flex items-center justify-center text-pp-blue-dark">
              <CreditCard size={28} />
            </div>
          </foreignObject>

          {/* Morphing Bubble: ? (pulsing) morphs into ✓ shield */}
          <g transform="translate(0, -56)">
            {resolved ? (
              <motion.g
                initial={{ scale: 0.8, rotate: -20 }}
                animate={{ scale: 1, rotate: 0 }}
                transition={{ type: 'spring', damping: 15 }}
              >
                <circle r="18" fill="#1F8A4C" stroke="#FFFFFF" strokeWidth="2" />
                <foreignObject x="-10" y="-10" width="20" height="20">
                  <div className="w-full h-full flex items-center justify-center text-white">
                    <Check size={14} strokeWidth={3} />
                  </div>
                </foreignObject>
              </motion.g>
            ) : (
              <motion.g
                animate={{ scale: [1, 1.15, 1], y: [0, -3, 0] }}
                transition={{ duration: 1.5, repeat: Infinity, ease: 'easeInOut' }}
              >
                <circle r="18" fill="#FFC439" stroke="#2C2E2F" strokeWidth="1.5" />
                <text
                  dy=".35em"
                  textAnchor="middle"
                  fill="#2C2E2F"
                  fontSize="16"
                  fontWeight="bold"
                  className="select-none font-mono"
                >
                  ?
                </text>
              </motion.g>
            )}
          </g>

          <text y="64" textAnchor="middle" fill="#FFFFFF" fontSize="12" fontWeight="600" className="tracking-wide">
            PayPal Engine
          </text>
        </g>

        {/* Right Node: Seller */}
        <g transform="translate(620, 110)" filter="url(#heroShadow)">
          <circle r="36" fill={resolved ? '#1F8A4C' : '#001C64'} stroke={resolved ? '#1F8A4C' : '#CAD1D8'} strokeWidth="2.5" className="transition-colors duration-500" />
          <foreignObject x="-16" y="-16" width="32" height="32">
            <div className="w-full h-full flex items-center justify-center text-white">
              <Building2 size={20} />
            </div>
          </foreignObject>
          <text y="52" textAnchor="middle" fill="#FFFFFF" fontSize="12" fontWeight="600" className="tracking-wide">
            Seller
          </text>
        </g>
      </svg>
    </div>
  )
}

export function Landing() {
  const nav = useNavigate()

  const scenarios = [
    {
      icon: <AlertTriangle size={24} className="text-warning" />,
      title: 'Lost Success Response',
      desc: 'Backend captured on PayPal, but response timed out locally. ResolveAI fails closed to UNKNOWN, prevents duplicate charge, and reconciles authoritative status.',
      badge: 'Network Fault',
      badgeColor: 'bg-[#FFF4D6] text-warning',
    },
    {
      icon: <Shield size={24} className="text-danger" />,
      title: 'Definitive Failure',
      desc: 'PayPal explicitly declines payment. Deterministic policy gates fresh retry strictly behind user review and verified failure proof.',
      badge: 'Declined State',
      badgeColor: 'bg-[#FDEBE6] text-danger',
    },
    {
      icon: <Clock size={24} className="text-pp-sky" />,
      title: 'Delayed Reconciliation',
      desc: 'Capture confirmed via delayed PayPal webhook. Case timeline and state machine update asynchronously via live Server-Sent Events.',
      badge: 'Asynchronous',
      badgeColor: 'bg-blue-50 text-pp-blue',
    },
  ]

  return (
    <div className="min-h-screen bg-surface">
      {/* Hero Section with radial gradient mesh */}
      <section className="relative overflow-hidden bg-gradient-to-b from-pp-navy via-pp-blue-dark to-pp-navy text-white pt-16 pb-24 px-6">
        {/* Subtle radial mesh keyframe drift */}
        <div className="absolute inset-0 opacity-20 pointer-events-none">
          <div className="absolute -top-32 -left-32 w-96 h-96 rounded-full bg-pp-sky blur-3xl animate-pulse" />
          <div className="absolute bottom-0 -right-32 w-96 h-96 rounded-full bg-pp-blue blur-3xl animate-pulse" style={{ animationDelay: '2s' }} />
        </div>

        <div className="relative max-w-5xl mx-auto text-center space-y-6">
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.6 }}
            className="inline-flex items-center gap-2 px-4 py-1.5 rounded-full bg-white/10 backdrop-blur-sm border border-white/20 text-xs font-semibold text-pp-gold tracking-wide"
          >
            <Shield size={14} />
            <span>Autonomous Payment Resolution & Recovery Engine</span>
          </motion.div>

          <motion.h1
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.6, delay: 0.1 }}
            className="text-4xl sm:text-5xl lg:text-6xl font-bold tracking-tight text-white max-w-3xl mx-auto leading-tight"
          >
            Payments should never leave you guessing.
          </motion.h1>

          <motion.p
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.6, delay: 0.2 }}
            className="text-lg text-gray-300 max-w-2xl mx-auto leading-relaxed"
          >
            ResolveAI eliminates stuck payments, prevents accidental double charges, and pairs authoritative PayPal evidence with an AI Investigator backed by a fail-closed safety engine.
          </motion.p>

          {/* Interactive animated hero diagram */}
          <motion.div
            initial={{ opacity: 0, scale: 0.95 }}
            animate={{ opacity: 1, scale: 1 }}
            transition={{ duration: 0.8, delay: 0.3 }}
            className="pt-4"
          >
            <HeroScene />
          </motion.div>

          {/* Call to Action buttons */}
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.6, delay: 0.4 }}
            className="flex flex-wrap items-center justify-center gap-4 pt-6"
          >
            <PillButton
              variant="gold"
              onClick={() => nav('/checkout')}
              className="text-base font-bold shadow-lg shadow-pp-gold/20"
            >
              <span>Start Real Sandbox Checkout</span>
              <ArrowRight size={18} />
            </PillButton>
            <PillButton
              variant="outline"
              onClick={() => nav('/console')}
              className="text-base text-white border-white/30 hover:bg-white/10"
            >
              Open Merchant Console
            </PillButton>
          </motion.div>
        </div>
      </section>

      {/* Scenario Cards */}
      <section className="max-w-6xl mx-auto px-6 py-20">
        <div className="text-center mb-14">
          <h2 className="text-3xl font-bold text-pp-blue-dark tracking-tight">
            Engineered for Real-World Payment Failures
          </h2>
          <p className="text-ink-soft mt-3 max-w-2xl mx-auto">
            Payment systems fail at network and human boundaries. ResolveAI enforces mathematical safety rules before permitting any side-effect.
          </p>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-8">
          {scenarios.map((sc, i) => (
            <motion.div
              key={i}
              initial={{ opacity: 0, y: 30 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true }}
              transition={{ duration: 0.5, delay: i * 0.15 }}
            >
              <Card className="h-full flex flex-col justify-between hover:shadow-lg transition-all duration-300 border border-line">
                <div>
                  <div className="flex items-center justify-between mb-4">
                    <div className="p-3 bg-surface rounded-xl">
                      {sc.icon}
                    </div>
                    <span className={`text-[11px] font-bold px-2.5 py-1 rounded-full ${sc.badgeColor}`}>
                      {sc.badge}
                    </span>
                  </div>

                  <h3 className="text-lg font-bold text-ink mb-2">
                    {sc.title}
                  </h3>
                  <p className="text-sm text-ink-soft leading-relaxed">
                    {sc.desc}
                  </p>
                </div>

                <div className="pt-6 mt-6 border-t border-line">
                  <button
                    onClick={() => nav('/checkout')}
                    className="inline-flex items-center gap-1.5 text-xs font-semibold text-pp-blue hover:text-pp-blue-dark transition-colors"
                  >
                    <span>Simulate in Checkout</span>
                    <ArrowRight size={12} />
                  </button>
                </div>
              </Card>
            </motion.div>
          ))}
        </div>
      </section>

      {/* Footer Info */}
      <footer className="border-t border-line py-8 text-center text-xs text-ink-soft bg-white">
        <p>Built on the PayPal Developer Platform · Sandbox environment</p>
        <p className="mt-1 text-[11px] text-gray-400">
          OAuth2 Client Credentials · Orders v2 · Payments v2 · Webhooks Signature Verification · Policy Engine (R01–R09)
        </p>
      </footer>
    </div>
  )
}
