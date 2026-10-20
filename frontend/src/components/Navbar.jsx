import { Link, useNavigate, useLocation } from 'react-router-dom'
import { ShieldCheck, LayoutDashboard, Search, UsersRound, BriefcaseBusiness, Building2, UserCircle2, LogOut, Menu, X, Sun, Moon } from 'lucide-react'
import { useState } from 'react'
import { useAuth } from '../context/AuthContext.jsx'
import { useTheme } from '../context/ThemeContext.jsx'

const links = [
  { to: '/analyze', label: 'Analyze Job', icon: Search },
  { to: '/company-check', label: 'AI Company Search', icon: Building2 },
  { to: '/trusted-jobs', label: 'Trusted Jobs', icon: UsersRound },
  { to: '/jobs-skills', label: 'Jobs & Skills', icon: BriefcaseBusiness },
  { to: '/dashboard', label: 'Dashboard', icon: LayoutDashboard },
]

export default function Navbar() {
  const { user, logout, isAuthenticated } = useAuth()
  const { theme, toggleTheme } = useTheme()
  const navigate = useNavigate()
  const location = useLocation()
  const [open, setOpen] = useState(false)

  const handleLogout = () => { logout(); setOpen(false); navigate('/') }
  const go = (to) => { setOpen(false); navigate(to) }

  return (
    <header className="sticky top-0 z-50 nav-shell backdrop-blur-xl">
      <nav className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 h-[72px] flex items-center justify-between gap-4">
        <Link to="/" className="flex items-center gap-2.5 font-bold text-lg shrink-0">
          <span className="brand-mark"><ShieldCheck size={22} strokeWidth={2.5} /></span>
          <span>SecureHire<span className="text-brand-500">AI</span></span>
        </Link>

        {isAuthenticated && (
          <div className="hidden lg:flex items-center gap-1 flex-1 justify-center">
            {links.map(({ to, label, icon: Icon }) => {
              const active = location.pathname === to || location.pathname.startsWith(`${to}/`)
              return <Link key={to} to={to} className={`nav-link ${active ? 'nav-link-active' : ''}`}><Icon size={16} /> {label}</Link>
            })}
          </div>
        )}

        <div className="hidden md:flex items-center gap-2 shrink-0">
          <button onClick={toggleTheme} className="icon-button" aria-label="Toggle theme" title={theme === 'dark' ? 'Switch to light theme' : 'Switch to dark theme'}>
            {theme === 'dark' ? <Sun size={17} /> : <Moon size={17} />}
          </button>
          {isAuthenticated ? (
            <>
              <button onClick={() => navigate('/profile')} className="profile-chip">
                <span className="avatar">{(user?.full_name || user?.email || 'U').slice(0, 1).toUpperCase()}</span>
                <span className="hidden xl:block">{user?.full_name?.split(' ')[0] || 'Profile'}</span>
              </button>
              <button onClick={handleLogout} className="icon-button" title="Log out"><LogOut size={16} /></button>
            </>
          ) : (
            <>
              <Link to="/login" className="nav-login">Log in</Link>
              <Link to="/signup" className="btn-primary text-sm px-4 py-2.5">Create account</Link>
            </>
          )}
        </div>

        <div className="md:hidden flex items-center gap-2">
          <button onClick={toggleTheme} className="icon-button" aria-label="Toggle theme">{theme === 'dark' ? <Sun size={17} /> : <Moon size={17} />}</button>
          <button className="icon-button" onClick={() => setOpen(!open)}>{open ? <X size={20} /> : <Menu size={20} />}</button>
        </div>
      </nav>

      {open && (
        <div className="md:hidden mobile-nav">
          {isAuthenticated ? links.map(({ to, label, icon: Icon }) => (
            <button key={to} onClick={() => go(to)} className="mobile-nav-link"><Icon size={17} /> {label}</button>
          )) : null}
          {isAuthenticated && <button onClick={() => go('/profile')} className="mobile-nav-link"><UserCircle2 size={17} /> Profile</button>}
          {!isAuthenticated && <><button onClick={() => go('/login')} className="mobile-nav-link">Log in</button><button onClick={() => go('/signup')} className="mobile-nav-link">Create account</button></>}
          {isAuthenticated && <button onClick={handleLogout} className="mobile-nav-link text-red-400"><LogOut size={17} /> Log out</button>}
        </div>
      )}
    </header>
  )
}
