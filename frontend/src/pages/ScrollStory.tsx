import React, { useEffect, useRef, useState } from 'react'
import { useLocation } from 'react-router-dom'
import {
  motion,
  useReducedMotion,
  useScroll,
  useTransform,
  useSpring,
  useMotionValueEvent,
  type MotionValue,
} from 'framer-motion'
import { ArrowDown, Check, CircleHelp, Search, ShieldCheck, ShoppingBag, Store } from 'lucide-react'
import { PhoneFrame } from '../components/PhoneFrame'
import { ThreePayPalLogo } from '../components/ThreePayPalLogo'

/** Left accent colors by card theme */
const ACCENT: Record<string, string> = {
  search:    '#0396D8',
  store:     '#0A2A66',
  shield:    '#1F8A4C',
  check:     '#FFC439',
  shopping:  '#0396D8',
  help:      '#B26A00',
}

function FloatingCard({
  className,
  progress,
  reveal,
  disappear,
  title,
  description,
  icon,
  accentKey,
}: {
  className: string
  progress: MotionValue<number>
  reveal: [number, number]
  disappear: [number, number]
  title: string
  description: string
  icon: React.ReactNode
  accentKey: string
}) {
  const reduceMotion = useReducedMotion() ?? false

  // Conditional mounting: unmounts card completely when outside its active scroll range
  // eliminating any ghost layers or text bleed-through from overlapping cards
  const [inRange, setInRange] = useState(() => {
    const v = progress.get()
    return v >= reveal[0] - 0.02 && v <= disappear[1] + 0.02
  })

  useMotionValueEvent(progress, 'change', (v) => {
    const shouldBeActive = v >= reveal[0] - 0.02 && v <= disappear[1] + 0.02
    setInRange(shouldBeActive)
  })

  // Clean fade from 0 -> 1 -> 1 -> 0 with no residual opacity
  const opacity = useTransform(
    progress,
    [reveal[0], reveal[1], disappear[0], disappear[1]],
    [0, 1, 1, 0],
  )
  const scale = useTransform(
    progress,
    [reveal[0], reveal[1], disappear[0], disappear[1]],
    reduceMotion ? [1, 1, 1, 1] : [0.92, 1, 1, 0.95],
  )
  const rotate = useTransform(
    progress,
    [reveal[0], reveal[1], disappear[0]],
    reduceMotion ? [0, 0, 0] : [-4, 0, 1.5],
  )
  const y = useTransform(
    progress,
    [reveal[0], reveal[1], disappear[0], disappear[1]],
    reduceMotion ? [0, 0, 0, 0] : [36, 0, -6, -20],
  )

  // Subtle 3D tilt springs
  const rotateX = useSpring(
    useTransform(progress, [reveal[0], reveal[1], disappear[0]], reduceMotion ? [0, 0, 0] : [3, 0, -1]),
    { stiffness: 120, damping: 28 },
  )

  // Unmount completely when outside active scroll range
  if (!inRange) {
    return null
  }

  const accent = ACCENT[accentKey] ?? '#0396D8'

  return (
    <motion.article
      className={`story-feature-card flex flex-col justify-between ${className}`}
      style={{ opacity, scale, rotate, rotateX, x: '-50%', y }}
    >
      {/* Left color accent stripe — inset from corners to eliminate border clipping */}
      <span
        className="pointer-events-none absolute left-0 top-6 bottom-6 w-1 rounded-r-full"
        style={{ background: accent }}
        aria-hidden
      />

      <div className="flex flex-col flex-1">
        <span className="story-feature-icon" style={{ background: `${accent}18`, color: accent }}>
          {icon}
        </span>
        <span className="story-feature-kicker" style={{ color: accent }}>RESOLVEAI · PAYMENT RECOVERY</span>
        <h2>{title}</h2>
        <p className="flex-1">{description}</p>
      </div>

      {/* Pinned bottom baseline across all cards regardless of text length */}
      <div className="story-feature-proof mt-auto pt-4">
        <Check size={14} /> PayPal evidence first
      </div>
    </motion.article>
  )
}

