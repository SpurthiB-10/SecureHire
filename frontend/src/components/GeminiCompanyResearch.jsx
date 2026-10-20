import { useEffect, useRef, useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import {
  Sparkles, Search, Loader2, ExternalLink, CheckCircle2, HelpCircle,
  AlertTriangle, Globe, RefreshCw, Clock, Info,
} from 'lucide-react'
import { deepResearchCompany } from '../api/client'

function formatCheckedTime(iso) {
  if (!iso) return null
  try {
    return new Date(iso).toLocaleString('en-US', {
      month: 'short', day: 'numeric', year: 'numeric', hour: 'numeric', minute: '2-digit',
    })
  } catch {
    return null
  }
}

// Purely a UX affordance while the single real API call is in flight —
// the underlying request is one call, not three; these are just staged
// status messages so a 5-10s grounded-search request doesn't look frozen.
// The data shown once loading finishes is always the real API response.
const LOADING_PHASES = [
  'Researching company...',
  'Gathering information...',
  'Generating report...',
]

export default function GeminiCompanyResearch({ companyName, companyWebsite, jobTitle, autoRun = false }) {
  const [status, setStatus] = useState('idle') // idle | loading | done | error
  const [phase, setPhase] = useState(0)
  const [report, setReport] = useState(null)
  const [error, setError] = useState('')
  const phaseTimer = useRef(null)

  useEffect(() => () => clearInterval(phaseTimer.current), [])

  // eslint-disable-next-line react-hooks/exhaustive-deps
  useEffect(() => {
    if (autoRun && companyName) runResearch()
  }, [autoRun, companyName])

  const runResearch = async () => {
    setStatus('loading')
    setPhase(0)
    setError('')
    setReport(null)

    phaseTimer.current = setInterval(() => {
      setPhase((p) => Math.min(p + 1, LOADING_PHASES.length - 1))
    }, 2200)

    try {
      const { data } = await deepResearchCompany({
        company_name: companyName,
        company_website: companyWebsite || null,
        job_title: jobTitle || null,
      })
      clearInterval(phaseTimer.current)
      if (data.status === 'unavailable' || data.status === 'error') {
        setStatus('error')
        setError(data.error_message || 'Company research is unavailable right now.')
        return
      }
      // "partial" means we retrieved source links but AI summarization is
      // not configured. Render the honest partial result rather than a blank
      // error panel; never label it as an AI verification.
      setReport(data)
      setStatus('done')
    } catch (err) {
      clearInterval(phaseTimer.current)
      setStatus('error')
      setError(err?.response?.data?.detail || 'Company research is unavailable right now.')
    }
  }

  return (
    <div className="glass-panel p-6 sm:p-8 border border-violet-500/20 bg-gradient-to-br from-violet-500/[0.04] to-transparent">
      <div className="flex items-center justify-between mb-1">
        <h2 className="font-semibold text-lg flex items-center gap-2">
          <Sparkles size={19} className="text-violet-400" /> Company Intelligence
        </h2>
        {status === 'done' && (
          <button onClick={runResearch} className="text-xs text-slate-500 hover:text-slate-300 flex items-center gap-1">
            <RefreshCw size={12} /> Re-research
          </button>
        )}
      </div>

      {status === 'idle' && (
        <>
          <p className="text-sm text-slate-400 mb-5 leading-relaxed">
            Want to know more about {companyName || 'this company'}? Gemini can research publicly
            available information about the company.
          </p>
          <button onClick={runResearch} className="btn-secondary py-3 px-5 border-violet-500/30 hover:border-violet-500/50">
            <Search size={16} /> Investigate Company
          </button>
        </>
      )}

      {status === 'loading' && (
        <div className="flex items-center gap-3 py-4">
          <Loader2 className="animate-spin text-violet-400" size={20} />
          <AnimatePresence mode="wait">
            <motion.span
              key={phase}
              initial={{ opacity: 0, y: 4 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -4 }}
              className="text-sm text-slate-300"
            >
              {LOADING_PHASES[phase]}
            </motion.span>
          </AnimatePresence>
        </div>
      )}

      {status === 'error' && (
        <div className="space-y-3">
          <div className="text-sm text-slate-500 bg-white/5 border border-white/10 rounded-lg px-4 py-3">
            {error}
          </div>
          <button onClick={runResearch} className="btn-secondary text-xs py-2 px-4">
            <RefreshCw size={13} /> Try Again
          </button>
        </div>
      )}

      {status === 'done' && report && (
        <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="space-y-6">
          {report.status === 'partial' ? (
            <div className="rounded-xl border border-amber-500/25 bg-amber-500/10 px-4 py-3 text-sm text-amber-200">
              <div className="flex items-center gap-2 font-semibold"><Info size={15} /> Source preview — AI not configured</div>
              <p className="mt-1 text-xs leading-relaxed text-amber-100/80">
                {report.error_message || 'Add GEMINI_API_KEY on the backend to enable AI-generated company research.'}
                {' '}The links below are sources only; this is not a legitimacy verdict.
              </p>
            </div>
          ) : (
            <div className="inline-flex items-center gap-1.5 text-[11px] font-medium text-violet-300 bg-violet-500/10 border border-violet-500/20 rounded-full px-2.5 py-1">
              <Sparkles size={10} /> AI-powered web research — from publicly available online sources
            </div>
          )}

          {/* --- Company Overview --- */}
          <section>
            <h3 className="text-xs font-semibold text-slate-400 uppercase tracking-wide mb-2.5">Company Overview</h3>
            {report.company_overview && (
              <p className="text-sm text-slate-300 leading-relaxed mb-3">{report.company_overview}</p>
            )}
            <div className="grid grid-cols-2 sm:grid-cols-3 gap-4 text-sm">
              {report.industry && (
                <div><div className="text-slate-500 text-xs mb-1">Industry</div><div className="font-medium">{report.industry}</div></div>
              )}
              {report.headquarters && (
                <div><div className="text-slate-500 text-xs mb-1">Headquarters</div><div className="font-medium">{report.headquarters}</div></div>
              )}
              {report.company_size && (
                <div><div className="text-slate-500 text-xs mb-1">Company Size</div><div className="font-medium">{report.company_size}</div></div>
              )}
              {report.founded_year && (
                <div><div className="text-slate-500 text-xs mb-1">Founded</div><div className="font-medium">{report.founded_year}</div></div>
              )}
            </div>
            {report.products_services && (
              <div className="text-sm mt-3"><span className="text-slate-500 text-xs">Products/Services: </span>{report.products_services}</div>
            )}
            {!report.company_overview && !report.industry && !report.headquarters && (
              <p className="text-xs text-slate-500">Could not verify basic company details.</p>
            )}
          </section>

          {/* --- Company Legitimacy --- */}
          <section className="pt-4 border-t border-white/10">
            <h3 className="text-xs font-semibold text-slate-400 uppercase tracking-wide mb-2.5">Company Legitimacy</h3>
            {report.official_website ? (
              <div className="mb-2">
                <div className="text-slate-500 text-xs mb-1 flex items-center gap-1"><Globe size={11} /> Official Website</div>
                <a href={report.official_website.startsWith('http') ? report.official_website : `https://${report.official_website}`}
                   target="_blank" rel="noopener noreferrer" className="text-brand-400 hover:underline text-xs break-all">
                  {report.official_website}
                </a>
              </div>
            ) : (
              <p className="text-xs text-slate-500 mb-2">Could not verify an official website.</p>
            )}
            {report.red_flags ? (
              <div className="flex items-start gap-2 text-sm bg-amber-500/10 border border-amber-500/20 rounded-lg px-4 py-3 mt-2">
                <AlertTriangle size={16} className="text-amber-400 mt-0.5 shrink-0" />
                <span className="text-amber-200">{report.red_flags}</span>
              </div>
            ) : (
              <p className="text-xs text-emerald-400/80 flex items-center gap-1.5 mt-2">
                <CheckCircle2 size={13} /> No concerning legitimacy signals found.
              </p>
            )}
          </section>

          {/* --- Company Reputation / Presence --- */}
          {(report.online_presence || report.careers_presence || report.recent_public_info) && (
            <section className="pt-4 border-t border-white/10">
              <h3 className="text-xs font-semibold text-slate-400 uppercase tracking-wide mb-2.5">Company Reputation &amp; Presence</h3>
              <div className="space-y-2 text-sm">
                {report.online_presence && (
                  <div><span className="text-slate-500 text-xs">Online Presence: </span>{report.online_presence}</div>
                )}
                {report.careers_presence && (
                  <div><span className="text-slate-500 text-xs">Careers Presence: </span>{report.careers_presence}</div>
                )}
                {report.recent_public_info && (
                  <div><span className="text-slate-500 text-xs">Recent Public Info: </span>{report.recent_public_info}</div>
                )}
              </div>
            </section>
          )}

          {/* --- Job/Company Relationship --- */}
          {jobTitle && (
            <section className="pt-4 border-t border-white/10">
              <h3 className="text-xs font-semibold text-slate-400 uppercase tracking-wide mb-2.5">Job / Company Relationship</h3>
              {report.job_consistency_notes ? (
                <p className="text-sm text-slate-300">{report.job_consistency_notes}</p>
              ) : (
                <p className="text-xs text-slate-500 flex items-center gap-1.5">
                  <Info size={12} /> Could not verify consistency between this company's public presence and the job posting.
                </p>
              )}
            </section>
          )}

          {/* --- Verified / interpreted / unverifiable — collapsible so the
              30-60s "understand this company" read isn't buried under a
              wall of bullet points by default. --- */}
          {(report.verified_facts?.length > 0 || report.ai_interpretation?.length > 0 || report.unverifiable?.length > 0) && (
            <section className="pt-4 border-t border-white/10 space-y-3">
              {report.verified_facts?.length > 0 && (
                <details className="group">
                  <summary className="text-xs font-semibold text-emerald-400 flex items-center gap-1.5 cursor-pointer select-none list-none">
                    <CheckCircle2 size={13} /> Verified Facts ({report.verified_facts.length})
                  </summary>
                  <ul className="space-y-1 mt-2">
                    {report.verified_facts.map((f, i) => <li key={i} className="text-xs text-slate-300 pl-4">{f}</li>)}
                  </ul>
                </details>
              )}
              {report.ai_interpretation?.length > 0 && (
                <details className="group">
                  <summary className="text-xs font-semibold text-brand-400 flex items-center gap-1.5 cursor-pointer select-none list-none">
                    <Sparkles size={13} /> AI Interpretation ({report.ai_interpretation.length})
                  </summary>
                  <ul className="space-y-1 mt-2">
                    {report.ai_interpretation.map((f, i) => <li key={i} className="text-xs text-slate-400 pl-4">{f}</li>)}
                  </ul>
                </details>
              )}
              {report.unverifiable?.length > 0 && (
                <details className="group">
                  <summary className="text-xs font-semibold text-slate-500 flex items-center gap-1.5 cursor-pointer select-none list-none">
                    <HelpCircle size={13} /> Could Not Verify ({report.unverifiable.length})
                  </summary>
                  <ul className="space-y-1 mt-2">
                    {report.unverifiable.map((f, i) => <li key={i} className="text-xs text-slate-500 pl-4">{f}</li>)}
                  </ul>
                </details>
              )}
            </section>
          )}

          {report.overall_assessment && (
            <p className="text-sm text-violet-200 pt-4 border-t border-white/10 font-medium">{report.overall_assessment}</p>
          )}

          {/* --- Sources --- */}
          <section className="pt-4 border-t border-white/10">
            <h3 className="text-xs font-semibold text-slate-400 uppercase tracking-wide mb-2.5">Sources</h3>
            {report.sources?.length > 0 ? (
              <div className="flex flex-wrap gap-2">
                {report.sources.map((s, i) => (
                  <a key={i} href={s.url} target="_blank" rel="noopener noreferrer"
                     className="text-xs px-2.5 py-1 rounded-full bg-white/5 border border-white/10 hover:border-violet-500/40 text-slate-400 hover:text-violet-300 flex items-center gap-1">
                    {s.title || s.domain || 'Source'} <ExternalLink size={10} />
                  </a>
                ))}
              </div>
            ) : (
              <p className="text-xs text-slate-500">No specific source citations were returned for this research.</p>
            )}
          </section>

          {report.generated_at && (
            <div className="flex items-center gap-1.5 text-[11px] text-slate-600 pt-1">
              <Clock size={11} /> Last checked: {formatCheckedTime(report.generated_at)}
            </div>
          )}
        </motion.div>
      )}
    </div>
  )
}
