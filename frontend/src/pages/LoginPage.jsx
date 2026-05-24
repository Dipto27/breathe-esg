import { useState } from 'react'
import { login } from '../api/client'

export default function LoginPage({ onLogin }) {
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  const handleSubmit = async (e) => {
    e.preventDefault()
    setError('')
    setLoading(true)
    try {
      const { data } = await login(username, password)
      localStorage.setItem('access_token', data.access)
      localStorage.setItem('refresh_token', data.refresh)
      onLogin(data.user ? { ...data.user, clients: data.clients } : null)
    } catch (err) {
      setError(err.response?.data?.error || 'Login failed. Check credentials.')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="login-page">
      <div className="login-card">
        <div className="login-logo">
          <div className="logo-icon" style={{ width: 52, height: 52, margin: '0 auto 12px', fontSize: 26, display: 'flex', alignItems: 'center', justifyContent: 'center', background: 'linear-gradient(135deg, #16a34a, #4ade80)', borderRadius: 12, boxShadow: '0 0 24px rgba(34,197,94,0.3)' }}>
            🌱
          </div>
          <h1 style={{ fontSize: '1.25rem', marginBottom: 4 }}>Breathe ESG</h1>
          <p style={{ fontSize: '0.875rem', color: 'var(--text-muted)' }}>Emissions Review Platform</p>
        </div>

        {error && <div className="error-msg">⚠ {error}</div>}

        <form onSubmit={handleSubmit}>
          <div className="form-group">
            <label htmlFor="login-username">Username</label>
            <input
              id="login-username"
              type="text"
              value={username}
              onChange={e => setUsername(e.target.value)}
              placeholder="analyst"
              required
              autoFocus
            />
          </div>
          <div className="form-group">
            <label htmlFor="login-password">Password</label>
            <input
              id="login-password"
              type="password"
              value={password}
              onChange={e => setPassword(e.target.value)}
              placeholder="••••••••"
              required
            />
          </div>

          <button
            type="submit"
            className="btn btn-primary w-full"
            style={{ marginTop: 8, justifyContent: 'center', padding: '10px' }}
            disabled={loading}
            id="btn-login"
          >
            {loading ? <><span className="spinner" style={{ width: 16, height: 16 }} />Signing in...</> : 'Sign in'}
          </button>
        </form>

        <div style={{ marginTop: 24, padding: '14px', background: 'var(--bg-surface)', borderRadius: 'var(--radius)', border: '1px solid var(--border)' }}>
          <div style={{ fontSize: '0.7rem', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.08em', color: 'var(--text-muted)', marginBottom: 8 }}>Demo Credentials</div>
          <div style={{ fontSize: '0.8125rem', color: 'var(--text-secondary)', display: 'flex', flexDirection: 'column', gap: 4 }}>
            <span><span style={{ color: 'var(--text-muted)' }}>Analyst:</span> <code style={{ fontFamily: 'var(--font-mono)', color: 'var(--green-400)' }}>analyst / demo1234</code></span>
            <span><span style={{ color: 'var(--text-muted)' }}>Admin:</span> <code style={{ fontFamily: 'var(--font-mono)', color: 'var(--green-400)' }}>admin / admin1234</code></span>
          </div>
        </div>
      </div>
    </div>
  )
}
