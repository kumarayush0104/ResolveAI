import React, { useEffect, useRef } from 'react'
import { useLocation } from 'react-router-dom'
import { motion, useReducedMotion, useScroll, useTransform, type MotionValue } from 'framer-motion'
import { ArrowDown, Check, CircleHelp, Search, ShieldCheck, ShoppingBag, Store } from 'lucide-react'
import { PhoneFrame } from '../components/PhoneFrame'
import { ThreePayPalLogo } from '../components/ThreePayPalLogo'

function FloatingCard({
  className,
  progress,
  reveal,
  disappear,
  title,
  description,
  icon,
}: {
  className: string
  progress: MotionValue<number>
  reveal: [number, number]
  disappear: [number, number]
  title: string
  description: string
  icon: React.ReactNode
}) {
  const opacity = useTransform(progress, [reveal[0], reveal[1], disappear[0], disappear[1]], [0, 1, 1, 0])
  const scale = useTransform(progress, [reveal[0], reveal[1], disappear[0], disappear[1]], [0.9, 1, 1, 0.94])
  const rotate = useTransform(progress, [reveal[0], reveal[1], disappear[0]], [-5, 0, 2])
  const y = useTransform(progress, [reveal[0], reveal[1], disappear[0]], [32, 0, -14])

  return (
    <motion.article
      className={`story-feature-card ${className}`}
      style={{ opacity, scale, rotate, x: '-50%', y }}
    >
      <span className="story-feature-icon">{icon}</span>
      <span className="story-feature-kicker">RESOLVEAI · PAYMENT RECOVERY</span>
      <h2>{title}</h2>
      <p>{description}</p>
      <span className="story-feature-proof"><Check size={14} /> PayPal evidence first</span>
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
  const demoOpacity = useTransform(demoProgress, [0, 1], [0, 1])
  const demoY = useTransform(demoProgress, [0, 1], [20, 0])
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
          <div className="story-backdrop story-backdrop-one" aria-hidden />
          <div className="story-backdrop story-backdrop-two" aria-hidden />
          <ThreePayPalLogo scrollProgress={scrollYProgress} />

          <FloatingCard
            className="story-feature-card-left"
            progress={scrollYProgress}
            reveal={[0.14, 0.2]}
            disappear={[0.37, 0.44]}
            icon={<Search size={22} />}
            title="Know what happened."
            description="Check PayPal transaction records before anyone tries the payment again."
          />
          <FloatingCard
            className="story-feature-card-top"
            progress={scrollYProgress}
            reveal={[0.14, 0.2]}
            disappear={[0.37, 0.44]}
            icon={<Store size={22} />}
            title="Seller-managed offers."
            description="Sellers add items and update prices; buyers always see the current offer."
          />
          <FloatingCard
            className="story-feature-card-main"
            progress={scrollYProgress}
            reveal={[0.14, 0.2]}
            disappear={[0.37, 0.44]}
            icon={<ShieldCheck size={23} />}
            title="Never pay twice."
            description="ResolveAI checks the payment evidence before it allows a retry."
          />
          <FloatingCard
            className="story-feature-card-right"
            progress={scrollYProgress}
            reveal={[0.48, 0.54]}
            disappear={[0.72, 0.78]}
            icon={<Check size={22} />}
            title="Refunds need both sides."
            description="A refund request goes to the seller for approval before it is sent."
          />
          <FloatingCard
            className="story-feature-card-lower-left"
            progress={scrollYProgress}
            reveal={[0.48, 0.54]}
            disappear={[0.72, 0.78]}
            icon={<ShoppingBag size={22} />}
            title="See the final total."
            description="Buyers add seller-listed items to a cart, review the price, then check out."
          />
          <FloatingCard
            className="story-feature-card-lower-right"
            progress={scrollYProgress}
            reveal={[0.48, 0.54]}
            disappear={[0.72, 0.78]}
            icon={<CircleHelp size={22} />}
            title="Open a case when stuck."
            description="Bring the buyer and seller into one place to review the issue and its evidence."
          />

          <motion.div className="story-scroll-hint" style={{ opacity: hintOpacity }}>
            Scroll to explore <ArrowDown size={16} />
          </motion.div>

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
