import { useEffect, useState } from 'react'
import {
  BarChart, Bar, PieChart, Pie, Cell, XAxis, YAxis, CartesianGrid, Tooltip,
  ResponsiveContainer, Legend, LineChart, Line,
} from 'recharts'
import { LayoutDashboard, Loader2, Building2, Workflow, CheckCircle2, XCircle } from 'lucide-react'
import { getFraudTrends, getModelPerformance, getCompanyTrust, getPipelineHealth } from '../api/client'

const COLORS = ['#16a34a', '#f59e0b', '#dc2626']
const BRAND = '#3380ff'

function ChartCard({ title, children, empty }) {
  return (
    <div className="glass-panel p-6">
      <h3 className="font-semibold mb-4">{title}</h3>
      {empty ? (
        <div className="h-52 flex items-center justify-center text-sm text-slate-500">
          Not enough data yet — analyze a few postings to populate this chart.
        </div>
      ) : children}
    </div>
  )
}

export default function Dashboard() {
  const [trends, setTrends] = useState(null)
  const [perf, setPerf] = useState(null)
  const [companyTrust, setCompanyTrust] = useState(null)
  const [pipelineHealth, setPipelineHealth] = useState(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    Promise.all([getFraudTrends(), getModelPerformance(), getCompanyTrust(), getPipelineHealth()])
      .then(([t, p, ct, ph]) => {
        setTrends(t.data)
        setPerf(p.data)
        setCompanyTrust(ct.data)
        setPipelineHealth(ph.data)
      })
      .catch(() => {})
      .finally(() => setLoading(false))
  }, [])

  if (loading) {
    return (
      <div className="flex justify-center py-32 text-slate-500">
        <Loader2 className="animate-spin mr-2" /> Loading analytics...
      </div>
    )
  }

  const fakeVsReal = trends
    ? Object.entries(trends.fake_vs_real).map(([name, value]) => ({ name, value }))
    : []
  const byLocation = trends
    ? Object.entries(trends.fraud_by_location).map(([name, value]) => ({ name, value })).slice(0, 8)
    : []
  const byCategory = trends
    ? Object.entries(trends.fraud_by_category).map(([name, value]) => ({ name, value }))
    : []
  const confidenceDist = trends
    ? Object.entries(trends.model_confidence_distribution).map(([name, value]) => ({ name, value }))
    : []
  const topKeywords = trends?.top_scam_keywords || []
  const skillTrends = trends?.skill_demand_trends || []
  const jobsPerDay = trends?.jobs_per_day || []

  const suspiciousCompanies = companyTrust?.top_suspicious_companies || []
  const recruiterDomainDist = companyTrust?.recruiter_domain_distribution || []
  const websiteVerificationDist = companyTrust
    ? Object.entries(companyTrust.website_verification_distribution).map(([name, value]) => ({ name, value }))
    : []

  const recentRuns = pipelineHealth?.recent_runs || []

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-12">
      <div className="mb-8">
        <h1 className="text-3xl font-bold flex items-center gap-2">
          <LayoutDashboard className="text-brand-500" /> Platform Analytics (Admin)
        </h1>
        <p className="text-slate-400 mt-2">Internal ML/DE metrics — not shown to normal users. Aggregate insights across every posting analyzed on the platform.</p>
      </div>

      {perf?.status === 'ok' && (
        <div className="glass-panel p-5 mb-8 flex flex-wrap gap-6 items-center">
          <span className="text-sm text-slate-400">Live model: <span className="text-white font-medium">{perf.model_version}</span></span>
          {perf.metrics?.ensemble && (
            <>
              <span className="text-sm">F1: <span className="text-brand-400 font-semibold">{(perf.metrics.ensemble.f1 * 100).toFixed(1)}%</span></span>
              <span className="text-sm">Precision: <span className="text-brand-400 font-semibold">{(perf.metrics.ensemble.precision * 100).toFixed(1)}%</span></span>
              <span className="text-sm">Recall: <span className="text-brand-400 font-semibold">{(perf.metrics.ensemble.recall * 100).toFixed(1)}%</span></span>
            </>
          )}
        </div>
      )}

      <div className="grid lg:grid-cols-2 gap-6">
        <ChartCard title="Fake vs Real Jobs" empty={fakeVsReal.every((d) => d.value === 0)}>
          <ResponsiveContainer width="100%" height={260}>
            <PieChart>
              <Pie data={fakeVsReal} dataKey="value" nameKey="name" cx="50%" cy="50%" outerRadius={90} label>
                {fakeVsReal.map((_, i) => <Cell key={i} fill={COLORS[i % COLORS.length]} />)}
              </Pie>
              <Tooltip contentStyle={{ background: '#0f172a', border: '1px solid #1e293b', borderRadius: 8 }} />
              <Legend />
            </PieChart>
          </ResponsiveContainer>
        </ChartCard>

        <ChartCard title="Jobs Analyzed Per Day" empty={jobsPerDay.length === 0}>
          <ResponsiveContainer width="100%" height={260}>
            <LineChart data={jobsPerDay}>
              <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
              <XAxis dataKey="date" tick={{ fontSize: 11, fill: '#94a3b8' }} />
              <YAxis tick={{ fontSize: 11, fill: '#94a3b8' }} allowDecimals={false} />
              <Tooltip contentStyle={{ background: '#0f172a', border: '1px solid #1e293b', borderRadius: 8 }} />
              <Line type="monotone" dataKey="count" stroke={BRAND} strokeWidth={2} dot={{ r: 3 }} />
            </LineChart>
          </ResponsiveContainer>
        </ChartCard>

        <ChartCard title="Fraud by Location" empty={byLocation.length === 0}>
          <ResponsiveContainer width="100%" height={260}>
            <BarChart data={byLocation}>
              <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
              <XAxis dataKey="name" tick={{ fontSize: 11, fill: '#94a3b8' }} angle={-20} textAnchor="end" height={60} />
              <YAxis tick={{ fontSize: 11, fill: '#94a3b8' }} />
              <Tooltip contentStyle={{ background: '#0f172a', border: '1px solid #1e293b', borderRadius: 8 }} />
              <Bar dataKey="value" fill="#dc2626" radius={[6, 6, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </ChartCard>

        <ChartCard title="Fraud by Job Category" empty={byCategory.length === 0}>
          <ResponsiveContainer width="100%" height={260}>
            <BarChart data={byCategory}>
              <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
              <XAxis dataKey="name" tick={{ fontSize: 11, fill: '#94a3b8' }} />
              <YAxis tick={{ fontSize: 11, fill: '#94a3b8' }} />
              <Tooltip contentStyle={{ background: '#0f172a', border: '1px solid #1e293b', borderRadius: 8 }} />
              <Bar dataKey="value" fill={BRAND} radius={[6, 6, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </ChartCard>

        <ChartCard title="Model Confidence Distribution" empty={confidenceDist.every((d) => d.value === 0)}>
          <ResponsiveContainer width="100%" height={260}>
            <BarChart data={confidenceDist}>
              <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
              <XAxis dataKey="name" tick={{ fontSize: 11, fill: '#94a3b8' }} />
              <YAxis tick={{ fontSize: 11, fill: '#94a3b8' }} />
              <Tooltip contentStyle={{ background: '#0f172a', border: '1px solid #1e293b', borderRadius: 8 }} />
              <Bar dataKey="value" fill="#a855f7" radius={[6, 6, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </ChartCard>

        <ChartCard title="Most Common Scam Keywords" empty={topKeywords.length === 0}>
          <ResponsiveContainer width="100%" height={260}>
            <BarChart data={topKeywords} layout="vertical">
              <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
              <XAxis type="number" tick={{ fontSize: 11, fill: '#94a3b8' }} />
              <YAxis type="category" dataKey="keyword" tick={{ fontSize: 11, fill: '#94a3b8' }} width={140} />
              <Tooltip contentStyle={{ background: '#0f172a', border: '1px solid #1e293b', borderRadius: 8 }} />
              <Bar dataKey="count" fill="#f59e0b" radius={[0, 6, 6, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </ChartCard>

        <ChartCard title="Skill Demand Trends" empty={skillTrends.length === 0}>
          <ResponsiveContainer width="100%" height={260}>
            <BarChart data={skillTrends}>
              <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
              <XAxis dataKey="skill" tick={{ fontSize: 11, fill: '#94a3b8' }} angle={-20} textAnchor="end" height={60} />
              <YAxis tick={{ fontSize: 11, fill: '#94a3b8' }} />
              <Tooltip contentStyle={{ background: '#0f172a', border: '1px solid #1e293b', borderRadius: 8 }} />
              <Bar dataKey="postings_count" fill="#16a34a" radius={[6, 6, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </ChartCard>

        <ChartCard title="Recruiter Email Domain Distribution" empty={recruiterDomainDist.length === 0}>
          <ResponsiveContainer width="100%" height={260}>
            <PieChart>
              <Pie data={recruiterDomainDist} dataKey="count" nameKey="category" cx="50%" cy="50%" outerRadius={90} label>
                {recruiterDomainDist.map((_, i) => <Cell key={i} fill={[BRAND, '#f59e0b'][i % 2]} />)}
              </Pie>
              <Tooltip contentStyle={{ background: '#0f172a', border: '1px solid #1e293b', borderRadius: 8 }} />
              <Legend />
            </PieChart>
          </ResponsiveContainer>
        </ChartCard>

        <ChartCard title="Company Website Verification (Gemini)" empty={websiteVerificationDist.length === 0}>
          <ResponsiveContainer width="100%" height={260}>
            <BarChart data={websiteVerificationDist}>
              <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
              <XAxis dataKey="name" tick={{ fontSize: 11, fill: '#94a3b8' }} />
              <YAxis tick={{ fontSize: 11, fill: '#94a3b8' }} allowDecimals={false} />
              <Tooltip contentStyle={{ background: '#0f172a', border: '1px solid #1e293b', borderRadius: 8 }} />
              <Bar dataKey="value" fill="#22c55e" radius={[6, 6, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </ChartCard>
      </div>

      {/* --- Company Trust section --- */}
      <div className="mt-10 mb-6">
        <h2 className="text-xl font-bold flex items-center gap-2">
          <Building2 className="text-brand-500" size={22} /> Company Trust
        </h2>
      </div>
      <div className="glass-panel p-6">
        {suspiciousCompanies.length === 0 ? (
          <div className="text-sm text-slate-500 py-6 text-center">No company data yet — analyze a few postings first.</div>
        ) : (
          <div className="space-y-2">
            {suspiciousCompanies.map((c) => (
              <div key={c.name} className="flex items-center justify-between py-2.5 border-b border-white/5 last:border-0">
                <span className="font-medium text-sm">{c.name}</span>
                <div className="flex items-center gap-4 text-xs text-slate-400">
                  <span>Trust score: <span className="text-white">{c.trust_score}</span></span>
                  <span>Reports: <span className="text-white">{c.fraud_report_count}</span></span>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* --- Pipeline Health section --- */}
      <div className="mt-10 mb-6">
        <h2 className="text-xl font-bold flex items-center gap-2">
          <Workflow className="text-brand-500" size={22} /> Data Pipeline Health
        </h2>
        <p className="text-slate-400 text-sm mt-1">
          Runs of the warehouse ETL pipeline (<code className="text-xs bg-white/5 px-1.5 py-0.5 rounded">pipelines/run_pipeline_jobs.py</code>).
        </p>
      </div>
      <div className="glass-panel p-6">
        {recentRuns.length === 0 ? (
          <div className="text-sm text-slate-500 py-6 text-center">
            No pipeline runs recorded yet — run <code className="text-xs bg-white/5 px-1.5 py-0.5 rounded">python pipelines/run_pipeline_jobs.py</code> to populate this.
          </div>
        ) : (
          <div className="space-y-2">
            {recentRuns.map((r) => (
              <div key={r.run_id} className="flex items-center justify-between py-2.5 border-b border-white/5 last:border-0 text-sm">
                <div className="flex items-center gap-2">
                  {r.status === 'success' ? <CheckCircle2 size={16} className="text-emerald-400" /> : <XCircle size={16} className="text-red-400" />}
                  <span className="font-mono text-xs text-slate-400">{r.run_id}</span>
                </div>
                <div className="flex items-center gap-4 text-xs text-slate-400">
                  <span>Ingested: <span className="text-white">{r.rows_ingested}</span></span>
                  <span>Cleaned: <span className="text-white">{r.rows_cleaned}</span></span>
                  <span>Duplicates: <span className="text-white">{r.duplicates_removed}</span></span>
                  <span>Duration: <span className="text-white">{r.pipeline_duration_seconds?.toFixed(2)}s</span></span>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}
