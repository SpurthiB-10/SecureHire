import { motion } from 'framer-motion'
import {
  Brain, Network, FileSearch, Sparkles, Clock, Users2, ShieldAlert, LineChart,
} from 'lucide-react'

const FEATURES = [
  { icon: Brain, title: 'Explainable Fraud Detection', desc: 'A soft-voting ensemble of Logistic Regression, Random Forest, and XGBoost combines hand-crafted red-flag features with TF-IDF text representations to score every posting 0–100%. SHAP explanations show exactly which signals drove the score.' },
  { icon: Network, title: 'Company Trust Graph', desc: 'Every employer accumulates a live Trust Score from domain age, verified-domain status, posting consistency over time, and community fraud reports — so trust is earned and observable, not assumed.' },
  { icon: FileSearch, title: 'Skill Intelligence Engine', desc: 'NLP-based skill extraction identifies required technologies from any posting, compares them against your tracked skill profile, and shows real market-demand tiers plus learning resources for gaps.' },
  { icon: Clock, title: 'Job Authenticity Timeline', desc: 'Tracks when a posting first appeared, when it was last updated, whether it duplicates across sources, and flags sudden suspicious edits — the same forensic pattern trust & safety teams use.' },
  { icon: Users2, title: 'Community Reporting System', desc: 'Users can report suspicious postings with evidence, vote on authenticity in comment threads, and directly influence a company\'s trust score in real time.' },
  { icon: Sparkles, title: 'AI Career Assistant', desc: 'A grounded chat assistant answers "why is this suspicious?", "what skills should I learn?", and "find safer alternatives" — using the actual structured prediction data, not a black box.' },
  { icon: ShieldAlert, title: 'Twelve Engineered Red-Flag Signals', desc: 'Free email domains, suspicious salary spreads, urgent-hiring language, missing company info, experience mismatches, promotional phrase density, skill-role mismatch, and more — each individually interpretable.' },
  { icon: LineChart, title: 'Fraud Analytics Dashboard', desc: 'Real-time charts on fake-vs-real ratios, fraud hotspots by location and category, top scam keywords, model confidence distribution, and skill demand trends.' },
]

export default function Features() {
  return (
    <div className="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8 py-16">
      <div className="text-center mb-14">
        <h1 className="text-4xl font-bold mb-4">Everything SecureHire AI does</h1>
        <p className="text-slate-400 max-w-2xl mx-auto">
          A production-style fraud-detection pipeline: Data Engineering (ETL) + Data Science (feature engineering,
          NLP) + explainable ML, wrapped in a real full-stack product.
        </p>
      </div>

      <div className="grid sm:grid-cols-2 gap-6">
        {FEATURES.map((f, i) => (
          <motion.div
            key={f.title}
            initial={{ opacity: 0, y: 16 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true }}
            transition={{ delay: i * 0.05 }}
            className="glass-panel p-6"
          >
            <div className="w-11 h-11 rounded-xl bg-brand-500/15 flex items-center justify-center mb-4">
              <f.icon className="text-brand-400" size={22} />
            </div>
            <h3 className="font-semibold mb-2">{f.title}</h3>
            <p className="text-sm text-slate-400 leading-relaxed">{f.desc}</p>
          </motion.div>
        ))}
      </div>
    </div>
  )
}
