import React from 'react'
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import { AuthProvider } from './lib/auth'
import { ToastProvider } from './components/Toast'
import { BottomNav } from './components/BottomNav'
import { Landing } from './pages/Landing'
import { Checkout } from './pages/Checkout'
import { CasePage } from './pages/CasePage'
import { Console } from './pages/Console'

function AnimatedRoutes() {
  return (
    <Routes>
      <Route path="/" element={<Landing />} />
      <Route path="/checkout" element={<Checkout />} />
      <Route path="/cases/:id" element={<CasePage />} />
      <Route path="/console" element={<Console />} />
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  )
}

export default function App() {
  return (
    <BrowserRouter>
      <AuthProvider>
        <ToastProvider>
          {/* Outer page: grey bg so mobile shell pops on desktop */}
          <div className="min-h-screen bg-gray-300 flex items-start justify-center">
            <div className="mobile-shell shadow-mobile">
              {/* Scrollable content */}
              <div className="mobile-content">
                <AnimatedRoutes />
              </div>
              {/* Sticky bottom nav inside shell */}
              <BottomNav />
            </div>
          </div>
        </ToastProvider>
      </AuthProvider>
    </BrowserRouter>
  )
}
