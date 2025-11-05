import { useState } from 'react'
import './App.css'
import Header from './components/Header'
import Sidebar from './components/Sidebar'
import QueryInterface from './components/QueryInterface'
import DatabaseManager from './components/DatabaseManager'
import SchemaViewer from './components/SchemaViewer'
import KnowledgeBase from './components/KnowledgeBase'
import SettingsPanel from './components/SettingsPanel'

function App() {
  const [activeView, setActiveView] = useState('query') // query, databases, schema, knowledge, settings
  const [selectedDatabase, setSelectedDatabase] = useState(null)
  const [apiConfig, setApiConfig] = useState({
    baseUrl: 'http://localhost:5556',
  })

  // Handle database selection from DatabaseManager
  const handleDatabaseSelect = (databaseId) => {
    setSelectedDatabase(databaseId)
    setActiveView('schema')
  }

  return (
    <div className="app">
      <Header />
      <div className="app-layout">
        <Sidebar activeView={activeView} setActiveView={setActiveView} />
        <main className="main-content">
          {activeView === 'query' && <QueryInterface apiConfig={apiConfig} />}
          {activeView === 'databases' && (
            <DatabaseManager 
              apiConfig={apiConfig} 
              onDatabaseSelect={handleDatabaseSelect}
            />
          )}
          {activeView === 'schema' && <SchemaViewer databaseId={selectedDatabase} apiConfig={apiConfig} />}
          {activeView === 'knowledge' && <KnowledgeBase apiConfig={apiConfig} />}
          {activeView === 'settings' && <SettingsPanel apiConfig={apiConfig} setApiConfig={setApiConfig} />}
        </main>
      </div>
    </div>
  )
}

export default App
