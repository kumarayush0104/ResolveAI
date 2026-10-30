import React from 'react'
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import { AnimatePresence } from 'framer-motion'
import { AuthProvider } from './lib/auth'
import { ToastProvider } from './components/Toast'
import { TopBar } from './components/TopBar'
import { Landing } from './pages/Landing'
import { Checkout } from './pages/Checkout'
import { CasePage } from './pages/CasePage'
import { Console } from './pages/Console'

export default function App() {
  return (
    <BrowserRouter>
      <AuthProvider>
        <ToastProvider>
          <div className="min-h-screen bg-surface flex flex-col">
            <TopBar />
            <main className="flex-1">
              <AnimatePresence mode="wait">
                <Routes>
                  <Route path="/" element={<Landing />} />
                  <Route path="/checkout" element={<Checkout />} />
                  <Route path="/cases/:id" element={<CasePage />} />
                  <Route path="/console" element={<Console />} />
                  <Route path="*" element={<Navigate to="/" replace />} />
                </Routes>
              </AnimatePresence>
            </main>
          </div>
        </ToastProvider>
      </AuthProvider>
    </BrowserRouter>
  )
}
