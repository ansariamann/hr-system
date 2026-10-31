import React from 'react';

export function ClientNavbar({ onRequestRole }) {
  return (
    <header className="app-header" style={{ borderBottomColor: 'rgba(14, 165, 233, 0.25)' }}>
      <div className="brand-section">
        <div
          style={{
            width: '38px',
            height: '38px',
            borderRadius: 'var(--radius-md)',
            background: 'linear-gradient(135deg, #0ea5e9 0%, #3b82f6 100%)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            fontSize: '1.15rem',
            color: '#fff',
            fontWeight: '800',
            boxShadow: '0 0 16px rgba(14, 165, 233, 0.4)',
          }}
        >
          🏢
        </div>
        <div>
          <div className="brand-title">
            Acme Global Technologies
            <span
              className="brand-badge"
              style={{
                background: 'rgba(14, 165, 233, 0.18)',
                color: '#38bdf8',
                borderColor: 'rgba(14, 165, 233, 0.35)',
              }}
            >
              CLIENT PORTAL
            </span>
          </div>
          <div style={{ fontSize: '0.72rem', color: 'var(--text-muted)' }}>
            Client Organization Workspace
          </div>
        </div>
      </div>

      <div className="header-actions">
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: '6px',
            fontSize: '0.75rem',
            color: '#38bdf8',
            background: 'rgba(14, 165, 233, 0.1)',
            padding: '4px 10px',
            borderRadius: 'var(--radius-full)',
            border: '1px solid rgba(14, 165, 233, 0.3)',
            fontWeight: '600',
          }}
        >
          <span>Client Portal</span>
        </div>

        <button className="btn btn-primary btn-sm" onClick={onRequestRole}>
          <span>+ Request New Role</span>
        </button>

        <div
          style={{
            width: '34px',
            height: '34px',
            borderRadius: '50%',
            background: 'linear-gradient(135deg, #0ea5e9 0%, #3b82f6 100%)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            fontWeight: '700',
            fontSize: '0.8rem',
            color: '#fff',
            boxShadow: '0 0 10px rgba(14, 165, 233, 0.3)',
          }}
          title="Client Reviewer Session"
        >
          CP
        </div>
      </div>
    </header>
  );
}
