import { Routes, Route } from 'react-router-dom'
import Navbar from './components/Navbar.jsx'
import Footer from './components/Footer.jsx'
import ProtectedRoute from './components/ProtectedRoute.jsx'

import Landing from './pages/Landing.jsx'
import Features from './pages/Features.jsx'
import About from './pages/About.jsx'
import Contact from './pages/Contact.jsx'
import Login from './pages/Login.jsx'
import Signup from './pages/Signup.jsx'
import AnalyzeJob from './pages/AnalyzeJob.jsx'
import FullAnalysis from './pages/FullAnalysis.jsx'
import CompanyCheck from './pages/CompanyCheck.jsx'
import TrustedJobsFeed from './pages/TrustedJobsFeed.jsx'
import Dashboard from './pages/Dashboard.jsx'
import SavedAnalyses from './pages/SavedAnalyses.jsx'
import Profile from './pages/Profile.jsx'
import JobsSkillsDemand from './pages/JobsSkillsDemand.jsx'
import AdminPanel from './pages/AdminPanel.jsx'
import AdminAnalytics from './pages/AdminAnalytics.jsx'
import NotFound from './pages/NotFound.jsx'

const Protected = ({ children }) => <ProtectedRoute>{children}</ProtectedRoute>

export default function App() {
  return (
    <div className="min-h-screen flex flex-col app-shell">
      <Navbar />
      <main className="flex-1">
        <Routes>
          <Route path="/" element={<Landing />} />
          <Route path="/features" element={<Features />} />
          <Route path="/about" element={<About />} />
          <Route path="/contact" element={<Contact />} />
          <Route path="/login" element={<Login />} />
          <Route path="/signup" element={<Signup />} />

          <Route path="/analyze" element={<Protected><AnalyzeJob /></Protected>} />
          <Route path="/analysis/:jobId" element={<Protected><FullAnalysis /></Protected>} />
          <Route path="/company-check" element={<Protected><CompanyCheck /></Protected>} />
          <Route path="/trusted-jobs" element={<Protected><TrustedJobsFeed /></Protected>} />
          <Route path="/dashboard" element={<Protected><Dashboard /></Protected>} />
          <Route path="/jobs-skills" element={<Protected><JobsSkillsDemand /></Protected>} />
          <Route path="/saved" element={<Protected><SavedAnalyses /></Protected>} />
          <Route path="/profile" element={<Protected><Profile /></Protected>} />
          <Route path="/admin" element={<Protected><AdminPanel /></Protected>} />
          <Route path="/admin/analytics" element={<Protected><AdminAnalytics /></Protected>} />

          <Route path="*" element={<NotFound />} />
        </Routes>
      </main>
      <Footer />
    </div>
  )
}
