import { useState, useRef } from 'react'
import { ingestFile } from '../api/client'

const SOURCE_TYPES = [
  {
    id: 'SAP',
    icon: '⚙',
    label: 'SAP Fuel & Procurement',
    description: 'MB51 material movement export. Scope 1 fuel data.',
    color: 'var(--red-400)',
    accent: 'rgba(239,68,68,0.1)',
    headers: 'MBLNR, BUDAT, MATNR, MAKTX, MENGE, MEINS, WERKS, KOSTL, WRBTR, WAERS',
    example: `MBLNR,BUDAT,MATNR,MAKTX,MENGE,MEINS,WERKS,KOSTL,WRBTR,WAERS
4900001234,20240115,DIESEL001,Diesel HSD,12500,L,1000,CC-MAINT-01,18750.00,EUR
4900001289,20240128,DIESEL001,Diesel HSD,8300,L,1100,CC-OPS-02,12450.00,EUR
4900001310,20240210,NATGAS001,Natural Gas,4200,M3,1000,CC-HEAT-01,5040.00,EUR
4900001402,20240222,PETROL001,Petrol Unleaded,3100,L,2000,CC-FLEET-01,4650.00,EUR
4900001455,20240305,DIESEL001,Diesel HSD,6800,L,3000,CC-OPS-SG,10200.00,SGD`
  },
  {
    id: 'UTILITY',
    icon: '⚡',
    label: 'Utility / Electricity',
    description: 'Portal CSV export. Scope 2 purchased electricity.',
    color: 'var(--blue-400)',
    accent: 'rgba(59,130,246,0.1)',
    headers: 'account_number, meter_id, service_address, billing_period_start, billing_period_end, usage_kwh, amount_due, currency',
    example: `account_number,meter_id,service_address,billing_period_start,billing_period_end,usage_kwh,demand_kw,rate_schedule,amount_due,currency,read_type
ACC-DE-1000,HH-001,Hamburg Plant Main Meter,2024-01-01,2024-01-31,245000,480,HV-INDUSTRIAL,36750.00,EUR,ACTUAL
ACC-DE-1100,BE-002,Berlin Plant Main Meter,2024-01-01,2024-01-31,178000,350,HV-INDUSTRIAL,26700.00,EUR,ACTUAL
ACC-US-2000,NY-010,New York Office,2024-02-01,2024-02-29,42000,85,COMMERCIAL-C,8400.00,USD,ESTIMATED`
  },
  {
    id: 'TRAVEL',
    icon: '✈',
    label: 'Corporate Travel',
    description: 'Concur expense export. Scope 3 air, hotel, ground.',
    color: 'var(--purple-400)',
    accent: 'rgba(168,85,247,0.1)',
    headers: 'report_id, employee_id, expense_date, expense_type, vendor, city_from, city_to, distance_km, nights, amount, currency',
    example: `report_id,employee_id,expense_date,expense_type,vendor,city_from,city_to,distance_km,nights,amount,currency,project_code
CONC-R001,EMP-0042,2024-01-10,Airfare,United Airlines,JFK,LHR,5570,,1850.00,USD,PROJ-ESG-2024
CONC-R001,EMP-0042,2024-01-14,Hotel,Marriott London,,London UK,,4,1200.00,GBP,PROJ-ESG-2024
CONC-R002,EMP-0078,2024-01-22,Airfare,Lufthansa,FRA,SIN,10250,,2400.00,EUR,PROJ-OPS-SG
CONC-R003,EMP-0121,2024-02-05,Airfare,American Airlines,ORD,AMS,,,1650.00,USD,PROJ-SALES-EU
CONC-R003,EMP-0121,2024-02-08,Car Rental,Hertz,Chicago IL,,,320,420.00,USD,PROJ-SALES-EU`
  },
]

