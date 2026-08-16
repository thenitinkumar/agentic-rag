import Logo from './Logo'

function statusInfo(health) {
  if (!health)                    return { state: 'connecting', label: 'connecting…' }
  if (health.error)               return { state: 'error',      label: 'server unreachable' }
  if (!health.vector_index_ready) return { state: 'warn',       label: 'index not built — run ingest' }
  if (health.mock_llm)            return { state: 'mock',       label: `mock · ${health.companies_loaded} cos.` }
  return { state: 'live', label: `live · ${health.companies_loaded} companies` }
}

export default function Topbar({ health }) {
  const { state, label } = statusInfo(health)
  return (
    <header className="topbar">
      <div className="brand">
        <Logo size={22} />
        <span className="brand-name">Earnings<br />Intelligence</span>
      </div>
      <div className="status-indicator">
        <span className={`status-dot ${state}`} />
        <span>{label}</span>
      </div>
    </header>
  )
}
