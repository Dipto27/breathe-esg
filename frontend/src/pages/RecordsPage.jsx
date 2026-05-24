import { useState, useEffect, useCallback } from 'react'
import { getRecords, getAuditTrail, approveRecord, flagRecord } from '../api/client'

const SCOPE_LABELS = { '1': 'Scope 1', '2': 'Scope 2', '3': 'Scope 3' }
const SOURCE_ICONS = { SAP: '⚙', UTILITY: '⚡', TRAVEL: '✈' }

function StatusBadge({ status }) {
  const cls = `badge badge-${status.toLowerCase()}`
  const icons = { PENDING: '○', FLAGGED: '⚑', APPROVED: '✓', LOCKED: '⊗' }
  return <span className={cls}>{icons[status] || ''} {status.toLowerCase()}</span>
}

function ScopeBadge({ scope }) {
  return <span className={`badge badge-scope${scope}`}>Scope {scope}</span>
}

function fmtNum(n, decimals = 0) {
  if (n == null) return '—'
  return Number(n).toLocaleString('en-US', { maximumFractionDigits: decimals })
}

function fmtDate(d) {
  if (!d) return '—'
  return new Date(d).toLocaleDateString('en-GB', { day: '2-digit', month: 'short', year: 'numeric' })
}

const AUDIT_ICONS = {
  CREATED: '●', APPROVED: '✓', FLAGGED: '⚑', LOCKED: '⊗', EDITED: '✎', UNFLAGGED: '○'
}

