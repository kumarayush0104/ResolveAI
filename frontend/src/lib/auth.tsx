import React, { createContext, useContext, useState, useEffect } from 'react'
import { api } from './api'

interface AuthCtx {
  role: string
  token: string | null
  switchRole: (r: string) => Promise<void>
  isLoading: boolean
}

const AuthContext = createContext<AuthCtx>({
  role: 'buyer',
  token: null,
  switchRole: async () => {},
  isLoading: true,
})

export const useAuth = () => useContext(AuthContext)

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [role, setRole] = useState('buyer')
  const [token, setToken] = useState<string | null>(null)
  const [isLoading, setIsLoading] = useState(true)

  const switchRole = async (r: string) => {
    setIsLoading(true)
    try {
      const data = await api.demoLogin(r)
      setRole(r)
      setToken(data.access_token)
      localStorage.setItem('jwt', data.access_token)
      localStorage.setItem('role', r)
    } catch (err) {
      console.error('Failed to authenticate demo user', err)
    } finally {
      setIsLoading(false)
    }
  }

  useEffect(() => {
    const saved = localStorage.getItem('role') || 'buyer'
    // Restore cached token immediately so pages can make API calls without waiting
    const cachedToken = localStorage.getItem('jwt')
    if (cachedToken) {
      setToken(cachedToken)
      setRole(saved)
      setIsLoading(false)
    }
    // Always refresh in background
    switchRole(saved)
  }, [])

  return (
    <AuthContext.Provider value={{ role, token, switchRole, isLoading }}>
      {isLoading && !token ? (
        <div className="min-h-screen bg-surface flex items-center justify-center">
          <div className="flex flex-col items-center gap-3">
            <div className="w-8 h-8 border-2 border-pp-blue border-t-transparent rounded-full animate-spin" />
            <span className="text-sm text-ink-soft">Connecting to ResolveAI...</span>
          </div>
        </div>
      ) : (
        children
      )}
    </AuthContext.Provider>
  )
}
