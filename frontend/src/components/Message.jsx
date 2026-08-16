import { useState, useEffect } from 'react'

/* ── Streaming text with blinking cursor ─────────────── */
function StreamingText({ text }) {
  const [idx, setIdx] = useState(0)

  useEffect(() => {
    if (!text || idx >= text.length) return
    const id = setTimeout(() => setIdx(i => i + 1), 8)
    return () => clearTimeout(id)
  }, [text, idx])

  const done = !text || idx >= text.length
  return (
    <>
      {text && text.slice(0, idx)}
      {!done && <span className="typing-cursor" aria-hidden="true" />}
    </>
  )
}

/* ── Pulsing skeleton while backend processes ────────── */
function Skeleton() {
  return (
    <div className="skeleton" aria-label="Loading response…">
      <div className="sk-line" style={{ width: '91%' }} />
      <div className="sk-line" style={{ width: '75%' }} />
      <div className="sk-line" style={{ width: '83%' }} />
      <div className="sk-line" style={{ width: '44%' }} />
    </div>
  )
}

/* ── Animated accordion panel (replaces <details>) ───── */
function Panel({ title, count, children }) {
  const [open, setOpen] = useState(false)

  return (
    <div className={`panel${open ? ' panel--open' : ''}`}>
      <button className="panel-summary" onClick={() => setOpen(o => !o)}>
        <svg
          className={`p-chevron${open ? ' p-chevron--open' : ''}`}
          width="10" height="10" viewBox="0 0 10 10" fill="none"
          aria-hidden="true"
        >
          <path
            d="M2.5 4L5 6.5L7.5 4"
            stroke="currentColor"
            strokeWidth="1.5"
            strokeLinecap="round"
            strokeLinejoin="round"
          />
        </svg>
        <span className="p-title">{title}</span>
        {count !== undefined && <span className="p-count">{count}</span>}
      </button>
      {open && (
        <div className="panel-body">
          {children}
        </div>
      )}
    </div>
  )
}

/* ── Copy button with feedback ───────────────────────── */
function CopyButton({ text }) {
  const [copied, setCopied] = useState(false)

  function copy() {
    navigator.clipboard.writeText(text).then(() => {
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
    })
  }

  return (
    <button className={`copy-btn${copied ? ' copy-btn--done' : ''}`} onClick={copy}>
      {copied ? '✓ Copied' : 'Copy'}
    </button>
  )
}

/* ── Panel contents ──────────────────────────────────── */
function SourcesPanel({ sources }) {
  return (
    <Panel title="Sources" count={sources.length}>
      <div className="source-list">
        {sources.map((s, i) => (
          <div key={i} className="source-item">{s}</div>
        ))}
      </div>
    </Panel>
  )
}

function SQLPanel({ queries }) {
  return (
    <Panel title="SQL">
      <div className="sql-list">
        {queries.map((sql, i) => (
          <div key={i} className="sql-block">
            <div className="sql-wrap">
              <code className="sql-code">{sql}</code>
            </div>
            <CopyButton text={sql} />
          </div>
        ))}
      </div>
    </Panel>
  )
}

function TracePanel({ steps, decomposed }) {
  const title = decomposed ? `Reasoning · ${steps.length} steps` : 'Reasoning'
  return (
    <Panel title={title}>
      <div className="trace-steps">
        {steps.map((s, i) => (
          <div key={s.id ?? i} className="trace-step">
            <div className="step-num">{i + 1}</div>
            <div className="step-inner">
              <div className="step-q">{s.question}</div>
              <div className="step-routes">
                {s.routes.map(r => (
                  <span key={r} className={`r-tag r-tag--${r}`}>{r.toUpperCase()}</span>
                ))}
              </div>
              <div className="step-a">{s.intermediate_answer}</div>
            </div>
          </div>
        ))}
      </div>
    </Panel>
  )
}

/* ── Message ─────────────────────────────────────────── */
export default function Message({ msg }) {
  const { question, status, data, errorMsg } = msg

  return (
    <div className="message">
      <div className="q-row">
        <div className="avatar avatar--user">You</div>
        <span className="q-text">{question}</span>
      </div>

      <div className="a-row">
        <div className="avatar avatar--ai">EI</div>

        {status === 'loading' && <Skeleton />}

        {status === 'error' && (
          <div className="error-card">{errorMsg}</div>
        )}

        {status === 'done' && data && (
          <div className="a-body">
            <div className="answer-card">
              <p className="answer-text">
                <StreamingText text={data.answer} />
              </p>
              {data.routing_reasoning && (
                <p className="routing-note">{data.routing_reasoning}</p>
              )}
            </div>
            {(data.all_sources?.length > 0 || data.all_sql?.length > 0 || data.steps?.length > 0) && (
              <div className="panels">
                {data.all_sources?.length > 0 && <SourcesPanel sources={data.all_sources} />}
                {data.all_sql?.length > 0      && <SQLPanel queries={data.all_sql} />}
                {data.steps?.length > 0         && <TracePanel steps={data.steps} decomposed={data.decomposed} />}
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  )
}
