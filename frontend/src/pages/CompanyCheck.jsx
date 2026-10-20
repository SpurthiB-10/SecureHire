import { useState } from 'react'
import { useLocation } from 'react-router-dom'
import { Building2 } from 'lucide-react'
import GeminiCompanyResearch from '../components/GeminiCompanyResearch.jsx'

export default function CompanyCheck() {
  const routeLocation = useLocation()
  const [companyName, setCompanyName] = useState(routeLocation.state?.companyName || '')
  const [companyWebsite, setCompanyWebsite] = useState(routeLocation.state?.companyWebsite || '')
  const [submittedName, setSubmittedName] = useState('')
  const [submittedWebsite, setSubmittedWebsite] = useState('')
  const [researchKey, setResearchKey] = useState(0)
  const [error, setError] = useState('')

  const handleCheck = (e) => {
    e.preventDefault()
    setError('')
    if (!companyName.trim()) {
      setError('Please enter a company name.')
      return
    }
    setSubmittedName(companyName.trim())
    setSubmittedWebsite(companyWebsite.trim())
    // Incrementing forces a fresh mount (and therefore a fresh autoRun)
    // on every submit, including re-checking the exact same company name
    // — a plain name-based key wouldn't change in that case.
    setResearchKey((k) => k + 1)
  }

  return (
    <div className="max-w-3xl mx-auto px-4 sm:px-6 lg:px-8 py-14">
      <div className="text-center mb-10">
        <h1 className="text-4xl font-extrabold tracking-tight">Check a Company</h1>
        <p className="text-slate-400 mt-3 text-lg">Learn more about a company before you apply.</p>
      </div>

      <form onSubmit={handleCheck} className="glass-panel p-6 sm:p-8 space-y-4">
        <div>
          <label className="text-xs text-slate-400 mb-1.5 block">Company Name</label>
          <input className="input-field" placeholder="e.g. Microsoft" value={companyName} onChange={(e) => setCompanyName(e.target.value)} />
        </div>
        <div>
          <label className="text-xs text-slate-400 mb-1.5 block">Company Website (optional)</label>
          <input className="input-field" placeholder="https://company.com" value={companyWebsite} onChange={(e) => setCompanyWebsite(e.target.value)} />
        </div>
        {error && (
          <div className="text-sm text-red-400 bg-red-500/10 border border-red-500/20 rounded-lg px-4 py-2.5">{error}</div>
        )}
        <button type="submit" className="btn-primary w-full py-3.5 text-base">
          Analyze Company
        </button>
      </form>

      {submittedName ? (
        <div className="mt-6">
          <GeminiCompanyResearch
            key={researchKey}
            companyName={submittedName}
            companyWebsite={submittedWebsite}
            autoRun
          />
        </div>
      ) : (
        <div className="glass-panel p-10 mt-6 text-center text-slate-500">
          <Building2 size={36} className="mx-auto mb-3 opacity-30" />
          <p>Enter a company above to see its trust signals and AI-researched background.</p>
        </div>
      )}
    </div>
  )
}
