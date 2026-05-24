import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import { useState, useEffect } from 'react'
import LoginPage from './pages/LoginPage'
import DashboardPage from './pages/DashboardPage'
import RecordsPage from './pages/RecordsPage'
import IngestPage from './pages/IngestPage'
import JobsPage from './pages/JobsPage'
import AppLayout from './components/AppLayout'

function App() {
  const [user, setUser] = useState(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    const storedUser = localStorage.getItem('user')
    if (storedUser) {
      try {
        setUser(JSON.parse(storedUser))
      } catch (_) {}
    }
    setLoading(false)
  }, [])

  const handleLogin = (userData) => {
    setUser(userData)
    localStorage.setItem('user', JSON.stringify(userData))
  }

  const handleLogout = () => {
    setUser(null)
    localStorage.removeItem('user')
    localStorage.removeItem('access_token')
    localStorage.removeItem('refresh_token')
    localStorage.removeItem('active_client')
  }

  if (loading) return null

  return (
    <BrowserRouter>
      <Routes>
        <Route path="/login" element={
          user ? <Navigate to="/" replace /> : <LoginPage onLogin={handleLogin} />
        } />
        <Route path="/*" element={
          user ? (
            <AppLayout user={user} onLogout={handleLogout}>
              <Routes>
                <Route path="/" element={<DashboardPage user={user} />} />
                <Route path="/records" element={<RecordsPage user={user} />} />
                <Route path="/ingest" element={<IngestPage user={user} />} />
                <Route path="/jobs" element={<JobsPage user={user} />} />
              </Routes>
            </AppLayout>
          ) : <Navigate to="/login" replace />
        } />
      </Routes>
    </BrowserRouter>
  )
}

export default App
