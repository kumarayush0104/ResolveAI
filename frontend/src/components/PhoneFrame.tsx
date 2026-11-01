import React, { useEffect, useRef, useState } from 'react'
import { useLocation } from 'react-router-dom'
import { OverlayContext } from './Overlay'
import { AppBar } from './AppBar'
import { TabBar } from './TabBar'
import { ToastProvider } from './Toast'
import { useAuth } from '../lib/auth'

/**
 * The device. On wide screens it is a phone mockup floating on the site;
 * on a real phone-sized screen the frame drops away and the app fills the screen.
 */
export function PhoneFrame({ children, zoom = 1 }: { children: React.ReactNode; zoom?: number }) {
  const [overlayEl, setOverlayEl] = useState<HTMLElement | null>(null)
  const scrollRef = useRef<HTMLDivElement>(null)
  const { pathname } = useLocation()
  const { isLoading, token } = useAuth()

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: 0 })
  }, [pathname])

  return (
    <div
      style={{ zoom }}
      className="
        relative flex flex-col overflow-hidden bg-canvas
        w-[396px] h-[min(852px,calc(100vh-32px))]
        rounded-[56px] border-[13px] border-navy shadow-phone
        max-sm:w-full max-sm:h-[100dvh] max-sm:rounded-none max-sm:border-0 max-sm:shadow-none
      "
    >
      <OverlayContext.Provider value={overlayEl}>
      <ToastProvider>
        {/* Status bar + notch (device chrome only) */}
        <div className="relative z-10 flex h-[38px] shrink-0 items-center justify-between bg-white px-7 text-[12px] font-bold text-navy max-sm:hidden">
          <span>9:41</span>
          <span className="absolute left-1/2 top-[7px] h-[7px] w-[88px] -translate-x-1/2 rounded-full bg-navy" aria-hidden />
          <span className="flex items-center gap-1" aria-hidden>
            <svg width="16" height="10" viewBox="0 0 16 10" fill="currentColor"><rect x="0" y="6" width="3" height="4" rx="1"/><rect x="4.3" y="4" width="3" height="6" rx="1"/><rect x="8.6" y="2" width="3" height="8" rx="1"/><rect x="12.9" y="0" width="3" height="10" rx="1"/></svg>
            <svg width="22" height="11" viewBox="0 0 22 11"><rect x="0.5" y="0.5" width="18" height="10" rx="3" fill="none" stroke="currentColor"/><rect x="2" y="2" width="14" height="7" rx="1.8" fill="currentColor"/><rect x="19.5" y="3.5" width="2" height="4" rx="1" fill="currentColor"/></svg>
          </span>
        </div>

        <AppBar />

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

        {/* Sheets and modals mount here so they stay inside the device */}
        <div ref={setOverlayEl} className="pointer-events-none absolute inset-0 z-40" />
      </ToastProvider>
      </OverlayContext.Provider>
    </div>
  )
}