export default function IngestPage({ user }) {
  const [selectedType, setSelectedType] = useState(null)
  const [file, setFile] = useState(null)
  const [dragging, setDragging] = useState(false)
  const [loading, setLoading] = useState(false)
  const [result, setResult] = useState(null)
  const [error, setError] = useState(null)
  const [showExample, setShowExample] = useState(false)
  const fileRef = useRef()

  const clientId = (() => {
    const stored = localStorage.getItem('active_client')
    return stored ? JSON.parse(stored).id : user?.clients?.[0]?.id
  })()

  const handleDrop = (e) => {
    e.preventDefault()
    setDragging(false)
    const f = e.dataTransfer.files[0]
    if (f) setFile(f)
  }

  const handleFileChange = (e) => {
    setFile(e.target.files[0])
    setResult(null)
    setError(null)
  }

  const handleIngest = async () => {
    if (!file || !selectedType || !clientId) return
    setLoading(true)
    setResult(null)
    setError(null)
    try {
      const label = `${selectedType.label} — ${new Date().toLocaleDateString()}`
      const { data } = await ingestFile(clientId, file, selectedType.id, label)
      setResult(data)
      setFile(null)
      if (fileRef.current) fileRef.current.value = ''
    } catch (err) {
      setError(err.response?.data?.error || 'Ingestion failed')
    } finally {
      setLoading(false)
    }
  }

  const downloadExample = (type) => {
    const blob = new Blob([type.example], { type: 'text/csv' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `sample_${type.id.toLowerCase()}.csv`
    a.click()
    URL.revokeObjectURL(url)
  }

  return (
    <>
      <div className="page-header">
        <h1>Ingest Data</h1>
        <p style={{ marginTop: 2 }}>Upload a CSV file from one of the three supported source types</p>
      </div>

      <div className="page-content">
        {/* Source type selector */}
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 16, marginBottom: 24 }}>
          {SOURCE_TYPES.map(type => (
            <div
              key={type.id}
              onClick={() => { setSelectedType(type); setResult(null); setError(null) }}
              style={{
                background: selectedType?.id === type.id ? type.accent : 'var(--bg-card)',
                border: `1px solid ${selectedType?.id === type.id ? type.color : 'var(--border)'}`,
                borderRadius: 'var(--radius-lg)',
                padding: '18px',
                cursor: 'pointer',
                transition: 'all 0.15s',
              }}
              id={`source-type-${type.id.toLowerCase()}`}
            >
              <div style={{ fontSize: '1.5rem', marginBottom: 8 }}>{type.icon}</div>
              <div style={{ fontWeight: 600, color: 'var(--text-bright)', marginBottom: 4, fontSize: '0.9375rem' }}>{type.label}</div>
              <div style={{ fontSize: '0.8125rem', color: 'var(--text-muted)', lineHeight: 1.5 }}>{type.description}</div>

              {selectedType?.id === type.id && (
                <div style={{ marginTop: 12, paddingTop: 12, borderTop: '1px solid var(--border-light)' }}>
                  <div style={{ fontSize: '0.7rem', color: 'var(--text-muted)', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.06em', marginBottom: 4 }}>Expected headers</div>
                  <code style={{ fontSize: '0.7rem', color: type.color, fontFamily: 'var(--font-mono)', lineHeight: 1.6 }}>
                    {type.headers}
                  </code>
                </div>
              )}
            </div>
          ))}
        </div>

        {selectedType && (
          <div className="card" style={{ marginBottom: 16 }}>
            <div className="card-header">
              <h3>Upload {selectedType.label} File</h3>
              <div className="flex gap-2">
                <button
                  className="btn btn-ghost btn-sm"
                  onClick={() => downloadExample(selectedType)}
                  id={`btn-download-sample-${selectedType.id.toLowerCase()}`}
                >
                  ↓ Download Sample CSV
                </button>
                <button
                  className="btn btn-ghost btn-sm"
                  onClick={() => setShowExample(!showExample)}
                  id="btn-show-example"
                >
                  {showExample ? 'Hide' : 'Show'} Example
                </button>
              </div>
            </div>

            {showExample && (
              <div style={{ background: 'var(--bg-surface)', border: '1px solid var(--border-light)', borderRadius: 'var(--radius)', padding: '12px', marginBottom: 16, overflow: 'auto' }}>
                <pre style={{ fontFamily: 'var(--font-mono)', fontSize: '0.7rem', color: 'var(--text-secondary)', whiteSpace: 'pre', margin: 0 }}>
                  {selectedType.example}
                </pre>
              </div>
            )}

            <div
              className={`upload-zone ${dragging ? 'dragging' : ''}`}
              onDragOver={e => { e.preventDefault(); setDragging(true) }}
              onDragLeave={() => setDragging(false)}
              onDrop={handleDrop}
              onClick={() => fileRef.current?.click()}
              id="upload-dropzone"
            >
              <div className="upload-icon">📁</div>
              {file ? (
                <>
                  <div style={{ fontWeight: 600, color: 'var(--green-400)', marginBottom: 4 }}>✓ {file.name}</div>
                  <div style={{ color: 'var(--text-muted)', fontSize: '0.8125rem' }}>{(file.size / 1024).toFixed(1)} KB</div>
                </>
              ) : (
                <>
                  <div style={{ fontWeight: 500, color: 'var(--text-primary)', marginBottom: 4 }}>Drop CSV file here or click to browse</div>
                  <div style={{ color: 'var(--text-muted)', fontSize: '0.8125rem' }}>UTF-8 or Excel-exported CSV</div>
                </>
              )}
              <input
                ref={fileRef}
                type="file"
                accept=".csv,text/csv"
                style={{ display: 'none' }}
                onChange={handleFileChange}
                id="file-input"
              />
            </div>

            <div style={{ marginTop: 16, display: 'flex', gap: 12 }}>
              <button
                className="btn btn-primary"
                onClick={handleIngest}
                disabled={!file || loading || !clientId}
                id="btn-ingest"
              >
                {loading
                  ? <><span className="spinner" style={{ width: 14, height: 14 }} /> Processing...</>
                  : `↑ Ingest ${selectedType.label}`
                }
              </button>
              {file && (
                <button className="btn btn-ghost" onClick={() => { setFile(null); if (fileRef.current) fileRef.current.value = '' }} id="btn-clear-file">
                  Clear
                </button>
              )}
            </div>
          </div>
        )}

        {result && (
          <div style={{ background: 'rgba(34,197,94,0.08)', border: '1px solid rgba(34,197,94,0.3)', borderRadius: 'var(--radius-lg)', padding: '20px' }}>
            <div style={{ fontWeight: 600, color: 'var(--green-400)', marginBottom: 12, fontSize: '1rem' }}>✓ Ingestion Complete</div>
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3,1fr)', gap: 16 }}>
              {[
                { label: 'Rows Ingested', value: result.rows_ingested, color: 'var(--green-400)' },
                { label: 'Rows Skipped', value: result.rows_skipped ?? 0, color: 'var(--text-secondary)' },
                { label: 'Errors', value: result.errors?.length ?? 0, color: result.errors?.length ? 'var(--red-400)' : 'var(--text-muted)' },
              ].map(item => (
                <div key={item.label} style={{ textAlign: 'center' }}>
                  <div style={{ fontSize: '1.5rem', fontWeight: 700, color: item.color }}>{item.value}</div>
                  <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.06em' }}>{item.label}</div>
                </div>
              ))}
            </div>
            {result.errors?.length > 0 && (
              <div style={{ marginTop: 16, paddingTop: 12, borderTop: '1px solid rgba(34,197,94,0.2)' }}>
                <div style={{ fontSize: '0.8125rem', color: 'var(--amber-400)', marginBottom: 6 }}>⚠ Parse errors (rows skipped)</div>
                {result.errors.map((e, i) => (
                  <div key={i} style={{ fontSize: '0.75rem', color: 'var(--text-secondary)', fontFamily: 'var(--font-mono)', marginBottom: 2 }}>
                    Row {e.row}: {e.message}
                  </div>
                ))}
              </div>
            )}
          </div>
        )}

        {error && (
          <div className="error-msg">⚠ {error}</div>
        )}
      </div>
    </>
  )
}
