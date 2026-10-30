import React from 'react'
import { BrowserRouter, Routes, Route, Navigate, useLocation } from 'react-router-dom'
import { AnimatePresence, motion } from 'framer-motion'
import { AuthProvider } from './lib/auth'
import { ToastProvider } from './components/Toast'
import { TopBar } from './components/TopBar'
import { Landing } from './pages/Landing'
import { Checkout } from './pages/Checkout'
import { CasePage } from './pages/CasePage'
import { Console } from './pages/Console'

function PageWrapper({ children }: { children: React.ReactNode }) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, y: -8 }}
      transition={{ duration: 0.2 }}
    >
      {children}
    </motion.div>
  )
}

function AnimatedRoutes() {
  const location = useLocation()
  return (
    <AnimatePresence mode="wait">
      <Routes location={location} key={location.pathname}>
        <Route
          path="/"
          element={
            <PageWrapper>
              <Landing />
            </PageWrapper>
          }
        />
        <Route
          path="/checkout"
          element={
            <PageWrapper>
              <Checkout />
            </PageWrapper>
          }
        />
        <Route
          path="/cases/:id"
          element={
            <PageWrapper>
              <CasePage />
            </PageWrapper>
          }
        />
        <Route
          path="/console"
          element={
            <PageWrapper>
              <Console />
            </PageWrapper>
          }
        />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </AnimatePresence>
  )
}

export default function App() {
  return (
    <BrowserRouter>
      <AuthProvider>
        <ToastProvider>
          <div className="min-h-screen bg-surface flex flex-col">
            <TopBar />
            <main className="flex-1">
              <AnimatedRoutes />
            </main>
          </div>
        </ToastProvider>
      </AuthProvider>
    </BrowserRouter>
  )
}
