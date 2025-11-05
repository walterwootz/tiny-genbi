import { useState, useEffect } from 'react'
import axios from 'axios'
import { FaBook, FaPlus, FaLightbulb, FaCode, FaTrash, FaDatabase } from 'react-icons/fa'
import './KnowledgeBase.css'

function KnowledgeBase({ apiConfig }) {
  const [databases, setDatabases] = useState([])
  const [selectedDb, setSelectedDb] = useState('')
  const [instructions, setInstructions] = useState([])
  const [sqlPairs, setSqlPairs] = useState([])
  const [loading, setLoading] = useState(false)
  const [message, setMessage] = useState(null)
  
  // Form states
  const [showAddInstruction, setShowAddInstruction] = useState(false)
  const [showAddSQLPair, setShowAddSQLPair] = useState(false)
  const [instructionForm, setInstructionForm] = useState({ title: '', content: '' })
  const [sqlPairForm, setSqlPairForm] = useState({ question: '', sql: '', description: '' })

  useEffect(() => {
    fetchDatabases()
  }, [])

  useEffect(() => {
    if (selectedDb) {
      fetchKnowledgeBase()
    }
  }, [selectedDb])

  const fetchDatabases = async () => {
    try {
      const response = await axios.get(`${apiConfig.baseUrl}/api/v1/databases`)
      setDatabases(response.data.databases || [])
      if (response.data.databases.length > 0 && !selectedDb) {
        setSelectedDb(response.data.databases[0].database_id)
      }
    } catch (err) {
      console.error('Error fetching databases:', err)
    }
  }

  const fetchKnowledgeBase = async () => {
    if (!selectedDb) return
    
    setLoading(true)
    try {
      const response = await axios.get(
        `${apiConfig.baseUrl}/api/v1/databases/${selectedDb}/knowledge-base`
      )
      setInstructions(response.data.instructions || [])
      setSqlPairs(response.data.sql_pairs || [])
    } catch (err) {
      console.error('Error fetching knowledge base:', err)
      setMessage({ type: 'error', text: 'Failed to load knowledge base' })
    } finally {
      setLoading(false)
    }
  }

  const addInstruction = async () => {
    if (!instructionForm.title.trim() || !instructionForm.content.trim()) {
      setMessage({ type: 'error', text: 'Please fill in all fields' })
      return
    }

    setLoading(true)
    setMessage(null)
    try {
      await axios.post(
        `${apiConfig.baseUrl}/api/v1/databases/${selectedDb}/knowledge-base/instructions`,
        {
          database_id: selectedDb,
          title: instructionForm.title,
          content: instructionForm.content
        }
      )
      
      setMessage({ type: 'success', text: '✅ Instruction added and indexed!' })
      setInstructionForm({ title: '', content: '' })
      setShowAddInstruction(false)
      fetchKnowledgeBase()
    } catch (err) {
      setMessage({ type: 'error', text: `❌ ${err.response?.data?.detail || err.message}` })
    } finally {
      setLoading(false)
    }
  }

  const addSQLPair = async () => {
    if (!sqlPairForm.question.trim() || !sqlPairForm.sql.trim()) {
      setMessage({ type: 'error', text: 'Please fill in question and SQL' })
      return
    }

    setLoading(true)
    setMessage(null)
    try {
      await axios.post(
        `${apiConfig.baseUrl}/api/v1/databases/${selectedDb}/knowledge-base/sql-pairs`,
        {
          database_id: selectedDb,
          question: sqlPairForm.question,
          sql: sqlPairForm.sql,
          description: sqlPairForm.description || null
        }
      )
      
      setMessage({ type: 'success', text: '✅ SQL pair added and indexed!' })
      setSqlPairForm({ question: '', sql: '', description: '' })
      setShowAddSQLPair(false)
      fetchKnowledgeBase()
    } catch (err) {
      setMessage({ type: 'error', text: `❌ ${err.response?.data?.detail || err.message}` })
    } finally {
      setLoading(false)
    }
  }

  const deleteInstruction = async (instructionId) => {
    if (!confirm('Delete this instruction?')) return

    try {
      await axios.delete(
        `${apiConfig.baseUrl}/api/v1/knowledge-base/instructions/${instructionId}`
      )
      setMessage({ type: 'success', text: '✅ Instruction deleted' })
      fetchKnowledgeBase()
    } catch (err) {
      setMessage({ type: 'error', text: `❌ ${err.response?.data?.detail || err.message}` })
    }
  }

  const deleteSQLPair = async (pairId) => {
    if (!confirm('Delete this SQL pair?')) return

    try {
      await axios.delete(
        `${apiConfig.baseUrl}/api/v1/knowledge-base/sql-pairs/${pairId}`
      )
      setMessage({ type: 'success', text: '✅ SQL pair deleted' })
      fetchKnowledgeBase()
    } catch (err) {
      setMessage({ type: 'error', text: `❌ ${err.response?.data?.detail || err.message}` })
    }
  }

  return (
    <div className="knowledge-base">
      <div className="kb-header">
        <div>
          <h2><FaBook /> Knowledge Base</h2>
          <p>Add instructions and SQL examples to improve query generation</p>
        </div>
      </div>

      {/* Database Selector */}
      <div className="db-selector-section">
        <label><FaDatabase /> Select Database</label>
        <select
          value={selectedDb}
          onChange={(e) => setSelectedDb(e.target.value)}
          className="input"
        >
          <option value="">-- Select a database --</option>
          {databases.map((db) => (
            <option key={db.database_id} value={db.database_id}>
              {db.database_id} ({db.database_name})
            </option>
          ))}
        </select>
      </div>

      {message && (
        <div className={`alert alert-${message.type}`}>
          {message.text}
        </div>
      )}

      {selectedDb && (
        <>
          {/* Instructions Section */}
          <div className="kb-section">
            <div className="section-header">
              <h3><FaLightbulb /> Instructions ({instructions.length})</h3>
              <button
                className="btn btn-primary btn-sm"
                onClick={() => setShowAddInstruction(!showAddInstruction)}
              >
                <FaPlus /> Add Instruction
              </button>
            </div>

            {showAddInstruction && (
              <div className="add-form">
                <div className="form-group">
                  <label>Title</label>
                  <input
                    type="text"
                    placeholder="e.g., Status Values"
                    value={instructionForm.title}
                    onChange={(e) => setInstructionForm({ ...instructionForm, title: e.target.value })}
                    className="input"
                  />
                </div>
                <div className="form-group">
                  <label>Content</label>
                  <textarea
                    placeholder="e.g., The status column can have values: 'pending', 'approved', 'rejected'..."
                    value={instructionForm.content}
                    onChange={(e) => setInstructionForm({ ...instructionForm, content: e.target.value })}
                    className="textarea"
                    rows="4"
                  />
                </div>
                <div className="form-actions">
                  <button className="btn btn-secondary" onClick={() => setShowAddInstruction(false)}>
                    Cancel
                  </button>
                  <button className="btn btn-primary" onClick={addInstruction} disabled={loading}>
                    {loading ? 'Adding...' : 'Add Instruction'}
                  </button>
                </div>
              </div>
            )}

            <div className="kb-list">
              {instructions.length === 0 ? (
                <div className="empty-state">
                  <FaLightbulb className="empty-icon" />
                  <p>No instructions yet</p>
                  <p className="empty-hint">Add instructions about table values, business rules, etc.</p>
                </div>
              ) : (
                instructions.map((inst) => (
                  <div key={inst.id} className="kb-card instruction-card">
                    <div className="kb-card-header">
                      <h4>{inst.title}</h4>
                      <button
                        className="btn-delete-sm"
                        onClick={() => deleteInstruction(inst.id)}
                      >
                        <FaTrash />
                      </button>
                    </div>
                    <p className="kb-content">{inst.content}</p>
                    <span className="kb-timestamp">
                      {new Date(inst.created_at).toLocaleString()}
                    </span>
                  </div>
                ))
              )}
            </div>
          </div>

          {/* SQL Pairs Section */}
          <div className="kb-section">
            <div className="section-header">
              <h3><FaCode /> SQL Pairs ({sqlPairs.length})</h3>
              <button
                className="btn btn-primary btn-sm"
                onClick={() => setShowAddSQLPair(!showAddSQLPair)}
              >
                <FaPlus /> Add SQL Pair
              </button>
            </div>

            {showAddSQLPair && (
              <div className="add-form">
                <div className="form-group">
                  <label>Question</label>
                  <input
                    type="text"
                    placeholder="e.g., Show me all pending orders"
                    value={sqlPairForm.question}
                    onChange={(e) => setSqlPairForm({ ...sqlPairForm, question: e.target.value })}
                    className="input"
                  />
                </div>
                <div className="form-group">
                  <label>SQL Query</label>
                  <textarea
                    placeholder="SELECT * FROM orders WHERE status = 'pending'..."
                    value={sqlPairForm.sql}
                    onChange={(e) => setSqlPairForm({ ...sqlPairForm, sql: e.target.value })}
                    className="textarea code-textarea"
                    rows="4"
                  />
                </div>
                <div className="form-group">
                  <label>Description (optional)</label>
                  <input
                    type="text"
                    placeholder="Explanation of the query..."
                    value={sqlPairForm.description}
                    onChange={(e) => setSqlPairForm({ ...sqlPairForm, description: e.target.value })}
                    className="input"
                  />
                </div>
                <div className="form-actions">
                  <button className="btn btn-secondary" onClick={() => setShowAddSQLPair(false)}>
                    Cancel
                  </button>
                  <button className="btn btn-primary" onClick={addSQLPair} disabled={loading}>
                    {loading ? 'Adding...' : 'Add SQL Pair'}
                  </button>
                </div>
              </div>
            )}

            <div className="kb-list">
              {sqlPairs.length === 0 ? (
                <div className="empty-state">
                  <FaCode className="empty-icon" />
                  <p>No SQL pairs yet</p>
                  <p className="empty-hint">Add question-SQL examples to guide future queries</p>
                </div>
              ) : (
                sqlPairs.map((pair) => (
                  <div key={pair.id} className="kb-card sql-pair-card">
                    <div className="kb-card-header">
                      <h4>❓ {pair.question}</h4>
                      <button
                        className="btn-delete-sm"
                        onClick={() => deleteSQLPair(pair.id)}
                      >
                        <FaTrash />
                      </button>
                    </div>
                    <pre className="sql-code">{pair.sql}</pre>
                    {pair.description && (
                      <p className="kb-description">{pair.description}</p>
                    )}
                    <span className="kb-timestamp">
                      {new Date(pair.created_at).toLocaleString()}
                    </span>
                  </div>
                ))
              )}
            </div>
          </div>
        </>
      )}
    </div>
  )
}

export default KnowledgeBase
