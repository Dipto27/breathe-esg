import axios from 'axios'

const api = axios.create({
  baseURL: `${import.meta.env.VITE_API_URL}/api`,
})

// Attach JWT token from localStorage to every request
api.interceptors.request.use((config) => {
  const token = localStorage.getItem('access_token')
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

// On 401, clear tokens and reload to login
api.interceptors.response.use(
  (res) => res,
  (err) => {
    if (err.response?.status === 401) {
      localStorage.removeItem('access_token')
      localStorage.removeItem('refresh_token')
      window.location.href = '/login'
    }
    return Promise.reject(err)
  }
)

export default api

// Auth
export const login = (username, password) =>
  api.post('/auth/login/', { username, password })

// Clients
export const getClients = () => api.get('/clients/')

// Summary
export const getSummary = (clientId) => api.get(`/clients/${clientId}/summary/`)

// Records
export const getRecords = (clientId, params = {}) =>
  api.get(`/clients/${clientId}/records/`, { params })

export const getRecord = (id) => api.get(`/records/${id}/`)

export const approveRecord = (id, notes = '') =>
  api.post(`/records/${id}/approve/`, { notes })

export const flagRecord = (id, reason) =>
  api.post(`/records/${id}/flag/`, { reason })

export const getAuditTrail = (id) => api.get(`/records/${id}/audit/`)

// Ingestion
export const getJobs = (clientId) => api.get(`/clients/${clientId}/jobs/`)

export const ingestFile = (clientId, file, sourceType, sourceLabel) => {
  const formData = new FormData()
  formData.append('file', file)
  formData.append('source_type', sourceType)
  formData.append('source_label', sourceLabel)
  return api.post(`/clients/${clientId}/ingest/`, formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
  })
}

export const loadSampleData = (clientId) =>
  api.post(`/clients/${clientId}/load-samples/`)
