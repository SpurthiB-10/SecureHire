import { useEffect, useState } from 'react'
import { useParams, Link } from 'react-router-dom'
import { motion } from 'framer-motion'
import {
  Loader2, AlertTriangle, CheckCircle2, TrendingUp, Building2, Sparkles,
  MessageCircle, Send, ArrowLeft,
} from 'lucide-react'
import { getFullAnalysis, sendChatMessage } from '../api/client'
import RiskBadge from '../components/RiskBadge.jsx'

export default function FullAnalysis() {
  const { jobId } = useParams()
  const [result, setResult] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  const [chatOpen, setChatOpen] = useState(false)
  const [chatMessages, setChatMessages] = useState([])
  const [chatInput, setChatInput] = useState('')
  const [chatLoading, setChatLoading] = useState(false)

  useEffect(() => {
    getFullAnalysis(jobId)
      .then(({ data }) => setResult(data))
      .catch((err) => setError(err?.response?.data?.detail || 'Could not load this analysis.'))
      .finally(() => setLoading(false))
  }, [jobId])

  const handleChatSend = async () => {
    if (!chatInput.trim()) return
    const userMsg = chatInput
    setChatMessages((m) => [...m, { role: 'user', text: userMsg }])
    setChatInput('')
    setChatLoading(true)
    try {
      const { data } = await sendChatMessage(userMsg, jobId)
      setChatMessages((m) => [...m, { role: 'assistant', text: data.reply }])
    } catch {
      setChatMessages((m) => [...m, { role: 'assistant', text: 'Sorry, I had trouble responding — please try again.' }])
    } finally {
      setChatLoading(false)
    }
  }

  if (loading) {
    return <div className="flex justify-center py-32 text-slate-500"><Loader2 className="animate-spin mr-2" /> Loading analysis...</div>
  }

  if (error || !result) {
    return (
      <div className="max-w-md mx-auto px-4 py-24 text-center">
        <p className="text-slate-400">{error || 'Analysis not found.'}</p>
        <Link to="/analyze" className="btn-primary inline-flex mt-6 px-6 py-3">Analyze a Job</Link>
      </div>
    )
  }

  const ci = result.company_intelligence

  return (
    <div className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 py-12">
      <Link to="/analyze" className="text-sm text-slate-400 hover:text-white inline-flex items-center gap-1.5 mb-6">
        <ArrowLeft size={15} /> Back to Analyze
      </Link>

      <div className="mb-8">
        <p className="muted-text">{result.company_name || 'Unknown Company'}</p>
        <h1 className="text-2xl font-bold">{result.title}</h1>
        {result.source_url && <a className="text-brand-500 text-sm hover:underline inline-block mt-2" href={result.source_url.startsWith('http') ? result.source_url : `https://${result.source_url}`} target="_blank" rel="noreferrer">View original job source ↗</a>}
      </div>

      <div className="space-y-6">
        {/* Fraud Risk */}
        <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} className="glass-panel p-6">
          <div className="flex items-center justify-between mb-4">
            <h2 className="font-semibold text-lg">Fraud Risk</h2>
            <RiskBadge category={result.risk_category} size="lg" />
          </div>
          <div className="grid grid-cols-2 sm:grid-cols-3 gap-4 mb-4">
            <div>
              <div className="text-slate-500 text-xs mb-1">Fraud Probability</div>
              <div className="text-2xl font-bold">{result.fraud_probability}%</div>
            </div>
            <div>
              <div className="text-slate-500 text-xs mb-1">Model Confidence</div>
              <div className="text-2xl font-bold">{result.confidence}%</div>
            </div>
            <div>
              <div className="text-slate-500 text-xs mb-1">Model Version</div>
              <div className="text-sm font-medium mt-2">{result.model_version}</div>
            </div>
          </div>
          <div className="pt-4 border-t border-white/10">
            <h3 className="text-sm font-semibold text-slate-300 mb-2">Why this score?</h3>
            <p className="text-sm text-slate-400 leading-relaxed">{result.explanation_text}</p>
          </div>
        </motion.div>

        {/* Risk Indicators */}
        {result.top_features?.length > 0 && (
          <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.05 }} className="glass-panel p-6">
            <h2 className="font-semibold text-lg flex items-center gap-2 mb-4">
              <TrendingUp size={18} className="text-brand-400" /> Risk Indicators
            </h2>
            <div className="space-y-2.5">
              {result.top_features.map((f) => (
                <div key={f.feature} className="flex items-start gap-2.5">
                  {f.direction === 'increases_risk'
                    ? <AlertTriangle size={16} className="text-red-400 mt-0.5 shrink-0" />
                    : <CheckCircle2 size={16} className="text-emerald-400 mt-0.5 shrink-0" />}
                  <span className="text-sm text-slate-300">{f.description}</span>
                </div>
              ))}
            </div>
          </motion.div>
        )}

        {/* Detected Skills */}
        {result.skills?.length > 0 && (
          <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.1 }} className="glass-panel p-6">
            <h2 className="font-semibold text-lg mb-4">Detected Skills</h2>
            <div className="flex flex-wrap gap-2">
              {result.skills.map((s) => (
                <span key={s.skill_name} className="text-xs px-3 py-1.5 rounded-full bg-white/5 border border-white/10">
                  {s.skill_name} <span className="text-slate-500">· {s.demand_level} demand</span>
                </span>
              ))}
            </div>
          </motion.div>
        )}

        {/* Company Trust Signals */}
        <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.15 }} className="glass-panel p-6">
          <h2 className="font-semibold text-lg flex items-center gap-2 mb-4">
            <Building2 size={18} className="text-brand-400" /> Company Trust Signals
          </h2>
          <div className="grid grid-cols-2 gap-4 text-sm">
            <div>
              <div className="text-slate-500 text-xs mb-1">Trust Score</div>
              <div className="font-semibold text-lg">{result.trust_signals.trust_score}/100</div>
            </div>
            <div>
              <div className="text-slate-500 text-xs mb-1">Domain Age</div>
              <div className="font-semibold">{result.trust_signals.domain_age_days ? `${result.trust_signals.domain_age_days} days` : 'Unknown'}</div>
            </div>
            <div>
              <div className="text-slate-500 text-xs mb-1">Verified Domain</div>
              <div className="font-semibold">{result.trust_signals.has_verified_domain ? 'Yes' : 'Not verified'}</div>
            </div>
            <div>
              <div className="text-slate-500 text-xs mb-1">Community Reports</div>
              <div className="font-semibold">{result.trust_signals.fraud_report_count}</div>
            </div>
          </div>
        </motion.div>

        {/* Quick company signal, computed automatically at analysis time.
            For the full, search-grounded, source-cited research report,
            see the Company Check link below (a separate, on-demand,
            deeper capability — see GeminiCompanyResearch.jsx). */}
        <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.2 }} className="glass-panel p-6">
          <div className="flex items-center justify-between mb-4">
            <h2 className="font-semibold text-lg flex items-center gap-2">
              <Sparkles size={18} className="text-brand-400" /> Company Intelligence
            </h2>
            {result.company_name && (
              <Link
                to="/company-check"
                state={{ companyName: result.company_name }}
                className="btn-secondary text-xs py-1.5 px-3 whitespace-nowrap"
              >
                Full Company Research
              </Link>
            )}
          </div>
          {ci.status === 'ok' ? (
            <div className="space-y-3 text-sm">
              <p className="text-slate-300">{ci.company_summary}</p>
              {ci.verification_score != null && (
                <div className="text-xs"><span className="text-slate-500">Verification score: </span><span className="font-semibold">{ci.verification_score}/100</span></div>
              )}
              {ci.recommendation && <p className="text-xs text-brand-300 pt-2 border-t border-white/10">{ci.recommendation}</p>}
            </div>
          ) : (
            <p className="text-xs text-slate-500">{ci.error_message || 'Company intelligence is unavailable for this posting.'}</p>
          )}
        </motion.div>

        {/* Contextual AI Assistant */}
        <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.25 }} className="glass-panel p-6">
          <button onClick={() => setChatOpen(!chatOpen)} className="flex items-center gap-2 font-semibold w-full">
            <MessageCircle size={18} className="text-brand-400" /> Ask about this posting
          </button>
          {chatOpen && (
            <div className="mt-4 space-y-3">
              <div className="max-h-64 overflow-y-auto space-y-2.5 pr-1">
                {chatMessages.length === 0 && (
                  <p className="text-xs text-slate-500">Try: "Why is this job suspicious?" or "What skills should I learn for this role?"</p>
                )}
                {chatMessages.map((m, i) => (
                  <div key={i} className={`text-sm rounded-lg px-3.5 py-2.5 max-w-[90%] ${m.role === 'user' ? 'bg-brand-600/30 ml-auto text-right' : 'bg-white/5'}`}>
                    {m.text}
                  </div>
                ))}
                {chatLoading && <Loader2 className="animate-spin text-brand-400" size={16} />}
              </div>
              <div className="flex gap-2">
                <input
                  className="input-field text-sm"
                  placeholder="Ask a question about this job..."
                  value={chatInput}
                  onChange={(e) => setChatInput(e.target.value)}
                  onKeyDown={(e) => e.key === 'Enter' && handleChatSend()}
                />
                <button onClick={handleChatSend} className="btn-primary px-3.5"><Send size={16} /></button>
              </div>
            </div>
          )}
        </motion.div>
      </div>
    </div>
  )
}
