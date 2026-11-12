import React, { createContext, useContext } from 'react'
import { createPortal } from 'react-dom'

/**
 * Modals and sheets render into the phone's own overlay layer, so they stay
 * inside the device frame instead of covering the whole browser window.
 * Falls back to document.body if used outside PhoneFrame or before frame mounts.
 */
export const OverlayContext = createContext<HTMLElement | null>(null)

export function Overlay({ children }: { children: React.ReactNode }) {
  const el = useContext(OverlayContext)
  const target = el || (typeof document !== 'undefined' ? document.body : null)
  return target ? createPortal(children, target) : null
}
