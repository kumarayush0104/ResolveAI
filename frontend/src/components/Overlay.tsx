import React, { createContext, useContext } from 'react'
import { createPortal } from 'react-dom'

/**
 * Modals and sheets render into the phone's own overlay layer, so they stay
 * inside the device frame instead of covering the whole browser window.
 */
export const OverlayContext = createContext<HTMLElement | null>(null)

export function Overlay({ children }: { children: React.ReactNode }) {
  const el = useContext(OverlayContext)
  return el ? createPortal(children, el) : null
}
