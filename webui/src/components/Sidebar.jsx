import React from 'react'
import { FaQuestionCircle, FaDatabase, FaBook, FaSitemap, FaCog } from 'react-icons/fa'
import './Sidebar.css'

function Sidebar({ activeView, setActiveView }) {
  const menuItems = [
    { id: 'query', label: 'Ask Questions', icon: FaQuestionCircle },
    { id: 'databases', label: 'Databases', icon: FaDatabase },
    { id: 'knowledge', label: 'Knowledge Base', icon: FaBook },
    { id: 'settings', label: 'Settings', icon: FaCog },
  ]

  return (
    <aside className="sidebar">
      <nav className="sidebar-nav">
        {menuItems.map((item) => (
          <button
            key={item.id}
            className={`nav-item ${activeView === item.id ? 'active' : ''}`}
            onClick={() => setActiveView(item.id)}
          >
            <item.icon className="nav-icon" />
            <span className="nav-label">{item.label}</span>
          </button>
        ))}
      </nav>
    </aside>
  )
}

export default Sidebar
