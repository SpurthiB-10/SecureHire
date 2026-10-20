import { Link } from 'react-router-dom'
import { motion } from 'framer-motion'
import { ShieldCheck, SearchCheck, Building2, History, ArrowRight, Sparkles, CheckCircle2 } from 'lucide-react'
import { useAuth } from '../context/AuthContext.jsx'

const features = [
  { icon: SearchCheck, title: 'Check a job before you apply', desc: 'Get a clear scam-risk assessment from the job description, contact details and other signals.' },
  { icon: Building2, title: 'Understand the company', desc: 'Use Gemini-powered company intelligence to investigate the employer and see evidence-backed findings.' },
  { icon: History, title: 'Keep your job-check history', desc: 'Every analysis stays in your account so you can revisit decisions, compare roles and avoid repeating work.' },
]

export default function Landing() {
  const { isAuthenticated, user } = useAuth()
  return (
    <div>
      <section className="hero-section">
        <div className="hero-orb hero-orb-one" /><div className="hero-orb hero-orb-two" />
        <div className="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8 py-20 sm:py-28 text-center relative">
          <motion.div initial={{opacity:0,y:12}} animate={{opacity:1,y:0}} className="eyebrow"><ShieldCheck size={15}/> Safer job hunting, powered by AI</motion.div>
          <motion.h1 initial={{opacity:0,y:18}} animate={{opacity:1,y:0}} transition={{delay:.08}} className="hero-title">
            Know the job is real <span>before you apply.</span>
          </motion.h1>
          <motion.p initial={{opacity:0,y:18}} animate={{opacity:1,y:0}} transition={{delay:.16}} className="hero-copy">
            SecureHire AI helps you spot suspicious job postings, understand the employer, and make a more confident decision — all in one place.
          </motion.p>
          <motion.div initial={{opacity:0,y:18}} animate={{opacity:1,y:0}} transition={{delay:.24}} className="flex flex-col sm:flex-row justify-center gap-3 mt-9">
            {isAuthenticated ? <Link to="/analyze" className="btn-primary px-7 py-3.5 text-base">Analyze a job <ArrowRight size={18}/></Link> : <Link to="/signup" className="btn-primary px-7 py-3.5 text-base">Create your free account <ArrowRight size={18}/></Link>}
            <Link to="/features" className="btn-secondary px-7 py-3.5 text-base">See how it works</Link>
          </motion.div>
          <div className="mt-12 flex flex-wrap justify-center gap-x-7 gap-y-3 text-sm muted-text">
            {['Fraud-risk scoring','Plain-English explanations','Company intelligence','Personal job history'].map((x)=><span key={x} className="inline-flex items-center gap-2"><CheckCircle2 size={15} className="text-brand-500"/>{x}</span>)}
          </div>
        </div>
      </section>

      <section className="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8 py-20">
        <div className="text-center max-w-2xl mx-auto mb-12"><p className="section-kicker">WHAT YOU GET</p><h2 className="section-title">Everything you need to make a safer job decision.</h2><p className="section-copy">No technical dashboards or model jargon. Just the information that matters when you are deciding whether a role is worth your time.</p></div>
        <div className="grid md:grid-cols-3 gap-5">
          {features.map((f,i)=><motion.div key={f.title} initial={{opacity:0,y:18}} whileInView={{opacity:1,y:0}} viewport={{once:true}} transition={{delay:i*.07}} className="feature-card"><div className="feature-icon"><f.icon size={22}/></div><h3>{f.title}</h3><p>{f.desc}</p></motion.div>)}
        </div>
      </section>

      <section className="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8 pb-20">
        <div className="product-story glass-panel">
          <div><p className="section-kicker">HOW IT FEELS</p><h2 className="section-title text-left">Paste the job. Understand the risk. Decide what to do next.</h2><p className="section-copy text-left">SecureHire checks the job for suspicious signals, then AI can investigate the company separately. You get the useful answer without having to understand the technology behind it.</p></div>
          <div className="story-steps">{[['01','Paste the posting'],['02','Review the risk'],['03','Investigate the company'],['04','Decide with confidence']].map(([n,t])=><div key={n} className="story-step"><span>{n}</span><strong>{t}</strong></div>)}</div>
        </div>
      </section>

      <section className="max-w-5xl mx-auto px-4 sm:px-6 lg:px-8 pb-24 text-center"><div className="cta-card"><Sparkles className="mx-auto text-brand-500 mb-4" size={30}/><h2 className="text-3xl font-bold">Ready to check your next opportunity{user ? `, ${user.full_name?.split(' ')[0] || 'there'}` : ''}?</h2><p className="muted-text mt-3 mb-7">Create an account to keep every job check in your personal history.</p>{!isAuthenticated && <Link to="/signup" className="btn-primary inline-flex px-7 py-3.5">Create account</Link>}</div></section>
    </div>
  )
}
