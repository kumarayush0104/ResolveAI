import React, { useEffect, useRef, useState } from 'react'
import { useLocation } from 'react-router-dom'
import { motion, useReducedMotion, useMotionValue, useTransform, useSpring } from 'framer-motion'
import { OverlayContext } from './Overlay'
import { AppBar } from './AppBar'
import { TabBar } from './TabBar'
import { ToastProvider } from './Toast'
import { useAuth } from '../lib/auth'

/** Layered device shadow — physical depth without being harsh */
const PHONE_SHADOW = [
  '0 48px 96px -16px rgba(10,42,102,0.45)',
  '0 16px 36px -8px rgba(0,0,0,0.22)',
  'inset 0 1.5px 0 rgba(255,255,255,0.18)',
  'inset 0 -1px 0 rgba(255,255,255,0.06)',
].join(', ')

/**
 * Device mockup used to preview the app inside the scroll story.
 *
 * Desktop (≥ 640px): real phone proportions with optional subtle 3D tilt on
 * pointer move. The frame and chrome (status bar, notch, home indicator) are
 * always shown.
 *
 * Small screens (< 640px): drops the frame entirely and goes full-bleed so it
 * reads as a native mobile app without chrome overhead. TabBar still shows.
 */
export function PhoneFrame({ children, zoom = 1 }: { children: React.ReactNode; zoom?: number }) {
  const [overlayEl, setOverlayEl] = useState<HTMLElement | null>(null)
  const scrollRef = useRef<HTMLDivElement>(null)
  const frameRef = useRef<HTMLDivElement>(null)
  const { pathname } = useLocation()
  const { isLoading, token } = useAuth()
  const reduceMotion = useReducedMotion() ?? false

  // 3D tilt motion values — desktop only, ignored on small screens
  const mouseX = useMotionValue(0)
  const mouseY = useMotionValue(0)
  const rotX = useSpring(useTransform(mouseY, [-1, 1], [3, -3]), { stiffness: 120, damping: 30 })
  const rotY = useSpring(useTransform(mouseX, [-1, 1], [-3, 3]), { stiffness: 120, damping: 30 })

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: 0 })
  }, [pathname])

  const handleMouseMove = (e: React.MouseEvent<HTMLDivElement>) => {
    if (reduceMotion) return
    const el = frameRef.current
    if (!el) return
    const rect = el.getBoundingClientRect()
    // Normalize to [-1, 1]
    mouseX.set(((e.clientX - rect.left) / rect.width) * 2 - 1)
    mouseY.set(((e.clientY - rect.top) / rect.height) * 2 - 1)
  }

  const handleMouseLeave = () => {
    mouseX.set(0)
    mouseY.set(0)
  }

  const inner = (
    <>
      <OverlayContext.Provider value={overlayEl}>
        <ToastProvider>
          <div ref={scrollRef} className="phone-scroll relative min-h-0 flex-1 overflow-y-auto overscroll-contain">
            {isLoading && !token ? (
              <div className="flex h-full flex-col items-center justify-center gap-3 text-muted">
                <div className="h-8 w-8 animate-spin rounded-full border-[3px] border-cyan border-t-transparent" />
                <span className="text-[13px] font-semibold">Connecting to ResolveAI…</span>
              </div>
            ) : (
              children
            )}
          </div>
          <TabBar />
          {/* Overlay portal — sheets/modals stay inside device bounds */}
          <div ref={setOverlayEl} className="pointer-events-none absolute inset-0 z-40" />
        </ToastProvider>
      </OverlayContext.Provider>
    </>
  )

  return (
    <>
      {/*
       * Full-bleed on sm and below (< 640px).
       * The frame chrome is hidden; we render as a native-looking mobile page.
       */}
      <div className="flex flex-col sm:hidden h-[100dvh] w-full bg-canvas">
        <AppBar />
        {inner}
      </div>

      {/*
       * Framed device on md and above (≥ 640px).
       * Uses real phone aspect (≈ 9/19.5), subtle 3D tilt on pointer move.
       */}
      <motion.div
        ref={frameRef}
        onMouseMove={handleMouseMove}
        onMouseLeave={handleMouseLeave}
        style={{
          zoom,
          boxShadow: PHONE_SHADOW,
          rotateX: reduceMotion ? 0 : rotX,
          rotateY: reduceMotion ? 0 : rotY,
          transformStyle: 'preserve-3d',
          perspective: 1200,
        }}
        className="
          story-phone-frame relative hidden sm:flex flex-col overflow-hidden bg-canvas
          rounded-[42px] border-[10px] border-navy
        "
      >
        {/* Status bar */}
        <div className="relative z-10 flex h-[36px] shrink-0 items-center justify-between bg-white px-6 text-[11.5px] font-bold text-navy">
          <span>9:41</span>
          {/* Dynamic Island style pill notch */}
          <span
            className="story-phone-notch absolute left-1/2 top-[6px] h-[6px] w-[72px] -translate-x-1/2 rounded-full bg-navy"
            aria-hidden
          />
          <span className="flex items-center gap-1" aria-hidden>
            <svg width="16" height="10" viewBox="0 0 16 10" fill="currentColor">
              <rect x="0"    y="6" width="3" height="4"  rx="1"/>
              <rect x="4.3"  y="4" width="3" height="6"  rx="1"/>
              <rect x="8.6"  y="2" width="3" height="8"  rx="1"/>
              <rect x="12.9" y="0" width="3" height="10" rx="1"/>
            </svg>
            <svg width="22" height="11" viewBox="0 0 22 11">
              <rect x="0.5" y="0.5" width="18" height="10" rx="3" fill="none" stroke="currentColor"/>
              <rect x="2"   y="2"   width="14" height="7"  rx="1.8" fill="currentColor"/>
              <rect x="19.5" y="3.5" width="2" height="4"  rx="1" fill="currentColor"/>
            </svg>
          </span>
        </div>

        <AppBar />

        {inner}
      </motion.div>
    </>
  )
}
