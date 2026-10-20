import { useState } from 'react'
import { Link, useNavigate, useLocation } from 'react-router-dom'
import { motion } from 'framer-motion'
import { ShieldCheck, Loader2 } from 'lucide-react'
import { useAuth } from '../context/AuthContext.jsx'

export default function Login() {
  const { login } = useAuth()
  const navigate = useNavigate()
  const location = useLocation()
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  const handleSubmit = async (e) => {
    e.preventDefault()
    setError('')
    setLoading(true)
    try {
      await login(email, password)
      navigate('/dashboard')
    } catch (err) {
      setError(err?.response?.data?.detail || 'Login failed. Please check your credentials.')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="min-h-[80vh] flex items-center justify-center px-4">
      <motion.div initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }} className="glass-panel p-8 w-full max-w-md">
        <div className="flex items-center gap-2 justify-center mb-6">
          <ShieldCheck className="text-brand-500" size={28} />
          <span className="font-bold text-xl">SecureHire AI</span>
        </div>
        <h1 className="text-xl font-semibold text-center mb-1">Welcome back</h1>
        <p className="text-sm text-slate-400 text-center mb-6">Log in to save analyses and track your skills.</p>
        {new URLSearchParams(location.search).get('reason') === 'session-expired' && (
          <div className="text-sm text-amber-200 bg-amber-500/10 border border-amber-500/20 rounded-lg px-4 py-3 mb-4">
            Your previous session expired or was created by a different local configuration. Please log in again to refresh your session.
          </div>
        )}

        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="text-xs text-slate-400 mb-1.5 block">Email</label>
            <input type="email" required className="input-field" value={email} onChange={(e) => setEmail(e.target.value)} placeholder="you@example.com" />
          </div>
          <div>
            <label className="text-xs text-slate-400 mb-1.5 block">Password</label>
            <input type="password" required className="input-field" value={password} onChange={(e) => setPassword(e.target.value)} placeholder="••••••••" />
          </div>
          {error && <div className="text-sm text-red-400 bg-red-500/10 border border-red-500/20 rounded-lg px-4 py-2.5">{error}</div>}
          <button type="submit" disabled={loading} className="btn-primary w-full py-3">
            {loading ? <Loader2 className="animate-spin" size={18} /> : 'Log In'}
          </button>
        </form>

        <p className="text-sm text-slate-400 text-center mt-6">
          Don't have an account? <Link to="/signup" className="text-brand-400 hover:underline">Sign up</Link>
        </p>
      </motion.div>
    </div>
  )
}
