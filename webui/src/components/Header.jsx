import React from 'react'
import './Header.css'

function Header() {
  return (
    <header className="header">
      <div className="header-content">
        <div className="logo">
          <img src="/logo.png" alt="Tiny GenBI Logo" className="logo-image" />
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
