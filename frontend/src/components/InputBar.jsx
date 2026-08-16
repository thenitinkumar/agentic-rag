import { forwardRef, useImperativeHandle, useRef, useState, useEffect } from 'react'

const InputBar = forwardRef(function InputBar({ onSubmit, loading, loadingStage }, ref) {
  const [value, setValue]     = useState('')
  const [pulsing, setPulsing] = useState(false)
  const textareaRef           = useRef(null)

  useImperativeHandle(ref, () => ({
    fill(q) {
      setValue(q)
      requestAnimationFrame(() => textareaRef.current?.focus())
    },
  }))

  useEffect(() => {
    const el = textareaRef.current
    if (!el) return
    el.style.height = 'auto'
    el.style.height = Math.min(el.scrollHeight, 180) + 'px'
  }, [value])

  function handleKeyDown(e) {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      submit()
    }
  }

  function submit() {
    const q = value.trim()
    if (!q || loading) return
    setPulsing(true)
    setTimeout(() => setPulsing(false), 220)
    onSubmit(q)
    setValue('')
  }

  return (
    <div className="input-bar">
      <div className="input-bar-inner">
        {loading && (
          <div className="loading-indicator">
            <div className="ldots">
              <span className="ldot" />
              <span className="ldot" />
              <span className="ldot" />
            </div>
            <span className="loading-stage">{loadingStage}</span>
          </div>
        )}
        <div className={`input-card${loading ? ' disabled' : ''}`}>
          <textarea
            ref={textareaRef}
            className="chat-textarea"
            value={value}
            onChange={e => setValue(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Ask about earnings, margins, or what was said in a call…"
            rows={1}
            disabled={loading}
          />
          <button
            className={`send-btn${pulsing ? ' send-btn--pulse' : ''}`}
            onClick={submit}
            disabled={loading || !value.trim()}
            aria-label="Send"
          >
            <svg width="15" height="15" viewBox="0 0 16 16" fill="none">
              <path
                d="M8 12.5V3.5M3.5 8 8 3.5 12.5 8"
                stroke="currentColor"
                strokeWidth="2"
                strokeLinecap="round"
                strokeLinejoin="round"
              />
            </svg>
          </button>
        </div>
      </div>
    </div>
  )
})

export default InputBar
