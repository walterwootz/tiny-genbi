import React from 'react'
import { FaDatabase } from 'react-icons/fa'
import './Header.css'

function Header() {
  return (
    <header className="header">
      <div className="header-content">
        <div className="logo">
          <FaDatabase className="logo-icon" />
          <h1>Tiny GenBI (MySQL)</h1>
          <span className="badge">Text-to-SQL</span>
        </div>
        <div className="header-info">
          <span className="status-indicator"></span>
          <span className="status-text">Connected</span>
        </div>
      </div>
    </header>
  )
}

export default Header
