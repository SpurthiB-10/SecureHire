import { useState } from 'react'
import { Mail, Github, Linkedin, Send } from 'lucide-react'

export default function Contact() {
  const [sent, setSent] = useState(false)
  const [form, setForm] = useState({ name: '', email: '', message: '' })

  const handleSubmit = (e) => {
    e.preventDefault()
    // No backend contact endpoint in this scaffold — this is a UI-complete
    // stub. Wire it to a /contact API route or a mail service if needed.
    setSent(true)
  }

  return (
    <div className="max-w-2xl mx-auto px-4 sm:px-6 lg:px-8 py-16">
      <h1 className="text-4xl font-bold mb-3">Get in touch</h1>
      <p className="text-slate-400 mb-10">Questions, feedback, or found a bug? Reach out.</p>

      <div className="glass-panel p-8">
        {sent ? (
          <div className="text-center py-8">
            <Send className="mx-auto text-brand-400 mb-3" size={32} />
            <p className="text-slate-300">Thanks for reaching out — this is a demo form, but in production it would send your message right through.</p>
          </div>
        ) : (
          <form onSubmit={handleSubmit} className="space-y-4">
            <input required className="input-field" placeholder="Your name" value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} />
            <input required type="email" className="input-field" placeholder="Your email" value={form.email} onChange={(e) => setForm({ ...form, email: e.target.value })} />
            <textarea required className="input-field min-h-[140px]" placeholder="Your message" value={form.message} onChange={(e) => setForm({ ...form, message: e.target.value })} />
            <button type="submit" className="btn-primary w-full py-3">Send Message</button>
          </form>
        )}

        <div className="flex justify-center gap-6 mt-8 pt-8 border-t border-white/10 text-slate-400">
          <a href="#" className="hover:text-white flex items-center gap-2 text-sm"><Mail size={16} /> Email</a>
          <a href="#" className="hover:text-white flex items-center gap-2 text-sm"><Github size={16} /> GitHub</a>
          <a href="#" className="hover:text-white flex items-center gap-2 text-sm"><Linkedin size={16} /> LinkedIn</a>
        </div>
      </div>
    </div>
  )
}
