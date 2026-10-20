import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { motion, AnimatePresence } from 'framer-motion'
import {
  ShieldCheck, ShieldAlert, ShieldQuestion, Loader2, Bookmark,
  ArrowRight, Sparkles, Building2,
} from 'lucide-react'
import { analyzeJob, saveJob } from '../api/client'
import { useAuth } from '../context/AuthContext.jsx'
import GeminiCompanyResearch from '../components/GeminiCompanyResearch.jsx'

const SAMPLE_FAKE = {
  title: 'Data Entry Intern',
  company: 'Quick Earn Solutions',
  email: 'hr.hiring123@gmail.com',
  text: `Immediate joining required!!! We are hiring Data Entry Interns across India, no interview required.
Earn up to Rs. 90,000 per week working from home! No experience needed, guaranteed placement!
Send your Aadhar card and a registration fee of Rs. 999 to confirm your seat. Limited seats, apply now!`,
}

const RISK_CONFIG = {
  Low: { icon: ShieldCheck, label: 'LOW RISK', color: 'text-emerald-400', bg: 'from-emerald-500/20 to-transparent', ring: 'ring-emerald-500/30' },
  Medium: { icon: ShieldQuestion, label: 'MEDIUM RISK', color: 'text-amber-400', bg: 'from-amber-500/20 to-transparent', ring: 'ring-amber-500/30' },
  High: { icon: ShieldAlert, label: 'HIGH RISK', color: 'text-red-400', bg: 'from-red-500/20 to-transparent', ring: 'ring-red-500/30' },
}

// Short, plain-language reassurance/warning lines derived from the
// actual API response — never hardcoded per-example, always driven by
// what top_features and company_intelligence genuinely say.
function buildQuickPoints(result) {
  const points = []
  const riskFeatures = result.top_features.filter((f) => f.direction === 'increases_risk')
  const safeFeatures = result.top_features.filter((f) => f.direction === 'decreases_risk')

  if (riskFeatures.length === 0) {
    points.push({ ok: true, text: 'No major scam indicators detected' })
  } else {
    riskFeatures.slice(0, 3).forEach((f) => points.push({ ok: false, text: f.description }))
  }
  if (safeFeatures.length > 0 && riskFeatures.length === 0) {
    safeFeatures.slice(0, 2).forEach((f) => points.push({ ok: true, text: f.description }))
  }
  return points.slice(0, 3)
}

