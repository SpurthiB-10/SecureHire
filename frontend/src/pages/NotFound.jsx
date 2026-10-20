import { Link } from 'react-router-dom'
import { ShieldQuestion } from 'lucide-react'

export default function NotFound() {
  return (
    <div className="max-w-md mx-auto px-4 py-32 text-center">
      <ShieldQuestion className="mx-auto text-slate-600 mb-4" size={48} />
      <h1 className="text-2xl font-bold mb-2">Page not found</h1>
      <p className="text-slate-400 mb-6">This page doesn't exist — maybe it's suspicious too.</p>
      <Link to="/" className="btn-primary inline-flex px-6 py-3">Back to Home</Link>
    </div>
  )
}
