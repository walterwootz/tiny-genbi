import { useState, useEffect } from 'react'
import axios from 'axios'
import { FaDatabase, FaPlus, FaSync, FaServer, FaCheck, FaTimes, FaArrowRight, FaTrash, FaSitemap } from 'react-icons/fa'
import Modal from './Modal'
import './DatabaseManager.css'

function DatabaseManager({ apiConfig, onDatabaseSelect }) {
  const [databases, setDatabases] = useState([])
  const [loading, setLoading] = useState(false)
  const [showAutoIndex, setShowAutoIndex] = useState(false)
  const [mysqlCreds, setMysqlCreds] = useState({
    host: '',
    port: 3306,
    user: '',
    password: '',
    database: '',
  })
  const [databaseId, setDatabaseId] = useState('')
  const [message, setMessage] = useState(null)
  
  // New state for two-phase workflow
  const [discoveredTables, setDiscoveredTables] = useState([])
  const [selectedTables, setSelectedTables] = useState([])
  const [showTableSelection, setShowTableSelection] = useState(false)
  const [discoveryInfo, setDiscoveryInfo] = useState(null)
  
  // State for delete confirmation
  const [showDeleteModal, setShowDeleteModal] = useState(false)
  const [databaseToDelete, setDatabaseToDelete] = useState(null)
  const [deleting, setDeleting] = useState(false)

  useEffect(() => {
    fetchDatabases()
  }, [])

  const fetchDatabases = async () => {
    try {
      const response = await axios.get(`${apiConfig.baseUrl}/api/v1/databases`)
      // New API returns {databases: [DatabaseInfo]} instead of {databases: [string]}
      setDatabases(response.data.databases || [])
    } catch (err) {
      console.error('Error fetching databases:', err)
    }
  }

  const discoverTables = async () => {
    if (!databaseId.trim()) {
      setMessage({ type: 'error', text: 'Please enter a Database ID' })
      return
    }

    setLoading(true)
    setMessage(null)
    try {
      const response = await axios.post(`${apiConfig.baseUrl}/api/v1/mysql/discover`, mysqlCreds)
      
      setDiscoveredTables(response.data.tables)
      setDiscoveryInfo({
        database_name: response.data.database_name,
        total_tables: response.data.total_tables
      })
      setSelectedTables(response.data.tables.map(t => t.name)) // Select all by default
      setShowTableSelection(true)
      setMessage({ 
        type: 'success', 
        text: `✅ Discovered ${response.data.total_tables} tables in ${response.data.database_name}` 
      })
    } catch (err) {
      setMessage({ type: 'error', text: `❌ ${err.response?.data?.detail || err.message}` })
    } finally {
      setLoading(false)
    }
  }

  const toggleTableSelection = (tableName) => {
    setSelectedTables(prev => 
      prev.includes(tableName)
        ? prev.filter(t => t !== tableName)
        : [...prev, tableName]
    )
  }

  const toggleAllTables = () => {
    if (selectedTables.length === discoveredTables.length) {
      setSelectedTables([])
    } else {
      setSelectedTables(discoveredTables.map(t => t.name))
    }
  }

  const autoIndex = async () => {
    if (!databaseId.trim()) {
      setMessage({ type: 'error', text: 'Please enter a Database ID' })
      return
    }

    if (selectedTables.length === 0) {
      setMessage({ type: 'error', text: 'Please select at least one table to index' })
      return
    }

    setLoading(true)
    setMessage(null)
    try {
      const response = await axios.post(`${apiConfig.baseUrl}/api/v1/mysql/auto-index`, {
        database_id: databaseId,
        credentials: mysqlCreds,
        selected_tables: selectedTables,
      })
      setMessage({
        type: 'success',
        text: `✅ Indexed ${response.data.num_tables} tables with ${response.data.num_documents} documents. Credentials stored securely!`,
      })
      fetchDatabases()
      // Reset form
      setShowAutoIndex(false)
      setShowTableSelection(false)
      setDiscoveredTables([])
      setSelectedTables([])
      setDatabaseId('')
      setMysqlCreds({
        host: '',
        port: 3306,
        user: '',
        password: '',
        database: '',
      })
    } catch (err) {
      setMessage({ type: 'error', text: `❌ ${err.response?.data?.detail || err.message}` })
    } finally {
      setLoading(false)
    }
  }

  const cancelAutoIndex = () => {
    setShowAutoIndex(false)
    setShowTableSelection(false)
    setDiscoveredTables([])
    setSelectedTables([])
    setMessage(null)
  }

  const handleDeleteClick = (database) => {
    setDatabaseToDelete(database)
    setShowDeleteModal(true)
  }

  const confirmDelete = async () => {
    if (!databaseToDelete) return

    setDeleting(true)
    try {
      await axios.delete(`${apiConfig.baseUrl}/api/v1/databases/${databaseToDelete.database_id}`)
      setMessage({
        type: 'success',
        text: `✅ Database "${databaseToDelete.database_id}" deleted successfully`
      })
      fetchDatabases()
      setShowDeleteModal(false)
      setDatabaseToDelete(null)
    } catch (err) {
      setMessage({
        type: 'error',
        text: `❌ Failed to delete database: ${err.response?.data?.detail || err.message}`
      })
    } finally {
      setDeleting(false)
    }
  }

  const cancelDelete = () => {
    setShowDeleteModal(false)
    setDatabaseToDelete(null)
  }

  const reindexDatabase = async (database_id) => {
    if (!confirm(`Re-index database "${database_id}"?\n\nThis will:\n- Delete the old index\n- Re-discover and re-index the same tables\n- Keep your credentials`)) {
      return
    }

    setLoading(true)
    setMessage(null)
    try {
      const response = await axios.post(`${apiConfig.baseUrl}/api/v1/databases/${database_id}/reindex`)
      setMessage({
        type: 'success',
        text: `✅ Successfully re-indexed ${response.data.num_tables} tables for "${database_id}"`
      })
      fetchDatabases()
    } catch (err) {
      setMessage({
        type: 'error',
        text: `❌ Failed to re-index: ${err.response?.data?.detail || err.message}`
      })
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="database-manager">
      <div className="manager-header">
        <div>
          <h2>Database Management</h2>
          <p>Manage indexed databases and auto-discover MySQL schemas</p>
        </div>
        <button className="btn btn-primary" onClick={() => setShowAutoIndex(!showAutoIndex)}>
          <FaPlus /> Auto-Index MySQL
        </button>
      </div>

      {showAutoIndex && (
        <div className="auto-index-panel">
          <h3><FaServer /> MySQL Auto-Discovery</h3>
          <p className="panel-description">
            Connect to MySQL and automatically discover and index the database schema.
            Credentials will be stored securely (encrypted) for future queries.
          </p>

          <div className="form-group">
            <label>Database ID (unique identifier for GenBI)</label>
            <input
              type="text"
              placeholder="e.g., my_ecommerce_db"
              value={databaseId}
              onChange={(e) => setDatabaseId(e.target.value)}
              className="input"
            />
          </div>

          <div className="credentials-grid">
            <input
              type="text"
              placeholder="Host"
              value={mysqlCreds.host}
              onChange={(e) => setMysqlCreds({ ...mysqlCreds, host: e.target.value })}
              className="input"
            />
            <input
              type="number"
              placeholder="Port"
              value={mysqlCreds.port}
              onChange={(e) => setMysqlCreds({ ...mysqlCreds, port: parseInt(e.target.value) })}
              className="input"
            />
            <input
              type="text"
              placeholder="User"
              value={mysqlCreds.user}
              onChange={(e) => setMysqlCreds({ ...mysqlCreds, user: e.target.value })}
              className="input"
            />
            <input
              type="password"
              placeholder="Password"
              value={mysqlCreds.password}
              onChange={(e) => setMysqlCreds({ ...mysqlCreds, password: e.target.value })}
              className="input"
            />
            <input
              type="text"
              placeholder="Database Name"
              value={mysqlCreds.database}
              onChange={(e) => setMysqlCreds({ ...mysqlCreds, database: e.target.value })}
              className="input input-full"
            />
          </div>

          <div className="panel-actions">
            {!showTableSelection ? (
              <>
                <button className="btn btn-secondary" onClick={cancelAutoIndex}>
                  Cancel
                </button>
                <button className="btn btn-primary" onClick={discoverTables} disabled={loading}>
                  {loading ? 'Discovering...' : <><FaArrowRight /> Discover Tables</>}
                </button>
              </>
            ) : (
              <>
                <button className="btn btn-secondary" onClick={cancelAutoIndex} disabled={loading}>
                  Cancel
                </button>
                <button className="btn btn-primary" onClick={autoIndex} disabled={loading}>
                  {loading ? 'Indexing...' : <><FaCheck /> Index Selected Tables ({selectedTables.length})</>}
                </button>
              </>
            )}
          </div>
        </div>
      )}

      {showTableSelection && (
        <div className="table-selection-panel">
          <h3><FaDatabase /> Select Tables to Index</h3>
          <p className="panel-description">
            Found <strong>{discoveredTables.length} tables</strong> in database <strong>{discoveryInfo?.database_name}</strong>.
            Select the tables you want to index for AI querying.
          </p>

          <div className="table-selection-header">
            <label className="checkbox-label">
              <input
                type="checkbox"
                checked={selectedTables.length === discoveredTables.length}
                onChange={toggleAllTables}
              />
              <span><strong>Select All ({selectedTables.length}/{discoveredTables.length})</strong></span>
            </label>
          </div>

          <div className="tables-grid">
            {discoveredTables.map((table) => (
              <div key={table.name} className="table-item">
                <label className="table-checkbox-label">
                  <input
                    type="checkbox"
                    checked={selectedTables.includes(table.name)}
                    onChange={() => toggleTableSelection(table.name)}
                  />
                  <div className="table-info">
                    <div className="table-name">
                      <FaDatabase className="table-icon" />
                      <strong>{table.name}</strong>
                      {table.has_primary_key && <span className="badge badge-success">PK</span>}
                    </div>
                    <div className="table-details">
                      <span>{table.column_count} columns</span>
                      {table.comment && <span className="table-comment">{table.comment}</span>}
                    </div>
                  </div>
                </label>
              </div>
            ))}
          </div>
        </div>
      )}

      {message && (
        <div className={`alert alert-${message.type}`}>
          {message.text}
        </div>
      )}

      <div className="databases-section">
        <div className="section-header">
          <h3><FaDatabase /> Indexed Databases</h3>
          <button className="btn-icon" onClick={fetchDatabases} title="Refresh">
            <FaSync />
          </button>
        </div>

        {databases.length === 0 ? (
          <div className="empty-state">
            <FaDatabase className="empty-icon" />
            <p>No databases indexed yet</p>
            <p className="empty-hint">Use Auto-Index MySQL to get started</p>
          </div>
        ) : (
          <div className="database-list">
            {databases.map((db) => (
              <div key={db.database_id} className="database-card">
                <div className="card-icon">
                  <FaDatabase />
                </div>
                <div className="card-content">
                  <h4>{db.database_id}</h4>
                  <div className="card-details">
                    <span><strong>Host:</strong> {db.host}:{db.port}</span>
                    <span><strong>User:</strong> {db.user}</span>
                    <span><strong>Database:</strong> {db.database_name}</span>
                    <span className="card-timestamp"><strong>Created:</strong> {new Date(db.created_at).toLocaleString()}</span>
                  </div>
                  <span className="badge badge-success"><FaCheck /> Indexed & Configured</span>
                </div>
                <div className="card-actions">
                  <button 
                    className="btn-view-schema" 
                    onClick={() => onDatabaseSelect && onDatabaseSelect(db.database_id)}
                    title="View schema"
                  >
                    <FaSitemap />
                  </button>
                  <button 
                    className="btn-reindex" 
                    onClick={() => reindexDatabase(db.database_id)}
                    title="Re-index database"
                    disabled={loading}
                  >
                    <FaSync />
                  </button>
                  <button 
                    className="btn-delete" 
                    onClick={() => handleDeleteClick(db)}
                    title="Delete database"
                  >
                    <FaTrash />
                  </button>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Delete Confirmation Modal */}
      <Modal
        isOpen={showDeleteModal}
        onClose={cancelDelete}
        title="Delete Database"
        onConfirm={confirmDelete}
        confirmText={deleting ? 'Deleting...' : 'Delete'}
        confirmClass="btn-danger"
      >
        <div className="delete-confirmation">
          <p>Are you sure you want to delete the database configuration:</p>
          <div className="delete-db-info">
            <strong>{databaseToDelete?.database_id}</strong>
            <span>{databaseToDelete?.host}:{databaseToDelete?.port}/{databaseToDelete?.database_name}</span>
          </div>
          <div className="warning-box">
            <p><strong>⚠️ Warning:</strong></p>
            <ul>
              <li>All stored credentials will be permanently deleted</li>
              <li>All indexed schema data will be removed</li>
              <li>This action cannot be undone</li>
            </ul>
          </div>
        </div>
      </Modal>
    </div>
  )
}

export default DatabaseManager
