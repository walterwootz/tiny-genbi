import { useState } from 'react'
import { FaCog, FaSave, FaServer } from 'react-icons/fa'
import './SettingsPanel.css'

function SettingsPanel({ apiConfig, setApiConfig }) {
  const [localConfig, setLocalConfig] = useState(apiConfig)
  const [saved, setSaved] = useState(false)

  const handleSave = () => {
    setApiConfig(localConfig)
    setSaved(true)
    setTimeout(() => setSaved(false), 3000)
  }

  return (
    <div className="settings-panel">
      <div className="settings-header">
        <h2><FaCog /> Settings</h2>
        <p>Configure API connection and preferences</p>
      </div>

      <div className="settings-content">
        <div className="settings-section">
          <h3><FaServer /> API Configuration</h3>
          
          <div className="form-group">
            <label>Tiny GenBI API Base URL</label>
            <input
              type="text"
              value={localConfig.baseUrl}
              onChange={(e) => setLocalConfig({ ...localConfig, baseUrl: e.target.value })}
              className="input"
              placeholder="http://localhost:5556"
            />
            <small className="hint">The base URL of your GenBI backend service</small>
          </div>

          <button className="btn btn-primary" onClick={handleSave}>
            <FaSave /> Save Settings
          </button>

          {saved && (
            <div className="alert alert-success" style={{ marginTop: '1rem' }}>
              ✅ Settings saved successfully!
            </div>
          )}
        </div>

        <div className="settings-section">
          <h3>About Tiny GenBI (MySQL)</h3>
          <div className="about-content">
            <p><strong>Version:</strong> 1.0.0 (Proof of Concept)</p>
            <p><strong>Description:</strong> Text-to-SQL system with natural language interface for MySQL databases</p>
            <p><strong>License:</strong> MIT License</p>
          </div>
        </div>

        <div className="settings-section">
          <h3>Documentation & Resources</h3>
          <div className="docs-links">
            <a href="http://localhost:5556/docs" target="_blank" rel="noopener noreferrer" className="doc-link">
              📚 API Documentation (Swagger)
            </a>
            <a href="http://localhost:5556/health" target="_blank" rel="noopener noreferrer" className="doc-link">
              🏥 Health Check
            </a>
            <a href="https://github.com/walterwootz/tiny-genbi" target="_blank" rel="noopener noreferrer" className="doc-link">
              🐙 GitHub Repository
            </a>
            <a href="https://github.com/walterwootz/tiny-genbi/issues" target="_blank" rel="noopener noreferrer" className="doc-link">
              🐛 Report an Issue
            </a>
            <a href="https://github.com/walterwootz/tiny-genbi/blob/main/README.md" target="_blank" rel="noopener noreferrer" className="doc-link">
              📖 User Guide
            </a>
          </div>
        </div>
      </div>
    </div>
  )
}

export default SettingsPanel
