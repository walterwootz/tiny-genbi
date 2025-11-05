import { useState, useEffect } from 'react'
import axios from 'axios'
import { FaPaperPlane, FaSpinner, FaDatabase, FaBookmark } from 'react-icons/fa'
import { Prism as SyntaxHighlighter } from 'react-syntax-highlighter'
import { vscDarkPlus } from 'react-syntax-highlighter/dist/esm/styles/prism'
import ReactMarkdown from 'react-markdown'
import './QueryInterface.css'

function QueryInterface({ apiConfig }) {
  const [question, setQuestion] = useState('')
  const [databaseId, setDatabaseId] = useState('')
  const [databases, setDatabases] = useState([])
  const [loading, setLoading] = useState(false)
  const [result, setResult] = useState(null)
  const [error, setError] = useState(null)
  const [savingToKB, setSavingToKB] = useState(false)
  const [kbMessage, setKbMessage] = useState(null)
  
  // Streaming states
  const [streamingReasoning, setStreamingReasoning] = useState('')
  const [currentStep, setCurrentStep] = useState('')
  const [isStreaming, setIsStreaming] = useState(false)

  // Tab state
  const [activeTab, setActiveTab] = useState('reasoning')

  useEffect(() => {
    fetchDatabases()
  }, [])

  const fetchDatabases = async () => {
    try {
      const response = await axios.get(`${apiConfig.baseUrl}/api/v1/databases`)
      setDatabases(response.data.databases || [])
    } catch (err) {
      console.error('Error fetching databases:', err)
    }
  }

  const handleAsk = async () => {
    if (!question.trim() || !databaseId.trim()) {
      setError('Please enter both a question and select a database')
      return
    }

    setLoading(true)
    setError(null)
    setResult(null)
    setStreamingReasoning('')
    setCurrentStep('')
    setIsStreaming(true)
    setActiveTab('reasoning') // Start with reasoning tab

    try {
      // Use fetch with streaming for SSE (EventSource doesn't support POST)
      const response = await fetch(`${apiConfig.baseUrl}/api/v1/ask/stream`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          question,
          database_id: databaseId,
          max_rows: 100,
        }),
      })

      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`)
      }

      const reader = response.body.getReader()
      const decoder = new TextDecoder()

      let buffer = ''
      let currentEvent = null

      while (true) {
        const { done, value } = await reader.read()
        if (done) break

        buffer += decoder.decode(value, { stream: true })
        const lines = buffer.split('\n')
        buffer = lines.pop() || ''

        for (const line of lines) {
          if (!line.trim()) {
            // Empty line = end of event
            currentEvent = null
            continue
          }

          if (line.startsWith('event:')) {
            currentEvent = line.substring(6).trim()
            continue
          }
          
          if (line.startsWith('data:')) {
            try {
              const data = JSON.parse(line.substring(5).trim())
            
              // Handle different event types
              if (data.step) {
                setCurrentStep(data.message || data.step)
              } else if (data.chunk) {
                // Streaming reasoning
                setStreamingReasoning(prev => prev + data.chunk)
              } else if (data.reasoning) {
                setStreamingReasoning(data.reasoning)
              } else if (data.sql) {
                // Store SQL when generated
                setResult(prev => ({ ...prev, sql: data.sql }))
              } else if (data.attempts) {
                // SQL was fixed after multiple attempts
                setResult(prev => ({ 
                  ...(prev || {}), 
                  sql: data.sql,
                  metadata: { 
                    ...(prev?.metadata || {}), 
                    auto_fixed: true, 
                    fix_attempts: data.attempts 
                  }
                }))
              } else if (data.explanation) {
                // Store explanation when generated
                setResult(prev => ({ ...prev, sql_explanation: data.explanation }))
                setCurrentStep('') // Clear "Generating explanation..." message
              } else if (data.natural_language_answer) {
                // Store natural language answer when generated
                setResult(prev => ({ ...prev, natural_language_answer: data.natural_language_answer }))
                setCurrentStep('') // Clear "Analyzing results..." message
              } else if (data.row_count !== undefined) {
                // SQL execution success
                const autoFixInfo = data.auto_fixed ? ` (auto-fixed in ${data.fix_attempts} attempts)` : ''
                setCurrentStep(`✅ Query executed successfully! ${data.row_count} rows returned${autoFixInfo}`)
                // Store auto-fix metadata
                if (data.auto_fixed) {
                  setResult(prev => ({ 
                    ...(prev || {}), 
                    metadata: { 
                      ...(prev?.metadata || {}), 
                      auto_fixed: true, 
                      fix_attempts: data.fix_attempts 
                    }
                  }))
                }
              } else if (data.error) {
                // SQL execution error
                setError(data.error)
                setIsStreaming(false)
                setLoading(false)
              } else if (data.query_id) {
                // Complete result
                setResult(data)
                setIsStreaming(false)
                setLoading(false)
                setCurrentStep('')
              } else if (data.message && data.message.includes('error')) {
                setError(data.message)
                setIsStreaming(false)
                setLoading(false)
              }
            } catch (parseErr) {
              console.error('Error parsing SSE data:', parseErr)
            }
          }
        }
      }
      
    } catch (err) {
      setError(err.response?.data?.detail || err.message || 'An error occurred')
      setIsStreaming(false)
    } finally {
      setLoading(false)
    }
  }

  const handleKeyPress = (e) => {
    if (e.key === 'Enter' && (e.metaKey || e.ctrlKey)) {
      handleAsk()
    }
  }

  const saveToKnowledgeBase = async () => {
    if (!result || !result.sql || !result.question) {
      return
    }

    setSavingToKB(true)
    setKbMessage(null)

    try {
      await axios.post(
        `${apiConfig.baseUrl}/api/v1/databases/${databaseId}/knowledge-base/sql-pairs`,
        {
          database_id: databaseId,
          question: result.question,
          sql: result.sql,
          description: result.sql_explanation || null
        }
      )

      setKbMessage({ type: 'success', text: '✅ Saved to Knowledge Base!' })
      
      // Clear message after 3 seconds
      setTimeout(() => setKbMessage(null), 3000)
    } catch (err) {
      setKbMessage({ 
        type: 'error', 
        text: `❌ Failed to save: ${err.response?.data?.detail || err.message}` 
      })
    } finally {
      setSavingToKB(false)
    }
  }

  return (
    <div className="query-interface">
      <div className="interface-header">
        <h2>Ask Questions in Natural Language</h2>
        <p>Select a database and type your question to get SQL queries with results</p>
      </div>

      <div className="query-form">
        <div className="form-group">
          <label htmlFor="databaseId">
            <FaDatabase /> Select Database
          </label>
          <select
            id="databaseId"
            value={databaseId}
            onChange={(e) => setDatabaseId(e.target.value)}
            className="input"
          >
            <option value="">-- Select a database --</option>
            {databases.map((db) => (
              <option key={db.database_id} value={db.database_id}>
                {db.database_id} ({db.database_name})
              </option>
            ))}
          </select>
          {databases.length === 0 && (
            <small className="hint" style={{ color: 'var(--warning-color)' }}>
              No databases available. Please index a database first in Database Management.
            </small>
          )}
        </div>

        <div className="form-group">
          <label htmlFor="question">Your Question</label>
          <textarea
            id="question"
            placeholder="e.g., Show me the top 10 customers by total order amount"
            value={question}
            onChange={(e) => setQuestion(e.target.value)}
            onKeyDown={handleKeyPress}
            className="textarea"
            rows={4}
          />
          <small className="hint">Press Cmd+Enter (Mac) or Ctrl+Enter (Windows) to submit</small>
        </div>

        <button
          onClick={handleAsk}
          disabled={loading}
          className="btn btn-primary"
        >
          {loading ? (
            <>
              <FaSpinner className="spinner" />
              Processing...
            </>
          ) : (
            <>
              <FaPaperPlane />
              Ask Question
            </>
          )}
        </button>
      </div>

      {error && (
        <div className="alert alert-error">
          <strong>Error:</strong> {error}
        </div>
      )}

      {/* Show current step during streaming */}
      {isStreaming && currentStep && (
        <div className="streaming-container">
          <div className="current-step">
            <FaSpinner className="spinner" />
            {currentStep}
          </div>
        </div>
      )}

      {(result || isStreaming) && (
        <div className="results">
          {kbMessage && (
            <div className={`alert alert-${kbMessage.type}`}>
              {kbMessage.text}
            </div>
          )}

          {result?.metadata?.auto_fixed && (
            <div className="alert alert-success">
              <strong>🔧 Auto-Fixed:</strong> The query was automatically corrected after {(result.metadata?.fix_attempts || 1) - 1} failed attempt(s). The SQL shown below is the corrected version.
            </div>
          )}

          {/* Answer Section - Always visible below tabs */}
          {result?.natural_language_answer && (
            <div className="result-section answer-section">
              <h3>💬 Answer</h3>
              <p className="answer">{result.natural_language_answer}</p>
            </div>
          )}

          {/* Tabs Navigation */}
          <div className="tabs-container">
            <div className="tabs-header">
              <button 
                className={`tab-button ${activeTab === 'reasoning' ? 'active' : ''}`}
                onClick={() => setActiveTab('reasoning')}
              >
                🧠 Reasoning
              </button>
              <button 
                className={`tab-button ${activeTab === 'sql' ? 'active' : ''}`}
                onClick={() => setActiveTab('sql')}
              >
                💾 Generated SQL
              </button>
              <button 
                className={`tab-button ${activeTab === 'explanation' ? 'active' : ''}`}
                onClick={() => setActiveTab('explanation')}
              >
                📝 Explanation
              </button>
            </div>

            <div className="tab-content">
              {/* Reasoning Tab */}
              <div className={`tab-panel ${activeTab === 'reasoning' ? 'active' : ''}`}>
                {(result?.reasoning || streamingReasoning || isStreaming) ? (
                  <>
                    <div className="reasoning-content">
                      <ReactMarkdown>{result?.reasoning || streamingReasoning}</ReactMarkdown>
                    </div>
                  </>
                ) : (
                  <p className="hint">No reasoning available</p>
                )}
              </div>

              {/* SQL Tab */}
              <div className={`tab-panel ${activeTab === 'sql' ? 'active' : ''}`}>
                {result?.sql ? (
                  <>
                    <div className="section-header-with-action" style={{ marginBottom: '1rem' }}>
                      <h4 style={{ margin: 0 }}>SQL Query</h4>
                      {result?.execution_result?.success && (
                        <button 
                          className="btn-save-kb" 
                          onClick={saveToKnowledgeBase}
                          disabled={savingToKB}
                          title="Save to Knowledge Base"
                        >
                          <FaBookmark /> {savingToKB ? 'Saving...' : 'Save to KB'}
                        </button>
                      )}
                    </div>
                    <SyntaxHighlighter language="sql" style={vscDarkPlus} customStyle={{ borderRadius: '8px', margin: 0 }}>
                      {result.sql}
                    </SyntaxHighlighter>

                    {/* Query Results inside SQL tab */}
                    {result.execution_result && (
                      <div style={{ marginTop: '1.5rem' }}>
                        <h4>Query Results</h4>
                        {result.execution_result.success ? (
                          <>
                            <div className="result-stats">
                              <span>✅ Success</span>
                              <span>Rows: {result.execution_result.row_count}</span>
                              <span>Time: {result.execution_result.execution_time_ms?.toFixed(2)}ms</span>
                            </div>
                            {result.formatted_table && (
                              <pre className="table-result">{result.formatted_table}</pre>
                            )}
                          </>
                        ) : (
                          <div className="alert alert-error">
                            {result.execution_result.error}
                          </div>
                        )}
                      </div>
                    )}
                  </>
                ) : (
                  <p className="hint">No SQL query available</p>
                )}
              </div>

              {/* Explanation Tab */}
              <div className={`tab-panel ${activeTab === 'explanation' ? 'active' : ''}`}>
                {result?.sql_explanation ? (
                  <p className="explanation">{result.sql_explanation}</p>
                ) : (
                  <p className="hint">No explanation available</p>
                )}
              </div>
            </div>
          </div>

          {result?.metadata && (
            <div className="metadata">
              <small>Query ID: {result.query_id}</small>
              <small>Model: {result.metadata.model}</small>
              <small>Schema Docs: {result.metadata.num_schema_docs}</small>
            </div>
          )}
        </div>
      )}
    </div>
  )
}

export default QueryInterface
