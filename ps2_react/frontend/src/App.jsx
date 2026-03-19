import { useState, useEffect } from 'react'

const SAMPLE_LOG = `[2024-03-15 14:23:11] Starting build #1234 for branch: main
[2024-03-15 14:23:12] Pulling Docker image: node:18-alpine
[2024-03-15 14:23:15] Running npm install...
[2024-03-15 14:23:45] npm ERR! code ERESOLVE
[2024-03-15 14:23:45] npm ERR! ERESOLVE unable to resolve dependency tree
[2024-03-15 14:23:45] npm ERR! peer dep missing: react@^17.0.0, required by react-router-dom@5.3.4
[2024-03-15 14:23:45] npm ERR! Conflicting peer dependency: react@18.2.0
[2024-03-15 14:23:45] npm ERR! Fix the upstream dependency conflict
[2024-03-15 14:23:46] Build failed with exit code 1
[2024-03-15 14:23:46] Pipeline stage 'install-dependencies' failed after 31s
[2024-03-15 14:23:47] Sending failure notification to team-channel`

export default function App() {
  const [models, setModels] = useState([])
  const [modelKey, setModelKey] = useState('gpt-4o-mini')
  const [logInput, setLogInput] = useState(SAMPLE_LOG)
  const [result, setResult] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)

  useEffect(() => {
    fetch('/api/models')
      .then(r => r.json())
      .then(data => {
        setModels(data.models)
        if (data.models.length && !data.models.includes(modelKey)) {
          setModelKey(data.models[0])
        }
      })
      .catch(() => setModels(['gpt-4o', 'gpt-4o-mini', 'gpt-35-turbo']))
  }, [])

  async function handleAnalyze() {
    if (!logInput.trim()) return
    setLoading(true)
    setError(null)
    setResult(null)
    try {
      const res = await fetch('/api/analyze', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ log_snippet: logInput, model_key: modelKey }),
      })
      if (!res.ok) {
        const err = await res.json()
        throw new Error(err.detail || `HTTP ${res.status}`)
      }
      setResult(await res.json())
    } catch (e) {
      setError(e.message)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="app">
      <header className="header">
        <h1>Pipeline Anomaly Explanation Agent</h1>
        <p className="caption">Paste a CI/CD pipeline log snippet to get an AI-powered anomaly analysis.</p>
      </header>

      <div className="controls">
        <label htmlFor="model-select">LLM Model</label>
        <select
          id="model-select"
          value={modelKey}
          onChange={e => setModelKey(e.target.value)}
        >
          {models.map(m => <option key={m} value={m}>{m}</option>)}
        </select>
      </div>

      <div className="input-section">
        <label htmlFor="log-input">Pipeline Log Snippet</label>
        <textarea
          id="log-input"
          value={logInput}
          onChange={e => setLogInput(e.target.value)}
          rows={12}
          placeholder="Paste your pipeline log here..."
        />
        <button
          className="btn-primary"
          onClick={handleAnalyze}
          disabled={loading || !logInput.trim()}
        >
          {loading ? 'Analyzing...' : 'Analyze Anomaly'}
        </button>
      </div>

      {loading && (
        <div className="spinner-container">
          <div className="spinner" />
          <span>Analyzing pipeline log...</span>
        </div>
      )}

      {error && <div className="error-box">Analysis failed: {error}</div>}

      {result && (
        <div className="results">
          <div className="metrics">
            <div className="metric-card">
              <span className="metric-label">Anomaly Type</span>
              <span className="metric-value">{result.anomaly_type}</span>
            </div>
            <div className="metric-card">
              <span className="metric-label">Severity</span>
              <span className={`metric-value severity-${result.severity?.toLowerCase()}`}>
                {result.severity?.toUpperCase()}
              </span>
            </div>
            <div className="metric-card">
              <span className="metric-label">Affected Stage</span>
              <span className="metric-value">{result.affected_stage}</span>
            </div>
          </div>

          <section>
            <h2>Plain English Summary</h2>
            <div className="info-box">{result.plain_english_summary}</div>
          </section>

          <section>
            <h2>Root Cause</h2>
            <div className="error-box">{result.root_cause}</div>
          </section>

          <div className="two-col">
            <section>
              <h2>Remediation Steps</h2>
              <ol>
                {result.remediation_steps?.map((step, i) => (
                  <li key={i}>{step}</li>
                ))}
              </ol>
            </section>
            <section>
              <h2>Prevention Tips</h2>
              <ul>
                {result.prevention_tips?.map((tip, i) => (
                  <li key={i}>{tip}</li>
                ))}
              </ul>
            </section>
          </div>
        </div>
      )}
    </div>
  )
}
