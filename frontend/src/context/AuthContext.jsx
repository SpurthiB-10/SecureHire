import { createContext, useContext, useState, useCallback } from 'react'
import { loginUser, registerUser } from '../api/client'

const AuthContext = createContext(null)

export function AuthProvider({ children }) {
  const [user, setUser] = useState(() => {
    // Treat the session as valid only when both the user and token exist.
    // A malformed/stale localStorage entry should never crash the whole app.
    try {
      const token = localStorage.getItem('securehire_token')
      const stored = localStorage.getItem('securehire_user')
      if (!token || !stored) {
        localStorage.removeItem('securehire_token')
        localStorage.removeItem('securehire_user')
        return null
      }
      return JSON.parse(stored)
    } catch {
      localStorage.removeItem('securehire_token')
      localStorage.removeItem('securehire_user')
      return null
    }
  })

  const persistSession = (token, userData) => {
    localStorage.setItem('securehire_token', token)
    localStorage.setItem('securehire_user', JSON.stringify(userData))
    setUser(userData)
  }

  const login = useCallback(async (email, password) => {
    const { data } = await loginUser({ email, password })
    persistSession(data.access_token, data.user)
    return data.user
  }, [])

  const register = useCallback(async (email, password, fullName) => {
    const { data } = await registerUser({ email, password, full_name: fullName })
    persistSession(data.access_token, data.user)
    return data.user
  }, [])

  const logout = useCallback(() => {
    localStorage.removeItem('securehire_token')
    localStorage.removeItem('securehire_user')
    setUser(null)
  }, [])

  return (
    <AuthContext.Provider value={{ user, login, register, logout, isAuthenticated: !!user }}>
      {children}
    </AuthContext.Provider>
  )
}

export function useAuth() {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error('useAuth must be used within AuthProvider')
  return ctx
}
