import axios from 'axios'

const API_BASE = import.meta.env.VITE_API_BASE_URL || '/api/v1'

export const api = axios.create({
  baseURL: API_BASE,
  headers: { 'Content-Type': 'application/json' },
})

api.interceptors.request.use((config) => {
  const token = localStorage.getItem('securehire_token')
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

// A cached user object can outlive the signing key or database session.
// If a protected API rejects its token, clear the stale browser session and
// send the user to login instead of leaving every page stuck in an error state.
api.interceptors.response.use(
  (response) => response,
  (error) => {
    const status = error?.response?.status
    const url = error?.config?.url || ''
    const isAuthRequest = /\/auth\/(login|register)/.test(url)
    if (status === 401 && !isAuthRequest) {
      localStorage.removeItem('securehire_token')
      localStorage.removeItem('securehire_user')
      if (window.location.pathname !== '/login') {
        window.location.assign('/login?reason=session-expired')
      }
    }
    return Promise.reject(error)
  },
)

// --- Auth ---
export const registerUser = (data) => api.post('/auth/register', data)
export const loginUser = (data) => api.post('/auth/login', data)

// --- Jobs ---
export const analyzeJob = (data) => api.post('/jobs/analyze', data)
export const uploadJobFile = (file) => {
  const formData = new FormData()
  formData.append('file', file)
  return api.post('/jobs/upload', formData, { headers: { 'Content-Type': 'multipart/form-data' } })
}
export const getTrustedJobs = () => api.get('/jobs/trusted')
export const getJob = (jobId) => api.get(`/jobs/${jobId}`)
export const getFullAnalysis = (jobId) => api.get(`/jobs/${jobId}/analysis`)
export const saveJob = (jobId) => api.post(`/jobs/${jobId}/save`)
export const getMySavedJobs = () => api.get('/jobs/saved/me')
export const getMyAnalyses = () => api.get('/jobs/mine')
export const getMySkills = () => api.get('/skills/mine')
export const getSkillMarketDemand = () => api.get('/skills/demand')

// --- Company Check ---
export const checkCompany = (data) => api.post('/company/check', data)
export const deepResearchCompany = (data) => api.post('/company/deep-research', data)

// --- Reports ---
export const createReport = (data) => api.post('/reports/create', data)

// --- Skills ---
export const extractSkills = (text) => api.post('/skills/extract', { text })
export const trackSkill = (skillName, proficiency) =>
  api.post(`/skills/track?skill_name=${encodeURIComponent(skillName)}&proficiency=${proficiency}`)

// --- Analytics ---
export const getFraudTrends = () => api.get('/analytics/fraud-trends')
export const getModelPerformance = () => api.get('/analytics/model-performance')
export const getCompanyTrust = () => api.get('/analytics/company-trust')
export const getPipelineHealth = () => api.get('/analytics/pipeline-health')

// --- Chat ---
export const sendChatMessage = (message, jobId) => api.post('/chat', { message, job_id: jobId })

export default api