export default function AnalyzeJob() {
  const { isAuthenticated } = useAuth()
  const navigate = useNavigate()
  const [title, setTitle] = useState('')
  const [companyName, setCompanyName] = useState('')
  const [companyWebsite, setCompanyWebsite] = useState('')
  const [sourceUrl, setSourceUrl] = useState('')
  const [contactEmail, setContactEmail] = useState('')
  const [location, setLocation] = useState('')
  const [rawText, setRawText] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [result, setResult] = useState(null)
  const [saved, setSaved] = useState(false)

  const fillSample = () => {
    setTitle(SAMPLE_FAKE.title)
    setCompanyName(SAMPLE_FAKE.company)
    setContactEmail(SAMPLE_FAKE.email)
    setRawText(SAMPLE_FAKE.text)
    setCompanyWebsite('')
    setLocation('Remote')
  }

  const handleAnalyze = async (e) => {
    e.preventDefault()
    setError('')
    setResult(null)
    setSaved(false)
    if (rawText.trim().length < 30) {
      setError('Please paste a longer job description (at least 30 characters).')
      return
    }
    setLoading(true)
    try {
      const { data } = await analyzeJob({
        title: title || 'Untitled Posting',
        raw_text: rawText,
        company_name: companyName || null,
        company_website: companyWebsite || null,
        contact_email: contactEmail || null,
        location: location || null,
        source_url: sourceUrl || null,
      })
      setResult(data)
    } catch (err) {
      setError(err?.response?.data?.detail || 'Something went wrong analyzing this posting. Please try again.')
    } finally {
      setLoading(false)
    }
  }

  const handleSave = async () => {
    if (!isAuthenticated || !result) return
    try {
      await saveJob(result.job_id)
      setSaved(true)
    } catch { /* non-critical for the demo */ }
  }

  const risk = result ? RISK_CONFIG[result.risk_category] : null
  const RiskIcon = risk?.icon

  return (
    <div className="max-w-3xl mx-auto px-4 sm:px-6 lg:px-8 py-14">
      <div className="text-center mb-10">
        <div className="eyebrow mx-auto mb-4"><Sparkles size={14}/> AI-assisted job safety check</div>
        <h1 className="text-4xl font-extrabold tracking-tight">Is this job safe?</h1>
        <p className="text-slate-400 mt-3 text-lg">
          Paste a job posting and SecureHire AI will check it for potential scam indicators. Your result is saved to your account history automatically.
        </p>
      </div>

      {/* FORM */}
      <form onSubmit={handleAnalyze} className="glass-panel p-6 sm:p-8 space-y-4">
        <div className="grid sm:grid-cols-2 gap-4">
          <div>
            <label className="text-xs text-slate-400 mb-1.5 block">Job Title</label>
            <input className="input-field" placeholder="e.g. Data Engineer Intern" value={title} onChange={(e) => setTitle(e.target.value)} />
          </div>
          <div>
            <label className="text-xs text-slate-400 mb-1.5 block">Company Name</label>
            <input className="input-field" placeholder="e.g. Infosys" value={companyName} onChange={(e) => setCompanyName(e.target.value)} />
          </div>
          <div>
            <label className="text-xs text-slate-400 mb-1.5 block">Company Website (optional)</label>
            <input className="input-field" placeholder="https://company.com" value={companyWebsite} onChange={(e) => setCompanyWebsite(e.target.value)} />
          </div>
          <div>
            <label className="text-xs text-slate-400 mb-1.5 block">Source Website <span className="text-slate-500">(where you found this job)</span></label>
            <input type="url" className="input-field" placeholder="https://linkedin.com/jobs/..." value={sourceUrl} onChange={(e) => setSourceUrl(e.target.value)} />
          </div>
          <div>
            <label className="text-xs text-slate-400 mb-1.5 block">Recruiter Email (optional)</label>
            <input className="input-field" placeholder="careers@company.com" value={contactEmail} onChange={(e) => setContactEmail(e.target.value)} />
          </div>
          <div>
            <label className="text-xs text-slate-400 mb-1.5 block">Location (optional)</label>
            <input className="input-field" placeholder="e.g. Bangalore, India / Remote" value={location} onChange={(e) => setLocation(e.target.value)} />
          </div>
        </div>
        <div>
          <div className="flex items-center justify-between mb-1.5">
            <label className="text-xs text-slate-400">Full Job Description</label>
            <button type="button" onClick={fillSample} className="text-xs text-brand-400 hover:text-brand-300">
              Try a sample fake posting →
            </button>
          </div>
          <textarea
            className="input-field min-h-[200px] resize-y"
            placeholder="Paste the full job description text here..."
            value={rawText}
            onChange={(e) => setRawText(e.target.value)}
          />
        </div>
        {error && (
          <div className="text-sm text-red-400 bg-red-500/10 border border-red-500/20 rounded-lg px-4 py-2.5">
            {error}
          </div>
        )}
        <button type="submit" disabled={loading} className="btn-primary w-full py-3.5 text-base">
          {loading ? <><Loader2 className="animate-spin" size={18} /> Analyzing...</> : 'Analyze Job'}
        </button>
      </form>

      {/* SIMPLE RESULT */}
      <AnimatePresence mode="wait">
        {result && risk && (
          <motion.div
            key={result.job_id}
            initial={{ opacity: 0, y: 16 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0 }}
            className={`glass-panel mt-6 p-8 text-center bg-gradient-to-br ${risk.bg} ring-1 ${risk.ring}`}
          >
            <p className="text-slate-400 text-sm">{companyName || 'Unknown Company'}</p>
            <h2 className="text-xl font-bold mb-5">{title || 'Untitled Posting'}</h2>
            {result.source_url && <a className="text-brand-400 text-xs hover:underline inline-block mb-3" href={result.source_url.startsWith('http') ? result.source_url : `https://${result.source_url}`} target="_blank" rel="noreferrer">View original job source ↗</a>}

            <div className={`inline-flex items-center gap-2 text-sm font-bold tracking-wide ${risk.color}`}>
              <RiskIcon size={20} /> {risk.label}
            </div>

            <div className="mt-4">
              <div className="text-5xl font-extrabold">{result.fraud_probability}%</div>
              <div className="text-slate-500 text-sm mt-1">Estimated scam probability</div>
            </div>

            <div className="mt-6 space-y-2 text-left max-w-sm mx-auto">
              {buildQuickPoints(result).map((p, i) => (
                <div key={i} className="flex items-start gap-2 text-sm">
                  <span className={p.ok ? 'text-emerald-400' : 'text-red-400'}>{p.ok ? '✓' : '⚠'}</span>
                  <span className="text-slate-300">{p.text}</span>
                </div>
              ))}
            </div>

            <div className="mt-8 flex flex-col sm:flex-row gap-3 justify-center">
              <button onClick={() => navigate(`/analysis/${result.job_id}`)} className="btn-primary px-5 py-2.5">
                View Full Analysis <ArrowRight size={16} />
              </button>
              <button
                onClick={() => navigate('/company-check', { state: { companyName, companyWebsite } })}
                className="btn-secondary px-5 py-2.5"
              >
                <Building2 size={16} /> Check Company
              </button>
              {isAuthenticated && (
                <button onClick={handleSave} className="btn-secondary px-5 py-2.5">
                  <Bookmark size={16} className={saved ? 'fill-brand-400 text-brand-400' : ''} />
                  {saved ? 'Saved' : 'Save Analysis'}
                </button>
              )}
            </div>
            <p className="text-xs muted-text mt-4">This analysis is saved to your SecureHire account automatically.</p>
          </motion.div>
        )}
      </AnimatePresence>

      {/* Gemini Company Intelligence — completely separate from the ML
          fraud result above: independent, on-demand, search-grounded
          company research, not another pass over the job posting text. */}
      {result && (
        <div className="mt-6">
          {companyName.trim() ? (
            <GeminiCompanyResearch
              companyName={companyName}
              companyWebsite={companyWebsite}
              jobTitle={title}
            />
          ) : (
            <div className="glass-panel p-6 border border-violet-500/10 text-center text-sm text-slate-500">
              Add a company name above and re-analyze to research the company with Gemini.
            </div>
          )}
        </div>
      )}
    </div>
  )
}
