import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { ShieldAlert, Loader2, CheckCircle2, BarChart3 } from 'lucide-react'
import { api } from '../api/client'

export default function AdminPanel() {
  const [summary, setSummary] = useState(null)
  const [companies, setCompanies] = useState([])
  const [forbidden, setForbidden] = useState(false)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    Promise.all([
      api.get('/admin/dashboard-summary'),
      api.get('/admin/companies'),
    ])
      .then(([s, c]) => {
        setSummary(s.data)
        setCompanies(c.data)
      })
      .catch((err) => {
        if (err?.response?.status === 403) setForbidden(true)
      })
      .finally(() => setLoading(false))
  }, [])

  const verifyCompany = async (id) => {
    await api.post(`/admin/companies/${id}/verify`)
    const { data } = await api.get('/admin/companies')
    setCompanies(data)
  }

  if (loading) return <div className="flex justify-center py-32 text-slate-500"><Loader2 className="animate-spin mr-2" /> Loading...</div>

  if (forbidden) {
    return (
      <div className="max-w-2xl mx-auto px-4 py-24 text-center">
        <ShieldAlert className="mx-auto text-amber-400 mb-4" size={40} />
        <h1 className="text-xl font-semibold mb-2">Admin access required</h1>
        <p className="text-slate-400 text-sm">
          Your account doesn't have admin privileges. To grant them for a demo, update the user's
          <code className="mx-1 px-2 py-0.5 bg-white/5 rounded">role</code> column to <code className="mx-1 px-2 py-0.5 bg-white/5 rounded">'admin'</code> directly in PostgreSQL.
        </p>
      </div>
    )
  }

  return (
    <div className="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8 py-12">
      <h1 className="text-3xl font-bold flex items-center gap-2 mb-8"><ShieldAlert className="text-brand-500" /> Admin Console</h1>

      <Link to="/admin/analytics" className="btn-secondary inline-flex text-sm py-2 px-4 mb-8">
        <BarChart3 size={16} /> View Platform Analytics (ML/DE internals)
      </Link>

      {summary && (
        <div className="grid sm:grid-cols-4 gap-4 mb-10">
          {[
            ['Jobs analyzed', summary.total_jobs_analyzed],
            ['High risk postings', summary.high_risk_postings],
            ['Pending reports', summary.pending_reports],
            ['Companies tracked', summary.total_companies_tracked],
          ].map(([label, value]) => (
            <div key={label} className="glass-panel p-5">
              <div className="text-2xl font-bold text-brand-400">{value}</div>
              <div className="text-xs text-slate-500 mt-1">{label}</div>
            </div>
          ))}
        </div>
      )}

      <div className="glass-panel p-6">
        <h2 className="font-semibold mb-4">Manage Verified Companies</h2>
        <div className="space-y-2">
          {companies.map((c) => (
            <div key={c.id} className="flex items-center justify-between py-2.5 border-b border-white/5 last:border-0">
              <div>
                <div className="font-medium text-sm">{c.name}</div>
                <div className="text-xs text-slate-500">Trust: {c.trust_score} · Reports: {c.fraud_report_count}</div>
              </div>
              {c.has_verified_domain ? (
                <span className="text-xs text-emerald-400 flex items-center gap-1"><CheckCircle2 size={14} /> Verified</span>
              ) : (
                <button onClick={() => verifyCompany(c.id)} className="btn-secondary text-xs py-1.5 px-3">Verify</button>
              )}
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}
