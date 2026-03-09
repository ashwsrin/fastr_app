import { BrowserRouter as Router, Routes, Route, Link, useLocation } from 'react-router-dom'
import SqlDeveloper from './pages/SqlDeveloper'
import './index.css'

function Navigation() {
  const location = useLocation();
  return (
    <nav className="header-nav">
      <Link to="/" className={`nav-link ${location.pathname === '/' ? 'active' : ''}`}>Home</Link>
      <Link to="/developer" className={`nav-link ${location.pathname === '/developer' ? 'active' : ''}`}>Developer</Link>
    </nav>
  )
}

function WelcomePage() {
  return (
    <div className="main-content">
      <div className="execute-section">
        <div className="results-area">
          <div className="empty-state">
            <svg width="64" height="64" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1" style={{ marginBottom: '16px', color: 'var(--accent-color)', opacity: 0.8 }}>
              <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"></path>
            </svg>
            <h3>Welcome to FASTR Workspace</h3>
            <p>Access the Developer view from the top navigation to execute queries against your Fusion instances.</p>
          </div>
        </div>
      </div>
    </div>
  )
}

function App() {
  return (
    <Router>
      <div className="main-layout">
        {/* Global Top Header */}
        <header className="global-header">
          <div className="header-left">
            <div className="brand" style={{ marginRight: '32px', display: 'flex', alignItems: 'center', gap: '8px' }}>
              <img src="/logo.png" alt="FASTR Logo" style={{ height: '32px' }} />
              FASTR
            </div>
            <Navigation />
          </div>

          <div className="header-right">
            <button className="icon-btn" title="Settings">
              <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><circle cx="12" cy="12" r="3"></circle><path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1 0 2.83 2 2 0 0 1-2.83 0l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-2 2 2 2 0 0 1-2-2v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83 0 2 2 0 0 1 0-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1-2-2 2 2 0 0 1 2-2h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 0-2.83 2 2 0 0 1 2.83 0l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 2-2 2 2 0 0 1 2 2v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 0 2 2 0 0 1 0 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 2 2 2 2 0 0 1-2 2h-.09a1.65 1.65 0 0 0-1.51 1z"></path></svg>
            </button>
            <div className="user-profile">
              <div className="avatar">U</div>
              <span>User</span>
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><polyline points="6 9 12 15 18 9"></polyline></svg>
            </div>
          </div>
        </header>

        <Routes>
          <Route path="/" element={<WelcomePage />} />
          <Route path="/developer" element={<SqlDeveloper />} />
        </Routes>
      </div>
    </Router>
  )
}

export default App

