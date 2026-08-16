import Logo from './Logo'

const CATEGORIES = [
  { label: 'Revenue',        q: 'Which S&P 500 companies had the highest revenue last quarter?' },
  { label: 'Margins',        q: 'Compare operating margins across major tech companies.' },
  { label: 'Earnings Calls', q: 'What did NVIDIA say about AI demand in their earnings call?' },
  { label: 'EPS Growth',     q: 'Which companies showed the strongest EPS growth last year?' },
]

const SUGGESTIONS = [
  'Compare Apple and Microsoft revenue growth',
  'What did executives say about AI spending?',
  'Which sectors had margin compression?',
]

export default function Hero({ onFill }) {
  return (
    <div className="hero">
      <div className="hero-inner">
        <div className="hero-logo-wrap">
          <Logo size={44} />
        </div>
        <p className="hero-eyebrow">S&amp;P 500 · Real Earnings Data</p>
        <h1 className="hero-title">Earnings<br />Intelligence.</h1>
        <p className="hero-sub">
          Ask anything about revenues, margins, EPS, or what executives said on their earnings calls.
        </p>
        <div className="cat-row">
          {CATEGORIES.map((cat, i) => (
            <button
              key={cat.label}
              className="cat-pill"
              onClick={() => onFill(cat.q)}
              style={{ animationDelay: `${i * 55}ms` }}
            >
              {cat.label}
            </button>
          ))}
        </div>
        <div className="chip-row">
          {SUGGESTIONS.map((q, i) => (
            <button
              key={q}
              className="chip"
              onClick={() => onFill(q)}
              title={q}
              style={{ animationDelay: `${220 + i * 50}ms` }}
            >
              {q}
            </button>
          ))}
        </div>
      </div>
    </div>
  )
}
