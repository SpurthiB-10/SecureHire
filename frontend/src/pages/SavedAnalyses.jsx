import { useEffect, useState } from 'react'
import { Bookmark, Loader2 } from 'lucide-react'
import { getMySavedJobs } from '../api/client'
import RiskBadge from '../components/RiskBadge.jsx'

export default function SavedAnalyses() {
  const [jobs, setJobs] = useState([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    getMySavedJobs()
      .then(({ data }) => setJobs(data))
      .finally(() => setLoading(false))
  }, [])

  return (
    <div className="max-w-5xl mx-auto px-4 sm:px-6 lg:px-8 py-12">
      <h1 className="text-3xl font-bold flex items-center gap-2 mb-8">
        <Bookmark className="text-brand-500" /> Saved Analyses
      </h1>

      {loading && <div className="flex justify-center py-16 text-slate-500"><Loader2 className="animate-spin mr-2" /> Loading...</div>}

      {!loading && jobs.length === 0 && (
        <div className="glass-panel p-12 text-center text-slate-500">
          You haven't saved any job analyses yet. Analyze a posting and hit "Save" to keep it here.
        </div>
      )}

      <div className="space-y-3">
        {jobs.map((job) => (
          <div key={job.id} className="glass-panel p-5 flex items-center justify-between">
            <div>
              <h3 className="font-semibold">{job.title}</h3>
              <p className="text-sm text-slate-400">{job.company_name || 'Unknown company'} {job.location && `· ${job.location}`}</p>
            </div>
            {job.risk_category && <RiskBadge category={job.risk_category} />}
          </div>
        ))}
      </div>
    </div>
  )
}
