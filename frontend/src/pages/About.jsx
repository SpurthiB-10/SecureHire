import { motion } from 'framer-motion'
import { Search, ShieldAlert, BadgeCheck, ThumbsUp, ShieldCheck } from 'lucide-react'

const STEPS = [
  { icon: Search, title: 'Analyze', desc: 'Paste in a job posting — title, company, and full description.' },
  { icon: ShieldAlert, title: 'Detect', desc: 'Our AI checks the text for scam patterns and red flags.' },
  { icon: BadgeCheck, title: 'Verify', desc: 'We check the company itself — trust signals and AI-backed background.' },
  { icon: ThumbsUp, title: 'Decide', desc: 'You get a clear risk rating so you can apply with confidence.' },
]

export default function About() {
  return (
    <div className="max-w-3xl mx-auto px-4 sm:px-6 lg:px-8 py-16">
      <div className="text-center mb-12">
        <ShieldCheck className="mx-auto text-brand-500 mb-4" size={40} />
        <h1 className="text-4xl font-bold mb-4">About SecureHire AI</h1>
        <p className="text-lg text-slate-300 leading-relaxed max-w-xl mx-auto">
          SecureHire AI helps job seekers identify potentially fraudulent job postings and verify
          company-related signals before applying.
        </p>
      </div>

      <div className="grid sm:grid-cols-2 gap-5">
        {STEPS.map((step, i) => (
          <motion.div
            key={step.title}
            initial={{ opacity: 0, y: 14 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true }}
            transition={{ delay: i * 0.08 }}
            className="glass-panel p-6"
          >
            <div className="flex items-center gap-3 mb-3">
              <div className="w-10 h-10 rounded-xl bg-brand-500/15 flex items-center justify-center">
                <step.icon className="text-brand-400" size={20} />
              </div>
              <span className="text-xs font-mono text-slate-500">0{i + 1}</span>
            </div>
            <h3 className="font-semibold mb-1.5">{step.title}</h3>
            <p className="text-sm text-slate-400 leading-relaxed">{step.desc}</p>
          </motion.div>
        ))}
      </div>

      <div className="glass-panel p-6 mt-8 text-center text-sm text-slate-500">
        Job and internship scams target early-career applicants disproportionately — fake postings
        that ask for fees, promise unrealistic pay, or impersonate real companies. SecureHire AI is
        built to catch those patterns before you do.
      </div>
    </div>
  )
}
