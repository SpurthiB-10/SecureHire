import { Link } from 'react-router-dom'
import { ShieldCheck } from 'lucide-react'

export default function Footer() {
  return (
    <footer className="border-t border-white/5 mt-24">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-10 flex flex-col sm:flex-row items-center justify-between gap-4">
        <div className="flex items-center gap-2 text-slate-400 text-sm">
          <ShieldCheck size={18} className="text-brand-500" />
          <span>© {new Date().getFullYear()} SecureHire AI — built as a Data Engineering / ML portfolio project.</span>
        </div>
        <div className="flex gap-6 text-sm text-slate-400">
          <Link to="/features" className="hover:text-white">Features</Link>
          <Link to="/about" className="hover:text-white">About</Link>
          <Link to="/contact" className="hover:text-white">Contact</Link>
        </div>
      </div>
    </footer>
  )
}
