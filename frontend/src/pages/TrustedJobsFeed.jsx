import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { motion } from 'framer-motion'
import { ShieldCheck, Loader2, MapPin, Building2, ArrowRight, ExternalLink, CheckCircle2 } from 'lucide-react'
import { getTrustedJobs } from '../api/client'
import RiskBadge from '../components/RiskBadge.jsx'

export default function TrustedJobsFeed() {
  const [jobs, setJobs] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  useEffect(() => {
    getTrustedJobs()
      .then(({ data }) => setJobs(data))
      .catch(() => setError('Could not load the trusted jobs feed right now.'))
      .finally(() => setLoading(false))
  }, [])

  return (
    <div className="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8 py-12">
      <div className="mb-10 text-center">
        <h1 className="text-3xl font-bold flex items-center justify-center gap-2">
          <ShieldCheck className="text-brand-500" /> Trusted Feed
        </h1>
        <p className="text-slate-400 mt-2 max-w-xl mx-auto">
          A small shortlist of up to 10 recent postings that SecureHire AI scored as Low Risk.
        </p>
      </div>

      {loading && (
        <div className="flex justify-center py-20 text-slate-500">
          <Loader2 className="animate-spin mr-2" /> Loading feed...
        </div>
      )}

      {error && <div className="text-red-400 text-center py-10">{error}</div>}

      {!loading && !error && jobs.length === 0 && (
        <div className="glass-panel p-14 text-center">
          <p className="text-slate-400 mb-5">No trusted postings yet — be the first to check one.</p>
          <Link to="/analyze" className="btn-primary inline-flex px-6 py-3">
            Analyze a Job <ArrowRight size={16} />
          </Link>
        </div>
      )}

      <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-5">
        {jobs.map((job, i) => (
          <motion.div
            key={job.id}
            initial={{ opacity: 0, y: 14 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: Math.min(i * 0.04, 0.4) }}
            className="glass-panel p-5 hover:border-brand-500/30 transition-colors flex flex-col"
          >
            <div className="flex items-start justify-between mb-3 gap-2">
              <h3 className="font-semibold leading-snug">{job.title}</h3>
              <RiskBadge category={job.risk_category || 'Low'} />
            </div>
            <div className="space-y-1.5 text-sm text-slate-400 flex-1">
              <div className="flex items-center gap-1.5 text-emerald-400 text-xs font-medium"><CheckCircle2 size={13}/> Low-risk signal</div>
              {job.company_name && (
                <div className="flex items-center gap-1.5"><Building2 size={14} /> {job.company_name}</div>
              )}
              {job.location && (
                <div className="flex items-center gap-1.5"><MapPin size={14} /> {job.location}</div>
              )}
            </div>
            <Link to="/analyze" className="btn-secondary text-xs py-2 px-3 mt-4 justify-center">
              Analyze a Similar Job
            </Link>
          </motion.div>
        ))}
      </div>
    </div>
  )
}