function RecordDetailPanel({ record, onClose, onApprove, onFlag }) {
  const [audit, setAudit] = useState([])
  const [flagReason, setFlagReason] = useState('')
  const [mode, setMode] = useState('detail') // 'detail' | 'flag'
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    if (record?.id) {
      getAuditTrail(record.id).then(r => setAudit(r.data)).catch(() => {})
    }
  }, [record?.id])

  const handleApprove = async () => {
    setLoading(true)
    await onApprove(record.id)
    setLoading(false)
  }

  const handleFlag = async () => {
    if (!flagReason.trim()) return
    setLoading(true)
    await onFlag(record.id, flagReason)
    setFlagReason('')
    setMode('detail')
    setLoading(false)
  }

  if (!record) return null

  return (
    <div className="overlay" onClick={e => e.target === e.currentTarget && onClose()}>
      <div className="detail-panel">
        <div className="panel-header">
          <div className="flex items-center justify-between">
            <div>
              <div className="flex items-center gap-2" style={{ marginBottom: 6 }}>
                <ScopeBadge scope={record.scope} />
                <StatusBadge status={record.status} />
              </div>
              <h3 style={{ fontSize: '0.875rem', color: 'var(--text-bright)' }}>
                {record.category.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase())}
              </h3>
            </div>
            <button className="btn btn-ghost btn-sm" onClick={onClose} id="btn-close-panel">✕</button>
          </div>

          {record.status !== 'LOCKED' && (
            <div className="flex gap-2 mt-3">
              <button
                className="btn btn-approve btn-sm"
                onClick={handleApprove}
                disabled={loading || record.status === 'APPROVED'}
                id={`btn-approve-${record.id}`}
              >
                ✓ Approve
              </button>
              <button
                className="btn btn-danger btn-sm"
                onClick={() => setMode(mode === 'flag' ? 'detail' : 'flag')}
                disabled={loading}
                id={`btn-flag-${record.id}`}
              >
                ⚑ Flag
              </button>
            </div>
          )}

          {mode === 'flag' && (
            <div style={{ marginTop: 12 }}>
              <textarea
                rows={3}
                placeholder="Describe why this record needs review..."
                value={flagReason}
                onChange={e => setFlagReason(e.target.value)}
                style={{ resize: 'vertical', marginBottom: 8 }}
                id={`flag-reason-${record.id}`}
              />
              <div className="flex gap-2">
                <button className="btn btn-danger btn-sm" onClick={handleFlag} disabled={!flagReason.trim() || loading}>
                  Submit Flag
                </button>
                <button className="btn btn-ghost btn-sm" onClick={() => setMode('detail')}>Cancel</button>
              </div>
            </div>
          )}
        </div>

        <div className="panel-body">
          {record.flag_reason && (
            <div style={{ background: 'rgba(245,158,11,0.08)', border: '1px solid rgba(245,158,11,0.3)', borderRadius: 8, padding: '10px 12px', marginBottom: 16 }}>
              <div style={{ fontSize: '0.7rem', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.08em', color: 'var(--amber-400)', marginBottom: 4 }}>⚑ Flag Reason</div>
              <div style={{ fontSize: '0.8125rem', color: 'var(--text-secondary)' }}>{record.flag_reason}</div>
            </div>
          )}

          <div className="section-title">Activity</div>
          <div className="field-row">
            <span className="field-label">Description</span>
            <span className="field-value" style={{ textAlign: 'right', maxWidth: '60%' }}>{record.activity_description || '—'}</span>
          </div>
          <div className="field-row">
            <span className="field-label">Source Ref</span>
            <span className="field-value mono">{record.source_row_ref || '—'}</span>
          </div>
          <div className="field-row">
            <span className="field-label">Date</span>
            <span className="field-value">{fmtDate(record.activity_date)}</span>
          </div>
          {record.billing_period_start && (
            <div className="field-row">
              <span className="field-label">Billing Period</span>
              <span className="field-value">{fmtDate(record.billing_period_start)} – {fmtDate(record.billing_period_end)}</span>
            </div>
          )}
          {record.origin && (
            <div className="field-row">
              <span className="field-label">Route</span>
              <span className="field-value">{record.origin} → {record.destination}</span>
            </div>
          )}
          {record.facility_name && (
            <div className="field-row">
              <span className="field-label">Facility</span>
              <span className="field-value">{record.facility_name} {record.facility_code ? `(${record.facility_code})` : ''}</span>
            </div>
          )}
          {record.cost_center && (
            <div className="field-row">
              <span className="field-label">Cost Center</span>
              <span className="field-value mono">{record.cost_center}</span>
            </div>
          )}

          <div className="section-title">Quantity & Emissions</div>
          <div className="field-row">
            <span className="field-label">Quantity (original)</span>
            <span className="field-value mono">{fmtNum(record.quantity, 2)} {record.unit}</span>
          </div>
          {record.quantity_normalized != null && record.unit_normalized !== record.unit && (
            <div className="field-row">
              <span className="field-label">Normalized</span>
              <span className="field-value mono">{fmtNum(record.quantity_normalized, 2)} {record.unit_normalized}</span>
            </div>
          )}
          <div className="field-row">
            <span className="field-label">Emission Factor</span>
            <span className="field-value mono">{record.emission_factor ? `${Number(record.emission_factor).toFixed(4)} kg CO₂e/${record.unit_normalized || record.unit}` : '—'}</span>
          </div>
          <div className="field-row">
            <span className="field-label">Factor Source</span>
            <span className="field-value" style={{ color: 'var(--text-muted)' }}>{record.emission_factor_source || '—'}</span>
          </div>
          <div className="field-row">
            <span className="field-label">CO₂e</span>
            <span className="field-value" style={{ fontWeight: 700, color: 'var(--green-400)' }}>
              {record.co2e_kg ? `${fmtNum(record.co2e_kg, 2)} kg` : '—'}
            </span>
          </div>
          {record.cost != null && (
            <div className="field-row">
              <span className="field-label">Cost</span>
              <span className="field-value">{fmtNum(record.cost, 2)} {record.currency}</span>
            </div>
          )}

          {record.reviewed_by_name && (
            <>
              <div className="section-title">Review</div>
              <div className="field-row">
                <span className="field-label">Reviewed by</span>
                <span className="field-value">{record.reviewed_by_name}</span>
              </div>
              <div className="field-row">
                <span className="field-label">Reviewed at</span>
                <span className="field-value">{fmtDate(record.reviewed_at)}</span>
              </div>
            </>
          )}

          {audit.length > 0 && (
            <>
              <div className="section-title">Audit Trail</div>
              <div className="audit-timeline">
                {audit.map((entry, i) => (
                  <div key={entry.id || i} className="audit-event">
                    <div className={`audit-dot audit-dot-${entry.action.toLowerCase()}`}>
                      {AUDIT_ICONS[entry.action] || '●'}
                    </div>
                    <div>
                      <div style={{ fontSize: '0.8125rem', color: 'var(--text-primary)', fontWeight: 500 }}>
                        {entry.action.charAt(0) + entry.action.slice(1).toLowerCase()}
                        <span style={{ color: 'var(--text-muted)', fontWeight: 400 }}> by {entry.actor_name}</span>
                      </div>
                      {entry.notes && <div style={{ fontSize: '0.75rem', color: 'var(--text-secondary)', marginTop: 2 }}>{entry.notes}</div>}
                      <div style={{ fontSize: '0.7rem', color: 'var(--text-muted)', marginTop: 2 }}>
                        {new Date(entry.timestamp).toLocaleString()}
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            </>
          )}
        </div>
      </div>
    </div>
  )
}

export default function RecordsPage({ user }) {
  const [records, setRecords] = useState([])
  const [loading, setLoading] = useState(true)
  const [selected, setSelected] = useState(null)
  const [clientId, setClientId] = useState(null)
  const [toast, setToast] = useState(null)
  const [filters, setFilters] = useState({ scope: '', source_type: '', status: '' })
  const [page, setPage] = useState(1)
  const [totalCount, setTotalCount] = useState(0)

  const showToast = (msg, type = 'success') => {
    setToast({ msg, type })
    setTimeout(() => setToast(null), 3000)
  }

  const loadRecords = useCallback(async (cid, f = {}, p = 1) => {
    if (!cid) return
    setLoading(true)
    try {
      const params = { page: p, ...Object.fromEntries(Object.entries(f).filter(([_, v]) => v)) }
      const { data } = await getRecords(cid, params)
      setRecords(data.results || data)
      setTotalCount(data.count || (data.results || data).length)
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
    loadRecords(cid, filters, page)

    const handler = (e) => {
      setClientId(e.detail?.id)
      loadRecords(e.detail?.id, filters, 1)
      setPage(1)
    }
    window.addEventListener('clientChanged', handler)
    return () => window.removeEventListener('clientChanged', handler)
  }, [user, loadRecords])

  const handleFilterChange = (key, val) => {
    const newFilters = { ...filters, [key]: val }
    setFilters(newFilters)
    setPage(1)
    loadRecords(clientId, newFilters, 1)
  }

  const handleApprove = async (id) => {
    try {
      const { data } = await approveRecord(id, '')
      setRecords(prev => prev.map(r => r.id === id ? data : r))
      if (selected?.id === id) setSelected(data)
      showToast('Record approved ✓', 'success')
    } catch (err) {
      showToast(err.response?.data?.error || 'Failed to approve', 'error')
    }
  }

  const handleFlag = async (id, reason) => {
    try {
      const { data } = await flagRecord(id, reason)
      setRecords(prev => prev.map(r => r.id === id ? data : r))
      if (selected?.id === id) setSelected(data)
      showToast('Record flagged ⚑', 'info')
    } catch (err) {
      showToast(err.response?.data?.error || 'Failed to flag', 'error')
    }
  }

  const fmtDate = (d) => d ? new Date(d).toLocaleDateString('en-GB', { day: '2-digit', month: 'short', year: '2-digit' }) : '—'
  const fmtNum = (n, dec = 0) => n != null ? Number(n).toLocaleString('en-US', { maximumFractionDigits: dec }) : '—'

  return (
    <>
      <div className="page-header">
        <div className="flex items-center justify-between">
          <div>
            <h1>Emission Records</h1>
            <p style={{ marginTop: 2 }}>{totalCount} records · Select a row to review and approve</p>
          </div>
          <button className="btn btn-ghost btn-sm" onClick={() => loadRecords(clientId, filters, page)} id="btn-refresh-records">
            ⟳ Refresh
          </button>
        </div>

        <div className="filters-bar">
          <select value={filters.scope} onChange={e => handleFilterChange('scope', e.target.value)} id="filter-scope">
            <option value="">All Scopes</option>
            <option value="1">Scope 1 (Fuel)</option>
            <option value="2">Scope 2 (Electricity)</option>
            <option value="3">Scope 3 (Travel)</option>
          </select>
          <select value={filters.source_type} onChange={e => handleFilterChange('source_type', e.target.value)} id="filter-source">
            <option value="">All Sources</option>
            <option value="SAP">SAP</option>
            <option value="UTILITY">Utility</option>
            <option value="TRAVEL">Travel</option>
          </select>
          <select value={filters.status} onChange={e => handleFilterChange('status', e.target.value)} id="filter-status">
            <option value="">All Statuses</option>
            <option value="PENDING">Pending</option>
            <option value="FLAGGED">Flagged</option>
            <option value="APPROVED">Approved</option>
            <option value="LOCKED">Locked</option>
          </select>
          <button className="btn btn-ghost btn-sm" onClick={() => {
            setFilters({ scope: '', source_type: '', status: '' })
            loadRecords(clientId, {}, 1)
          }} id="btn-clear-filters">Clear</button>
        </div>
      </div>

      <div className="page-content">
        {loading ? (
          <div className="loading-center"><div className="spinner" /> Loading records...</div>
        ) : records.length === 0 ? (
          <div className="empty-state">
            <div className="empty-state-icon">📋</div>
            <h3>No records found</h3>
            <p>Try adjusting filters or ingesting data first</p>
          </div>
        ) : (
          <div className="data-table-wrap">
            <table className="data-table">
              <thead>
                <tr>
                  <th>Source</th>
                  <th>Scope</th>
                  <th>Category</th>
                  <th>Description</th>
                  <th>Date</th>
                  <th style={{ textAlign: 'right' }}>Quantity</th>
                  <th style={{ textAlign: 'right' }}>CO₂e (kg)</th>
                  <th>Status</th>
                  <th>Actions</th>
                </tr>
              </thead>
              <tbody>
                {records.map(record => (
                  <tr
                    key={record.id}
                    onClick={() => setSelected(record)}
                    className={selected?.id === record.id ? 'selected' : ''}
                  >
                    <td>
                      <span title={record.source_type} style={{ fontSize: '1rem' }}>
                        {SOURCE_ICONS[record.source_type]}
                      </span>
                      <span style={{ color: 'var(--text-muted)', fontSize: '0.75rem', marginLeft: 6 }}>{record.source_type}</span>
                    </td>
                    <td><ScopeBadge scope={record.scope} /></td>
                    <td style={{ color: 'var(--text-secondary)', fontSize: '0.8125rem' }}>
                      {record.category.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase())}
                    </td>
                    <td style={{ maxWidth: 240 }} className="truncate" title={record.activity_description}>
                      {record.activity_description}
                    </td>
                    <td style={{ color: 'var(--text-muted)', fontSize: '0.8125rem' }}>{fmtDate(record.activity_date)}</td>
                    <td style={{ textAlign: 'right', fontFamily: 'var(--font-mono)', fontSize: '0.8125rem' }}>
                      {fmtNum(record.quantity, 1)} <span style={{ color: 'var(--text-muted)', fontSize: '0.7rem' }}>{record.unit}</span>
                    </td>
                    <td style={{ textAlign: 'right', fontFamily: 'var(--font-mono)', fontSize: '0.8125rem', color: 'var(--green-400)', fontWeight: 600 }}>
                      {fmtNum(record.co2e_kg, 1)}
                    </td>
                    <td><StatusBadge status={record.status} /></td>
                    <td onClick={e => e.stopPropagation()}>
                      <div className="flex gap-2">
                        {record.status !== 'LOCKED' && record.status !== 'APPROVED' && (
                          <button
                            className="btn btn-approve btn-sm"
                            onClick={() => handleApprove(record.id)}
                            id={`btn-approve-row-${record.id}`}
                          >✓</button>
                        )}
                        <button
                          className="btn btn-ghost btn-sm"
                          onClick={() => setSelected(record)}
                          id={`btn-detail-${record.id}`}
                        >→</button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {selected && (
        <RecordDetailPanel
          record={selected}
          onClose={() => setSelected(null)}
          onApprove={handleApprove}
          onFlag={handleFlag}
        />
      )}

      {toast && (
        <div className="toast-container">
          <div className={`toast toast-${toast.type}`}>{toast.msg}</div>
        </div>
      )}
    </>
  )
}
