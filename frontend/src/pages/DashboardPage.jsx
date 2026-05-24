import { useState, useEffect, useCallback } from 'react'
import { getSummary, loadSampleData } from '../api/client'
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, PieChart, Pie, Cell, Legend } from 'recharts'

const SCOPE_COLORS = { 'Scope 1': '#fc8181', 'Scope 2': '#60a5fa', 'Scope 3': '#c084fc' }
const SOURCE_COLORS = { SAP: '#fc8181', UTILITY: '#60a5fa', TRAVEL: '#c084fc' }
const STATUS_COLORS = { PENDING: '#60a5fa', FLAGGED: '#fbbf24', APPROVED: '#22c55e', LOCKED: '#a855f7' }

function fmtCO2(kg) {
  if (kg >= 1_000_000) return `${(kg / 1_000_000).toFixed(1)} kt`
  if (kg >= 1_000) return `${(kg / 1_000).toFixed(1)} t`
  return `${kg.toFixed(0)} kg`
}

export default function DashboardPage({ user }) {
  const [summary, setSummary] = useState(null)
  const [loading, setLoading] = useState(true)
  const [loadingDemo, setLoadingDemo] = useState(false)
  const [clientId, setClientId] = useState(null)
  const [toast, setToast] = useState(null)

  const showToast = (msg, type = 'success') => {
    setToast({ msg, type })
    setTimeout(() => setToast(null), 3500)
  }

  const loadSummary = useCallback(async (cid) => {
    if (!cid) return
    setLoading(true)
    try {
      const { data } = await getSummary(cid)
      setSummary(data)
    } catch (err) {
      console.error(err)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    const stored = localStorage.getItem('active_client')
    const cid = stored ? JSON.parse(stored).id : user?.clients?.[0]?.id
    setClientId(cid)
    loadSummary(cid)

    const handler = (e) => {
      setClientId(e.detail?.id)
      loadSummary(e.detail?.id)
    }
    window.addEventListener('clientChanged', handler)
    return () => window.removeEventListener('clientChanged', handler)
  }, [user, loadSummary])

  const handleLoadDemo = async () => {
    if (!clientId) return
    setLoadingDemo(true)
    try {
      const { data } = await loadSampleData(clientId)
      showToast(`Loaded ${data.records_created} sample records`, 'success')
      loadSummary(clientId)
    } catch (err) {
      showToast('Failed to load sample data', 'error')
    } finally {
      setLoadingDemo(false)
    }
  }

  const scopeChartData = summary ? [
    { name: 'Scope 1', value: summary.by_scope.scope_1?.co2e_kg || 0, count: summary.by_scope.scope_1?.count },
    { name: 'Scope 2', value: summary.by_scope.scope_2?.co2e_kg || 0, count: summary.by_scope.scope_2?.count },
    { name: 'Scope 3', value: summary.by_scope.scope_3?.co2e_kg || 0, count: summary.by_scope.scope_3?.count },
  ] : []

  const sourceChartData = summary ? [
    { name: 'SAP (Fuel)', value: summary.by_source.SAP?.co2e_kg || 0 },
    { name: 'Utility (Elec)', value: summary.by_source.UTILITY?.co2e_kg || 0 },
    { name: 'Travel', value: summary.by_source.TRAVEL?.co2e_kg || 0 },
  ] : []

  const statusData = summary ? Object.entries(summary.status_counts).map(([k, v]) => ({
    name: k.charAt(0) + k.slice(1).toLowerCase(),
    value: v,
  })) : []

  const CustomTooltip = ({ active, payload, label }) => {
    if (active && payload?.length) {
      return (
        <div style={{ background: 'var(--bg-elevated)', border: '1px solid var(--border)', borderRadius: 8, padding: '10px 14px' }}>
          <div style={{ color: 'var(--text-muted)', fontSize: '0.75rem', marginBottom: 4 }}>{label || payload[0].name}</div>
          <div style={{ color: 'var(--text-bright)', fontWeight: 600 }}>{fmtCO2(payload[0].value)} CO₂e</div>
        </div>
      )
    }
    return null
  }

  return (
    <>
      <div className="page-header">
        <div className="flex items-center justify-between">
          <div>
            <h1>Dashboard</h1>
            <p style={{ marginTop: 2 }}>Emissions overview and review status</p>
          </div>
          <button
            className="btn btn-ghost"
            onClick={handleLoadDemo}
            disabled={loadingDemo || !clientId}
            id="btn-load-demo"
          >
            {loadingDemo ? <><span className="spinner" style={{ width: 14, height: 14 }} /> Loading...</> : '⊕ Load Sample Data'}
          </button>
        </div>
      </div>

      <div className="page-content">
        {loading ? (
          <div className="loading-center">
            <div className="spinner" />
            <span>Loading emissions data...</span>
          </div>
        ) : !summary || summary.total_records === 0 ? (
          <div className="empty-state">
            <div className="empty-state-icon">📊</div>
            <h3>No emissions data yet</h3>
            <p style={{ marginBottom: 16 }}>Load the sample dataset or upload a file via Ingest Data</p>
            <button className="btn btn-primary" onClick={handleLoadDemo} disabled={loadingDemo} id="btn-load-demo-empty">
              ⊕ Load Sample Data
            </button>
          </div>
        ) : (
          <>
            {/* Summary metrics */}
            <div className="metrics-grid">
              <div className="metric-card green">
                <div className="metric-label">Total CO₂e</div>
                <div className="metric-value">{fmtCO2(summary.total_co2e_kg)}</div>
                <div className="metric-sub">{summary.total_records} records</div>
              </div>
              <div className="metric-card red">
                <div className="metric-label">Scope 1 (Direct)</div>
                <div className="metric-value">{fmtCO2(summary.by_scope.scope_1?.co2e_kg || 0)}</div>
                <div className="metric-sub">{summary.by_scope.scope_1?.count || 0} fuel records</div>
              </div>
              <div className="metric-card blue">
                <div className="metric-label">Scope 2 (Electricity)</div>
                <div className="metric-value">{fmtCO2(summary.by_scope.scope_2?.co2e_kg || 0)}</div>
                <div className="metric-sub">{summary.by_scope.scope_2?.count || 0} utility records</div>
              </div>
              <div className="metric-card purple">
                <div className="metric-label">Scope 3 (Travel)</div>
                <div className="metric-value">{fmtCO2(summary.by_scope.scope_3?.co2e_kg || 0)}</div>
                <div className="metric-sub">{summary.by_scope.scope_3?.count || 0} travel records</div>
              </div>
              <div className="metric-card amber">
                <div className="metric-label">Needs Review</div>
                <div className="metric-value" style={{ color: 'var(--amber-400)' }}>
                  {(summary.status_counts.PENDING || 0) + (summary.status_counts.FLAGGED || 0)}
                </div>
                <div className="metric-sub">{summary.status_counts.FLAGGED || 0} flagged, {summary.status_counts.PENDING || 0} pending</div>
              </div>
              <div className="metric-card green">
                <div className="metric-label">Approved</div>
                <div className="metric-value" style={{ color: 'var(--green-400)' }}>
                  {summary.status_counts.APPROVED || 0}
                </div>
                <div className="metric-sub">Ready for audit lock</div>
              </div>
            </div>

            {/* Charts */}
            <div className="chart-grid">
              <div className="card">
                <div className="card-header">
                  <h3>CO₂e by Scope</h3>
                </div>
                <ResponsiveContainer width="100%" height={200}>
                  <BarChart data={scopeChartData} margin={{ top: 4, right: 8, bottom: 4, left: 8 }}>
                    <XAxis dataKey="name" tick={{ fill: 'var(--text-muted)', fontSize: 12 }} axisLine={false} tickLine={false} />
                    <YAxis tickFormatter={v => fmtCO2(v)} tick={{ fill: 'var(--text-muted)', fontSize: 11 }} axisLine={false} tickLine={false} />
                    <Tooltip content={<CustomTooltip />} />
                    <Bar dataKey="value" radius={[4, 4, 0, 0]}>
                      {scopeChartData.map((entry, i) => (
                        <Cell key={i} fill={SCOPE_COLORS[entry.name]} />
                      ))}
                    </Bar>
                  </BarChart>
                </ResponsiveContainer>
              </div>

              <div className="card">
                <div className="card-header">
                  <h3>CO₂e by Source</h3>
                </div>
                <ResponsiveContainer width="100%" height={200}>
                  <PieChart>
                    <Pie data={sourceChartData} dataKey="value" nameKey="name" cx="50%" cy="50%" outerRadius={75} paddingAngle={3}>
                      {sourceChartData.map((entry, i) => (
                        <Cell key={i} fill={SOURCE_COLORS[entry.name.split(' ')[0]]} />
                      ))}
                    </Pie>
                    <Tooltip formatter={(v) => fmtCO2(v)} contentStyle={{ background: 'var(--bg-elevated)', border: '1px solid var(--border)', borderRadius: 8, fontSize: '0.8125rem' }} />
                    <Legend formatter={(v) => <span style={{ color: 'var(--text-secondary)', fontSize: '0.8125rem' }}>{v}</span>} />
                  </PieChart>
                </ResponsiveContainer>
              </div>

              <div className="card">
                <div className="card-header">
                  <h3>Review Status Distribution</h3>
                </div>
                <ResponsiveContainer width="100%" height={200}>
                  <BarChart data={statusData} layout="vertical" margin={{ top: 4, right: 8, bottom: 4, left: 40 }}>
                    <XAxis type="number" tick={{ fill: 'var(--text-muted)', fontSize: 11 }} axisLine={false} tickLine={false} />
                    <YAxis dataKey="name" type="category" tick={{ fill: 'var(--text-secondary)', fontSize: 12 }} axisLine={false} tickLine={false} />
                    <Tooltip contentStyle={{ background: 'var(--bg-elevated)', border: '1px solid var(--border)', borderRadius: 8 }} />
                    <Bar dataKey="value" radius={[0, 4, 4, 0]}>
                      {statusData.map((entry, i) => (
                        <Cell key={i} fill={STATUS_COLORS[entry.name.toUpperCase()] || 'var(--border)'} />
                      ))}
                    </Bar>
                  </BarChart>
                </ResponsiveContainer>
              </div>

              <div className="card">
                <div className="card-header">
                  <h3>Source Breakdown</h3>
                </div>
                <div style={{ padding: '8px 0' }}>
                  {['SAP', 'UTILITY', 'TRAVEL'].map(src => {
                    const d = summary.by_source[src]
                    const pct = summary.total_co2e_kg > 0 ? (d.co2e_kg / summary.total_co2e_kg * 100) : 0
                    return (
                      <div key={src} style={{ marginBottom: 16 }}>
                        <div className="flex justify-between mb-2">
                          <span style={{ fontSize: '0.8125rem', color: 'var(--text-secondary)' }}>
                            {src === 'SAP' ? 'SAP (Fuel)' : src === 'UTILITY' ? 'Utility (Electricity)' : 'Corporate Travel'}
                          </span>
                          <span style={{ fontSize: '0.8125rem', color: 'var(--text-primary)', fontWeight: 600 }}>
                            {fmtCO2(d.co2e_kg)} <span style={{ color: 'var(--text-muted)', fontWeight: 400 }}>({pct.toFixed(1)}%)</span>
                          </span>
                        </div>
                        <div className="progress-bar">
                          <div className="progress-fill" style={{
                            width: `${pct}%`,
                            background: src === 'SAP' ? 'linear-gradient(90deg, #ef4444, #fc8181)' :
                              src === 'UTILITY' ? 'linear-gradient(90deg, #3b82f6, #60a5fa)' :
                                'linear-gradient(90deg, #a855f7, #c084fc)'
                          }} />
                        </div>
                        <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', marginTop: 4 }}>{d.count} records</div>
                      </div>
                    )
                  })}
                </div>
              </div>
            </div>
          </>
        )}
      </div>

      {toast && (
        <div className="toast-container">
          <div className={`toast toast-${toast.type}`}>{toast.msg}</div>
        </div>
      )}
    </>
  )
}
