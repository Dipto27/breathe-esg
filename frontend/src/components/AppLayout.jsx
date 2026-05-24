import { useLocation, useNavigate } from 'react-router-dom'
import { useState, useEffect } from 'react'
import { getClients } from '../api/client'

const NAV_ITEMS = [
  { path: '/', icon: '◈', label: 'Dashboard' },
  { path: '/records', icon: '≡', label: 'Records' },
  { path: '/ingest', icon: '↑', label: 'Ingest Data' },
  { path: '/jobs', icon: '⟳', label: 'Jobs' },
]

export default function AppLayout({ user, onLogout, children }) {
  const location = useLocation()
  const navigate = useNavigate()
  const [clients, setClients] = useState([])
  const [activeClient, setActiveClient] = useState(null)

  useEffect(() => {
    // Load clients from user memberships
    const userClients = user?.clients || []
    setClients(userClients)

    const stored = localStorage.getItem('active_client')
    if (stored) {
      try {
        setActiveClient(JSON.parse(stored))
      } catch (_) {
        setActiveClient(userClients[0] || null)
      }
    } else {
      setActiveClient(userClients[0] || null)
    }
  }, [user])

  const handleClientChange = (e) => {
    const cid = parseInt(e.target.value)
    const c = clients.find(cl => cl.id === cid)
    setActiveClient(c)
    localStorage.setItem('active_client', JSON.stringify(c))
    // Notify pages via storage event is overkill; we use context or prop drill
    window.dispatchEvent(new CustomEvent('clientChanged', { detail: c }))
  }

  const initials = (user?.full_name || user?.username || 'U')
    .split(' ').map(w => w[0]).join('').toUpperCase().slice(0, 2)

  return (
    <div className="layout">
      <aside className="sidebar">
        <div className="sidebar-logo">
          <div className="logo-mark">
            <div className="logo-icon">🌱</div>
            <div>
              <div className="logo-text">Breathe ESG</div>
              <div className="logo-subtitle">Emissions Platform</div>
            </div>
          </div>
        </div>

        <nav className="sidebar-nav">
          <div className="nav-section-label">Navigation</div>
          {NAV_ITEMS.map(item => (
            <button
              key={item.path}
              className={`nav-item ${location.pathname === item.path ? 'active' : ''}`}
              onClick={() => navigate(item.path)}
              id={`nav-${item.label.toLowerCase().replace(/\s/g,'-')}`}
            >
              <span className="nav-icon">{item.icon}</span>
              <span>{item.label}</span>
            </button>
          ))}

          {clients.length > 0 && (
            <>
              <div className="nav-section-label" style={{ marginTop: 16 }}>Client</div>
              <div style={{ padding: '4px 2px' }}>
                <select
                  value={activeClient?.id || ''}
                  onChange={handleClientChange}
                  style={{ fontSize: '0.8125rem' }}
                  id="client-select"
                >
                  {clients.map(c => (
                    <option key={c.id} value={c.id}>{c.name}</option>
                  ))}
                </select>
              </div>
            </>
          )}
        </nav>

        <div className="sidebar-footer">
          <div className="user-info">
            <div className="user-avatar">{initials}</div>
            <div style={{ flex: 1, minWidth: 0 }}>
              <div style={{ fontSize: '0.8125rem', fontWeight: 600, color: 'var(--text-primary)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                {user?.full_name || user?.username}
              </div>
              <div style={{ fontSize: '0.7rem', color: 'var(--text-muted)' }}>
                {activeClient?.role || 'Analyst'}
              </div>
            </div>
          </div>
          <button className="nav-item" onClick={onLogout} id="btn-logout" style={{ width: '100%', color: 'var(--red-400)' }}>
            <span className="nav-icon">⊗</span>
            <span>Sign out</span>
          </button>
        </div>
      </aside>

      <main className="main-content">
        {children}
      </main>
    </div>
  )
}
