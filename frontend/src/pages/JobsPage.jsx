import { useState, useEffect, useCallback } from 'react'
import { getJobs } from '../api/client'

function StatusBadge({ status }) {
  const cls = `badge badge-${status.toLowerCase()}`
  const icons = { DONE: '✓', FAILED: '✕', PROCESSING: '↻', PENDING: '○' }
  return <span className={cls}>{icons[status] || ''} {status.toLowerCase()}</span>
}

function fmtDate(d) {
  if (!d) return '—'
  return new Date(d).toLocaleString()
}

export default function JobsPage({ user }) {
  const [jobs, setJobs] = useState([])
  const [loading, setLoading] = useState(true)
  const [expanded, setExpanded] = useState(null)
  const [clientId, setClientId] = useState(null)

  const loadJobs = useCallback(async (cid) => {
    if (!cid) return
    setLoading(true)
    try {
      const { data } = await getJobs(cid)
      setJobs(data.results || data)
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
    loadJobs(cid)

    const handler = (e) => {
      setClientId(e.detail?.id)
      loadJobs(e.detail?.id)
    }
    window.addEventListener('clientChanged', handler)
    return () => window.removeEventListener('clientChanged', handler)
  }, [user, loadJobs])

  const SOURCE_ICONS = { SAP: '⚙', UTILITY: '⚡', TRAVEL: '✈' }

  return (
    <>
      <div className="page-header">
        <div className="flex items-center justify-between">
          <div>
            <h1>Ingestion Jobs</h1>
            <p style={{ marginTop: 2 }}>History of all data ingestion runs</p>
          </div>
          <button className="btn btn-ghost btn-sm" onClick={() => loadJobs(clientId)} id="btn-refresh-jobs">
            ⟳ Refresh
          </button>
        </div>
      </div>

      <div className="page-content">
        {loading ? (
          <div className="loading-center"><div className="spinner" /> Loading...</div>
        ) : jobs.length === 0 ? (
          <div className="empty-state">
            <div className="empty-state-icon">⟳</div>
            <h3>No ingestion jobs yet</h3>
            <p>Upload a CSV via the Ingest Data page</p>
          </div>
        ) : (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
            {jobs.map(job => (
              <div key={job.id} className="card" style={{ padding: 0, cursor: 'pointer' }} onClick={() => setExpanded(expanded === job.id ? null : job.id)}>
                <div style={{ padding: '16px 20px', display: 'flex', alignItems: 'center', gap: 16 }}>
                  <div style={{ fontSize: '1.25rem' }}>{SOURCE_ICONS[job.source_type] || '●'}</div>
                  <div style={{ flex: 1 }}>
                    <div style={{ fontWeight: 600, color: 'var(--text-bright)', marginBottom: 2 }}>
                      {job.data_source_label}
                    </div>
                    <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>
                      Job #{job.id} · {fmtDate(job.created_at)}
                    </div>
                  </div>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 16 }}>
                    <div style={{ textAlign: 'right' }}>
                      <div style={{ fontSize: '0.8125rem', fontWeight: 600, color: 'var(--green-400)' }}>{job.row_count} rows</div>
                      {job.error_count > 0 && (
                        <div style={{ fontSize: '0.75rem', color: 'var(--amber-400)' }}>{job.error_count} errors</div>
                      )}
                    </div>
                    <StatusBadge status={job.status} />
                    <span style={{ color: 'var(--text-muted)', transition: 'transform 0.2s', transform: expanded === job.id ? 'rotate(180deg)' : 'none' }}>▾</span>
                  </div>
                </div>

                {expanded === job.id && (
                  <div style={{ borderTop: '1px solid var(--border-light)', padding: '16px 20px', background: 'var(--bg-surface)' }}
                    onClick={e => e.stopPropagation()}>
                    <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4,1fr)', gap: 16, marginBottom: 16 }}>
                      {[
                        { label: 'Source Type', value: job.source_type },
                        { label: 'Started', value: fmtDate(job.started_at) },
                        { label: 'Completed', value: fmtDate(job.completed_at) },
                        { label: 'Duration', value: job.started_at && job.completed_at
                          ? `${((new Date(job.completed_at) - new Date(job.started_at)) / 1000).toFixed(1)}s`
                          : '—' },
                      ].map(item => (
                        <div key={item.label}>
                          <div style={{ fontSize: '0.7rem', textTransform: 'uppercase', letterSpacing: '0.07em', color: 'var(--text-muted)', marginBottom: 3 }}>{item.label}</div>
                          <div style={{ fontSize: '0.875rem', color: 'var(--text-primary)' }}>{item.value}</div>
                        </div>
                      ))}
                    </div>

                    {job.errors && job.errors.length > 0 && (
                      <div>
                        <div style={{ fontSize: '0.75rem', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.07em', color: 'var(--amber-400)', marginBottom: 8 }}>
                          ⚠ Parse Errors
                        </div>
                        <div style={{ background: 'var(--bg-base)', borderRadius: 'var(--radius)', padding: '10px 14px', maxHeight: 180, overflowY: 'auto' }}>
                          {job.errors.map((e, i) => (
                            <div key={i} style={{ fontFamily: 'var(--font-mono)', fontSize: '0.75rem', color: 'var(--text-secondary)', marginBottom: 4 }}>
                              <span style={{ color: 'var(--amber-400)' }}>Row {e.row}: </span>{e.message}
                            </div>
                          ))}
                        </div>
                      </div>
                    )}
                  </div>
                )}
              </div>
            ))}
          </div>
        )}
      </div>
    </>
  )
}
