import React from 'react';

export function HrNavbar({ onNewCandidate, isSseActive, activeTab, setActiveTab }) {
  return (
    <header className="app-header">
      <div className="brand-section">
        <div className="brand-logo">HR</div>
        <div>
          <div className="brand-title">
            ATS Enterprise
            <span className="brand-badge">HR ADMIN</span>
          </div>
          <div style={{ fontSize: '0.72rem', color: 'var(--text-muted)' }}>
            Internal Talent Acquisition & Pipeline
          </div>
        </div>
      </div>

      <nav className="nav-tabs" aria-label="HR Internal Navigation">
        <button
          className={`nav-tab-btn ${activeTab === 'candidates' ? 'active' : ''}`}
          onClick={() => setActiveTab('candidates')}
        >
          <span>👥 Master Database</span>
        </button>
        <button
          className={`nav-tab-btn ${activeTab === 'interviews' ? 'active' : ''}`}
          onClick={() => setActiveTab('interviews')}
        >
          <span>📅 Direct Interviews</span>
        </button>
      </nav>

      <div className="header-actions">
        <div className="live-indicator" title="Connected to Server-Sent Events stream">
          <div className="live-dot"></div>
          <span>{isSseActive ? 'SSE Real-Time: Active' : 'Live Sync'}</span>
        </div>

        <button className="btn btn-primary btn-sm" onClick={onNewCandidate}>
          <span>+ Ingest Candidate</span>
        </button>

        <div
          style={{
            width: '34px',
            height: '34px',
            borderRadius: '50%',
            background: 'linear-gradient(135deg, #6366f1 0%, #a855f7 100%)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            fontWeight: '700',
            fontSize: '0.8rem',
            color: '#fff',
            boxShadow: '0 0 10px rgba(99, 102, 241, 0.4)',
          }}
          title="HR Administrator Session"
        >
          HR
        </div>
      </div>
    </header>
  );
}