export function ScrollStory({ children }: { children: React.ReactNode }) {
  const demoRef = useRef<HTMLElement>(null)
  const storyRef = useRef<HTMLElement>(null)
  const { pathname } = useLocation()
  const reduceMotion = useReducedMotion() ?? false
  const { scrollYProgress } = useScroll({
    target: storyRef,
    offset: ['start start', 'end end'],
  })
  const { scrollYProgress: demoProgress } = useScroll({
    target: demoRef,
    offset: ['start end', 'start start'],
  })

  // Smoother spring on scroll-linked values
  const smoothScroll = useSpring(scrollYProgress, { stiffness: 80, damping: 25 })
  const activeProgress = reduceMotion ? scrollYProgress : smoothScroll

  const demoOpacity = useTransform(demoProgress, [0, 1], [0, 1])
  const demoY = useTransform(demoProgress, [0, 1], [24, 0])
  const demoScale = useTransform(demoProgress, [0, 1], [0.97, 1])
  const stepsOpacity = useTransform(demoProgress, [0.05, 0.45], [0, 1])
  const stepsY = useTransform(demoProgress, [0.05, 0.45], [24, 0])
  const stepLine = useTransform(demoProgress, [0.15, 0.9], [0, 1])
  const hintOpacity = useTransform(scrollYProgress, [0, 0.12], [1, 0])
  const storySteps = ['Verify payment', 'Sync both sides', 'Resolve with confidence']

  useEffect(() => {
    if (pathname !== '/') {
      demoRef.current?.scrollIntoView({ behavior: reduceMotion ? 'auto' : 'smooth' })
    }
  }, [pathname, reduceMotion])

  return (
    <main className="story-page min-h-screen overflow-x-clip bg-[#F5F9FC] text-navy">
      <section ref={storyRef} className="story-scroll-track relative">
        <div className="story-scroll-stage sticky top-0 flex h-[100svh] items-center justify-center">
          {/* Soft floating orb backdrops */}
          <div className="story-backdrop story-backdrop-one" aria-hidden />
          <div className="story-backdrop story-backdrop-two" aria-hidden />
          <ThreePayPalLogo scrollProgress={activeProgress} />

          {/* Batch 1 — reveals 14–44% */}
          <FloatingCard
            className="story-feature-card-left"
            progress={activeProgress}
            reveal={[0.14, 0.2]}
            disappear={[0.37, 0.44]}
            icon={<Search size={22} />}
            accentKey="search"
            title="Know what happened."
            description="Check PayPal transaction records before anyone tries the payment again."
          />
          <FloatingCard
            className="story-feature-card-top"
            progress={activeProgress}
            reveal={[0.14, 0.2]}
            disappear={[0.37, 0.44]}
            icon={<Store size={22} />}
            accentKey="store"
            title="Seller-managed offers."
            description="Sellers add items and update prices; buyers always see the current offer."
          />
          <FloatingCard
            className="story-feature-card-main"
            progress={activeProgress}
            reveal={[0.14, 0.2]}
            disappear={[0.37, 0.44]}
            icon={<ShieldCheck size={23} />}
            accentKey="shield"
            title="Never pay twice."
            description="ResolveAI checks the payment evidence before it allows a retry."
          />

          {/* Batch 2 — reveals 48–78% */}
          <FloatingCard
            className="story-feature-card-right"
            progress={activeProgress}
            reveal={[0.48, 0.54]}
            disappear={[0.72, 0.78]}
            icon={<Check size={22} />}
            accentKey="check"
            title="Refunds need both sides."
            description="A refund request goes to the seller for approval before it is sent."
          />
          <FloatingCard
            className="story-feature-card-lower-left"
            progress={activeProgress}
            reveal={[0.48, 0.54]}
            disappear={[0.72, 0.78]}
            icon={<ShoppingBag size={22} />}
            accentKey="shopping"
            title="See the final total."
            description="Buyers add seller-listed items to a cart, review the price, then check out."
          />
          <FloatingCard
            className="story-feature-card-lower-right"
            progress={activeProgress}
            reveal={[0.48, 0.54]}
            disappear={[0.72, 0.78]}
            icon={<CircleHelp size={22} />}
            accentKey="help"
            title="Open a case when stuck."
            description="Bring the buyer and seller into one place to review the issue and its evidence."
          />

          {/* Scroll hint — fades out as user scrolls */}
          <motion.div className="story-scroll-hint" style={{ opacity: hintOpacity }}>
            Scroll to explore <ArrowDown size={16} />
          </motion.div>

          {/* Progress bar */}
          <span className="story-scroll-progress" aria-hidden>
            SCROLL TO EXPLORE <motion.span style={{ scaleX: scrollYProgress }} />
          </span>
        </div>
      </section>

      <section ref={demoRef} className="story-demo relative flex min-h-screen flex-col items-center px-4 pb-14 pt-16 sm:px-8">
        <div className="story-demo-glow" aria-hidden />
        <motion.div className="relative z-10 flex w-full flex-col items-center" style={{ opacity: demoOpacity, y: demoY, scale: demoScale }}>
          <div className="mb-7 max-w-2xl text-center">
            <p className="text-[11px] font-extrabold uppercase tracking-[0.22em] text-cyan-deep">The interactive demo</p>
            <h2 className="mt-3 text-[clamp(2rem,5vw,3.8rem)] font-extrabold leading-tight tracking-[-0.055em] text-[#102A53]">
              Your turn to explore.
            </h2>
            <p className="mt-3 text-[14px] leading-relaxed text-muted">
              Switch buyer and seller roles, manage items and prices, check payments, and open a case.
            </p>
          </div>
          <div className="story-phone-showcase relative z-10">
            <PhoneFrame>{children}</PhoneFrame>
            <motion.aside
              className="story-how-it-works"
              style={{ opacity: stepsOpacity, y: stepsY }}
              aria-label="How ResolveAI works"
            >
              <div className="story-how-it-works-heading">HOW IT WORKS</div>
              <div className="story-step-list">
                <motion.div className="story-step-line-fill" style={{ scaleY: stepLine }} />
                {storySteps.map((step, index) => (
                  <div className="story-step" key={step}>
                    <span className="story-step-number">{index + 1}</span>
                    <span>{step}</span>
                  </div>
                ))}
              </div>
            </motion.aside>
          </div>
          <div className="story-trust-strip" aria-label="ResolveAI safeguards">
            <div className="story-trust-item"><ShieldCheck size={18} /><span>PayPal-verified evidence</span></div>
            <div className="story-trust-item"><Store size={18} /><span>Seller-approved refunds</span></div>
            <div className="story-trust-item"><CircleHelp size={18} /><span>Case support when stuck</span></div>
          </div>
          <p className="relative z-10 mt-4 text-center text-[11px] font-semibold text-muted">
            PayPal sandbox only · No real payments move.
          </p>
        </motion.div>
      </section>
    </main>
  )
}
