import { useState, useRef, useEffect } from 'react'
import Topbar from './components/Topbar'
import Hero from './components/Hero'
import Thread from './components/Thread'
import InputBar from './components/InputBar'

const LOADING_STAGES = [
  'Routing query…',
  'Retrieving financial data…',
  'Analyzing earnings calls…',
  'Synthesizing answer…',
]

export default function App() {
  const [messages, setMessages] = useState([])
  const [loading, setLoading]   = useState(false)
  const [loadingStage, setLoadingStage] = useState('')
  const [health, setHealth]     = useState(null)
  const inputBarRef = useRef(null)
  const stageTimer  = useRef(null)

  useEffect(() => {
    fetch('/api/health')
      .then(r => r.json())
      .then(setHealth)
      .catch(() => setHealth({ error: true }))
  }, [])

  function fillInput(q) {
    inputBarRef.current?.fill(q)
  }

  async function handleSubmit(question) {
    if (!question.trim() || loading) return

    const id = String(Date.now())
    setMessages(prev => [...prev, { id, question, status: 'loading' }])
    setLoading(true)

    let idx = 0
    setLoadingStage(LOADING_STAGES[0])
    stageTimer.current = setInterval(() => {
      idx = (idx + 1) % LOADING_STAGES.length
      setLoadingStage(LOADING_STAGES[idx])
    }, 4500)

    try {
      const r = await fetch('/api/query', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ question }),
      })

      if (r.ok) {
        const data = await r.json()
        setMessages(prev =>
          prev.map(m => m.id === id ? { ...m, status: 'done', data } : m)
        )
      } else {
        const err = await r.json().catch(() => ({}))
        setMessages(prev =>
          prev.map(m => m.id === id
            ? { ...m, status: 'error', errorMsg: err.detail || r.statusText }
            : m
          )
        )
      }
    } catch {
      setMessages(prev =>
        prev.map(m => m.id === id
          ? { ...m, status: 'error', errorMsg: 'Could not reach the server.' }
          : m
        )
      )
    } finally {
      clearInterval(stageTimer.current)
      setLoading(false)
    }
  }

  return (
    <div className="app">
      <Topbar health={health} />
      <div className="content">
        {messages.length === 0
          ? <Hero onFill={fillInput} />
          : <Thread messages={messages} />
        }
      </div>
      <InputBar
        ref={inputBarRef}
        onSubmit={handleSubmit}
        loading={loading}
        loadingStage={loadingStage}
      />
    </div>
  )
}
