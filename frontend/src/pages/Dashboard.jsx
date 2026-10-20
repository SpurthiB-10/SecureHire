import { useEffect, useMemo, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { motion } from 'framer-motion'
import { Loader2, Search, Building2, ArrowRight, ShieldCheck, Clock3, UserCircle2 } from 'lucide-react'
import { getMyAnalyses } from '../api/client'
import { useAuth } from '../context/AuthContext.jsx'
import RiskBadge from '../components/RiskBadge.jsx'

function formatDate(iso) { try { return new Date(iso).toLocaleDateString('en-US',{month:'short',day:'numeric',year:'numeric'}) } catch { return '' } }

export default function Dashboard() {
  const { user } = useAuth(); const navigate=useNavigate(); const [jobs,setJobs]=useState([]); const [loading,setLoading]=useState(true); const [error,setError]=useState(''); const [query,setQuery]=useState('')
  useEffect(()=>{ getMyAnalyses().then(({data})=>setJobs(data)).catch(()=>setError('Could not load your job history right now.')).finally(()=>setLoading(false)) },[])
  const filtered=useMemo(()=>jobs.filter(j=>`${j.title} ${j.company_name||''}`.toLowerCase().includes(query.toLowerCase())),[jobs,query])
  const counts={low:jobs.filter(j=>j.risk_category==='Low').length, medium:jobs.filter(j=>j.risk_category==='Medium').length, high:jobs.filter(j=>j.risk_category==='High').length}
  if(loading) return <div className="page-center"><Loader2 className="animate-spin"/> Loading your dashboard...</div>
  return <div className="page-container max-w-6xl">
    <div className="dashboard-hero"><div><p className="section-kicker">YOUR SPACE</p><h1 className="page-title">Welcome back, {user?.full_name?.split(' ')[0] || 'there'}.</h1><p className="section-copy text-left">Your profile and every job you have checked, all in one place.</p></div><Link to="/analyze" className="btn-primary"><Search size={17}/> Analyze a new job</Link></div>
    <div className="grid md:grid-cols-[1.1fr_2fr] gap-5 mb-7">
      <div className="glass-panel p-6"><div className="flex items-center gap-3 mb-5"><span className="avatar avatar-lg">{(user?.full_name||user?.email||'U').slice(0,1).toUpperCase()}</span><div><h2 className="font-semibold">{user?.full_name||'Your Profile'}</h2><p className="muted-text text-sm">{user?.email}</p></div></div><div className="space-y-3 text-sm"><div className="info-row"><span>Account</span><strong>{user?.is_verified?'Verified':'Active'}</strong></div><div className="info-row"><span>Member since</span><strong>{user?.created_at ? formatDate(user.created_at) : 'Recently'}</strong></div></div><Link to="/profile" className="btn-secondary w-full mt-5">Manage profile <ArrowRight size={15}/></Link></div>
      <div className="glass-panel p-6"><div className="flex items-center justify-between mb-5"><div><h2 className="font-semibold text-lg">Your job checks</h2><p className="muted-text text-sm">A quick view of your recent decisions.</p></div><span className="text-sm font-semibold">{jobs.length} total</span></div><div className="grid grid-cols-3 gap-3"><div className="stat-card"><span>{counts.low}</span><small>Low risk</small></div><div className="stat-card"><span>{counts.medium}</span><small>Review</small></div><div className="stat-card"><span>{counts.high}</span><small>High risk</small></div></div></div>
    </div>
    <div className="flex flex-col sm:flex-row gap-3 items-stretch sm:items-center justify-between mb-4"><div><h2 className="text-xl font-bold">Search history</h2><p className="muted-text text-sm mt-1">Open any previous analysis to review the full result.</p></div><input className="input-field sm:max-w-xs" placeholder="Search jobs or companies..." value={query} onChange={e=>setQuery(e.target.value)}/></div>
    {error && <div className="error-box mb-4">{error}</div>}
    {filtered.length===0 ? <div className="glass-panel p-14 text-center"><Clock3 size={34} className="mx-auto mb-4 text-brand-500"/><h3 className="font-semibold mb-2">{jobs.length?'No matching jobs':'Your history is empty'}</h3><p className="muted-text text-sm mb-6">{jobs.length?'Try a different search.':'Analyze your first posting and it will appear here automatically.'}</p>{!jobs.length&&<Link to="/analyze" className="btn-primary inline-flex">Analyze a job <ArrowRight size={16}/></Link>}</div> : <div className="space-y-3">{filtered.map((job,i)=><motion.div key={job.id} initial={{opacity:0,y:8}} animate={{opacity:1,y:0}} transition={{delay:Math.min(i*.025,.25)}} className="history-row" onClick={()=>navigate(`/analysis/${job.id}`)}><div className="min-w-0 flex-1"><div className="flex items-center gap-1.5 text-xs muted-text mb-1"><Building2 size={12}/>{job.company_name||'Company not provided'}</div><h3 className="font-semibold truncate">{job.title}</h3><div className="text-xs muted-text mt-1">Analyzed {formatDate(job.created_at)}{job.location?` · ${job.location}`:''}</div></div><div className="flex items-center gap-2 shrink-0">{job.risk_category&&<RiskBadge category={job.risk_category}/>}<Link to={`/analysis/${job.id}`} onClick={e=>e.stopPropagation()} className="btn-secondary text-xs py-2 px-3">Open <ArrowRight size={13}/></Link></div></motion.div>)}</div>}
  </div>
}
