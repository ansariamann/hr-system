import React from 'react';

export function Navbar({ activePortal, setActivePortal, onNewCandidate, isSseActive }) {
  return (
    <header className="app-header">
      <div className="brand-section" onClick={() => setActivePortal('hr')}>
        <div className="brand-logo">HR</div>
        <div>
          <div className="brand-title">
            ATS Enterprise
            <span className="brand-badge">PRO</span>
          </div>
          <div style={{ fontSize: '0.72rem', color: 'var(--text-muted)' }}>
            Modular Monolith • Talent Pipeline
          </div>
        </div>
      </div>

      <nav className="nav-tabs" aria-label="Portal Navigation">
        <button
          className={`nav-tab-btn ${activePortal === 'hr' ? 'active' : ''}`}
          onClick={() => setActivePortal('hr')}
        >
          <span>⚡ HR Power Dashboard</span>
        </button>
        <button
          className={`nav-tab-btn ${activePortal === 'client' ? 'active' : ''}`}
          onClick={() => setActivePortal('client')}
        >
          <span>🤝 Client Portal (Kanban)</span>
        </button>
      </nav>

      <div className="header-actions">
        <div className="live-indicator" title="Connected to Server-Sent Events stream">
          <div className="live-dot"></div>
          <span>{isSseActive ? 'SSE Real-Time: Active' : 'Live Sync'}</span>
        </div>

        {activePortal === 'hr' && (
          <button className="btn btn-primary btn-sm" onClick={onNewCandidate}>
            <span>+ Add Candidate</span>
          </button>
        )}

        <div style={{
          width: '34px',
          height: '34px',
          borderRadius: '50%',
          background: 'linear-gradient(135deg, #10b981 0%, #06b6d4 100%)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          fontWeight: '700',
          fontSize: '0.8rem',
          color: '#fff',
          boxShadow: '0 0 10px rgba(16, 185, 129, 0.3)'
        }}>
          {activePortal === 'hr' ? 'HR' : 'CP'}
        </div>
      </div>
    </header>
  );
}
