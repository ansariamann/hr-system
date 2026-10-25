import React, { useState, useMemo } from 'react';

export function HrDashboard({
  candidates,
  onReviewCandidate,
  onScheduleInterview,
  onSendToClient,
  onToggleBlacklist,
  onResetData,
}) {
  const [search, setSearch] = useState('');
  const [selectedSkill, setSelectedSkill] = useState('All');
  const [selectedLocation, setSelectedLocation] = useState('All');
  const [excludeLeavers, setExcludeLeavers] = useState(true);

  // Available skills for faceted search
  const allSkills = useMemo(() => {
    const set = new Set();
    candidates.forEach((c) => c.skills?.forEach((s) => set.add(s)));
    return ['All', ...Array.from(set)];
  }, [candidates]);

  // Available locations
  const allLocations = useMemo(() => {
    const set = new Set();
    candidates.forEach((c) => {
      if (c.location) set.add(c.location);
    });
    return ['All', ...Array.from(set)];
  }, [candidates]);

  // Filtered candidate list
  const filteredCandidates = useMemo(() => {
    return candidates.filter((cand) => {
      // Exclude Leavers / Blacklisted candidates (Strict Policy Enforcement)
      if (excludeLeavers && cand.isBlacklisted) {
        return false;
      }
      if (search) {
        const q = search.toLowerCase();
        const matchesName = cand.name?.toLowerCase().includes(q);
        const matchesEmail = cand.email?.toLowerCase().includes(q);
        const matchesSkill = cand.skills?.some((s) => s.toLowerCase().includes(q));
        if (!matchesName && !matchesEmail && !matchesSkill) return false;
      }
      if (selectedSkill !== 'All') {
        if (!cand.skills?.some((s) => s.toLowerCase() === selectedSkill.toLowerCase())) {
          return false;
        }
      }
      if (selectedLocation !== 'All') {
        if (!cand.location?.toLowerCase().includes(selectedLocation.toLowerCase())) {
          return false;
        }
      }
      return true;
    });
  }, [candidates, search, selectedSkill, selectedLocation, excludeLeavers]);

  // Calculated Metrics
  const metrics = useMemo(() => {
    const total = candidates.length;
    const inPipeline = candidates.filter((c) => ['submitted', 'interview_scheduled', 'selected'].includes(c.currentStatus)).length;
    const interviewed = candidates.filter((c) => c.currentStatus === 'interview_scheduled').length;
    const joined = candidates.filter((c) => c.currentStatus === 'joined').length;
    const blacklisted = candidates.filter((c) => c.isBlacklisted).length;
    return { total, inPipeline, interviewed, joined, blacklisted };
  }, [candidates]);

  const getStatusBadge = (status, isBlacklisted) => {
    if (isBlacklisted) {
      return <span className="badge badge-left">⚠️ Leaver (Blacklisted)</span>;
    }
    switch (status) {
      case 'pool': return <span className="badge badge-pool">Pool</span>;
      case 'submitted': return <span className="badge badge-submitted">Submitted</span>;
      case 'interview_scheduled': return <span className="badge badge-interview">Interview</span>;
      case 'selected': return <span className="badge badge-selected">Selected</span>;
      case 'joined': return <span className="badge badge-joined">Joined</span>;
      case 'left_company': return <span className="badge badge-left">Left Company</span>;
      default: return <span className="badge badge-pool">{status}</span>;
    }
  };

  return (
    <div>
      {/* Metrics Row */}
      <div className="metrics-grid">
        <div className="metric-card">
          <div className="metric-header">
            <span>Total Candidates</span>
            <span>👥</span>
          </div>
          <div className="metric-value">{metrics.total}</div>
          <div className="metric-footer">Across all tenant pools</div>
        </div>

        <div className="metric-card">
          <div className="metric-header">
            <span>In Client Review</span>
            <span>⚡</span>
          </div>
          <div className="metric-value" style={{ color: '#38bdf8' }}>{metrics.inPipeline}</div>
          <div className="metric-footer">Active FSM applications</div>
        </div>

        <div className="metric-card">
          <div className="metric-header">
            <span>Interviews Scheduled</span>
            <span>📅</span>
          </div>
          <div className="metric-value" style={{ color: '#a5b4fc' }}>{metrics.interviewed}</div>
          <div className="metric-footer">Direct & Client rounds</div>
        </div>

        <div className="metric-card">
          <div className="metric-header">
            <span>Ex-Employees Excluded</span>
            <span>🛡️</span>
          </div>
          <div className="metric-value" style={{ color: '#fca5a5' }}>{metrics.blacklisted}</div>
          <div className="metric-footer">Automatic Leaver loop enforced</div>
        </div>
      </div>

      {/* Main Candidate Card & Faceted Search */}
      <div className="card">
        <div className="card-header">
          <div>
            <h2 style={{ fontSize: '1.15rem' }}>Master Candidate Database</h2>
            <div style={{ fontSize: '0.78rem', color: 'var(--text-muted)' }}>
              PostgreSQL Native Full-Text Search with JSONB Skills & Automatic Exclusion
            </div>
          </div>
          <div style={{ display: 'flex', gap: '0.75rem', alignItems: 'center' }}>
            <button className="btn btn-secondary btn-sm" onClick={onResetData} title="Reset demo records">
              🔄 Reset Demo DB
            </button>
          </div>
        </div>

        {/* Faceted Search Bar */}
        <div className="search-filter-section">
          <div className="search-bar-row">
            <div className="search-input-wrapper">
              <svg className="search-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <circle cx="11" cy="11" r="8"></circle>
                <line x1="21" y1="21" x2="16.65" y2="16.65"></line>
              </svg>
              <input
                type="text"
                className="search-input"
                placeholder="Search candidates by name, email, or skill keywords..."
                value={search}
                onChange={(e) => setSearch(e.target.value)}
              />
            </div>

            <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
              <span style={{ fontSize: '0.78rem', color: 'var(--text-muted)' }}>City:</span>
              <select
                className="form-select"
                style={{ padding: '0.5rem 0.85rem', fontSize: '0.82rem' }}
                value={selectedLocation}
                onChange={(e) => setSelectedLocation(e.target.value)}
              >
                {allLocations.map((loc) => (
                  <option key={loc} value={loc}>{loc}</option>
                ))}
              </select>
            </div>

            {/* Leaver Exclusion Policy Banner / Toggle */}
            <div
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: '0.5rem',
                cursor: 'pointer',
                background: excludeLeavers ? 'rgba(239, 68, 68, 0.12)' : 'rgba(255, 255, 255, 0.05)',
                padding: '6px 12px',
                borderRadius: 'var(--radius-full)',
                border: '1px solid ' + (excludeLeavers ? 'rgba(239, 68, 68, 0.35)' : 'var(--border-subtle)'),
                transition: 'all 200ms ease'
              }}
              onClick={() => setExcludeLeavers(!excludeLeavers)}
              title="Per the Architecture Blueprint: Terminated former employees are automatically excluded from searches"
            >
              <input
                type="checkbox"
                checked={excludeLeavers}
                onChange={(e) => setExcludeLeavers(e.target.checked)}
                style={{ accentColor: '#ef4444', cursor: 'pointer' }}
              />
              <span style={{ fontSize: '0.75rem', fontWeight: '600', color: excludeLeavers ? '#fca5a5' : 'var(--text-secondary)' }}>
                {excludeLeavers ? '🛡️ Policy: Exclude Ex-Employees (ACTIVE)' : '⚠️ Ex-Employees Included (Audit)'}
              </span>
            </div>
          </div>

          {/* Faceted Skill Pills */}
          <div className="filter-pills">
            <span style={{ fontSize: '0.78rem', color: 'var(--text-muted)' }}>Skills:</span>
            {allSkills.slice(0, 10).map((skill) => (
              <button
                key={skill}
                className={`filter-pill ${selectedSkill === skill ? 'active' : ''}`}
                onClick={() => setSelectedSkill(skill)}
              >
                {skill}
              </button>
            ))}
          </div>
        </div>

        {/* Data Table */}
        <div className="table-responsive">
          <table className="data-table">
            <thead>
              <tr>
                <th>Candidate</th>
                <th>Location</th>
                <th>Key Skills (JSONB)</th>
                <th>Exp / CTC</th>
                <th>Status</th>
                <th style={{ textAlign: 'right' }}>Actions</th>
              </tr>
            </thead>
            <tbody>
              {filteredCandidates.length === 0 ? (
                <tr>
                  <td colSpan="6" style={{ textAlign: 'center', padding: '3rem', color: 'var(--text-muted)' }}>
                    No candidates match the current faceted filters.
                  </td>
                </tr>
              ) : (
                filteredCandidates.map((cand) => (
                  <tr key={cand.id}>
                    <td>
                      <div style={{ fontWeight: '600', color: cand.isBlacklisted ? '#fca5a5' : '#fff' }}>
                        {cand.name}
                      </div>
                      <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>
                        {cand.email} • {cand.phone || 'No phone'}
                      </div>
                    </td>

                    <td>
                      <span style={{ fontSize: '0.82rem', color: 'var(--text-secondary)' }}>
                        📍 {cand.location || 'Remote'}
                      </span>
                    </td>

                    <td>
                      <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.3rem', maxWidth: '280px' }}>
                        {cand.skills?.map((s) => (
                          <span key={s} className="skill-tag">{s}</span>
                        ))}
                      </div>
                    </td>

                    <td>
                      <div style={{ fontSize: '0.82rem' }}>{cand.experienceYears} yrs exp</div>
                      <div style={{ fontSize: '0.75rem', color: '#34d399', fontWeight: '600' }}>
                        ₹{cand.ctcCurrent ? (cand.ctcCurrent / 100000).toFixed(1) + ' LPA' : 'N/A'}
                      </div>
                    </td>

                    <td>
                      {getStatusBadge(cand.currentStatus, cand.isBlacklisted)}
                    </td>

                    <td style={{ textAlign: 'right' }}>
                      <div style={{ display: 'inline-flex', gap: '0.4rem' }}>
                        <button
                          className="btn btn-secondary btn-sm"
                          onClick={() => onReviewCandidate(cand)}
                          title="Open Split-Screen Document & Entity Review"
                        >
                          📄 Review
                        </button>

                        <button
                          className="btn btn-primary btn-sm"
                          onClick={() => onScheduleInterview(cand)}
                          title="Schedule Direct Interview"
                        >
                          📅 Interview
                        </button>

                        <button
                          className="btn btn-ghost btn-sm"
                          onClick={() => onSendToClient(cand.id)}
                          title="Send Profile to Client Portal via FSM"
                        >
                          🚀 Send
                        </button>
                      </div>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
