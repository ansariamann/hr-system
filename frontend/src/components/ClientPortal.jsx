import React, { useState, useMemo } from 'react';

export function ClientPortal({
  candidates,
  onTransitionStatus,
  onReviewCandidate,
  onAddJob,
  requestRoleOpen,
  onRequestRoleClose,
}) {
  const [selectedCandidate, setSelectedCandidate] = useState(null);
  const [modalType, setModalType] = useState(null); // 'interview' | 'reject' | 'terminate' | 'new-job'

  React.useEffect(() => {
    if (requestRoleOpen) {
      setModalType('new-job');
      onRequestRoleClose?.();
    }
  }, [requestRoleOpen, onRequestRoleClose]);

  // Modal form states
  const [interviewDate, setInterviewDate] = useState(new Date().toISOString().slice(0, 16));
  const [interviewMode, setInterviewMode] = useState('Google Meet');
  const [rejectReason, setRejectReason] = useState('Missing required technical skills');
  const [rejectFeedback, setRejectFeedback] = useState('');
  const [exitReason, setExitReason] = useState('Contract Completed');
  const [exitDate, setExitDate] = useState(new Date().toISOString().slice(0, 10));

  // Job Opening form
  const [jobTitle, setJobTitle] = useState('');
  const [jobSkills, setJobSkills] = useState('');
  const [jobBudget, setJobBudget] = useState('');

  // Kanban Columns
  const toReview = useMemo(() => {
    return candidates.filter((c) => ['submitted', 'under_review', 'pool'].includes(c.currentStatus) && !c.isBlacklisted);
  }, [candidates]);

  const interview = useMemo(() => {
    return candidates.filter((c) => c.currentStatus === 'interview_scheduled' && !c.isBlacklisted);
  }, [candidates]);

  const selected = useMemo(() => {
    return candidates.filter((c) => ['selected', 'offer_extended'].includes(c.currentStatus) && !c.isBlacklisted);
  }, [candidates]);

  const joined = useMemo(() => {
    return candidates.filter((c) => c.currentStatus === 'joined' && !c.isBlacklisted);
  }, [candidates]);

  // Handle Interview Schedule Action
  const handleConfirmInterview = (e) => {
    e.preventDefault();
    if (!selectedCandidate) return;
    onTransitionStatus(selectedCandidate.id, 'interview_scheduled', {
      interviewDate,
      interviewMode,
    });
    setModalType(null);
    setSelectedCandidate(null);
  };

  // Handle Reject Action
  const handleConfirmReject = (e) => {
    e.preventDefault();
    if (!selectedCandidate) return;
    onTransitionStatus(selectedCandidate.id, 'rejected', {
      reason: rejectReason,
      feedback: rejectFeedback,
    });
    setModalType(null);
    setSelectedCandidate(null);
  };

  // Handle Terminate (Leaver) Action - CRITICAL FSM STEP
  const handleConfirmTerminate = (e) => {
    e.preventDefault();
    if (!selectedCandidate) return;
    onTransitionStatus(selectedCandidate.id, 'left_company', {
      exitDate,
      reason: exitReason,
    });
    setModalType(null);
    setSelectedCandidate(null);
  };

  // Handle Submit Job Opening
  const handleCreateJob = (e) => {
    e.preventDefault();
    onAddJob?.({
      title: jobTitle,
      skills: jobSkills.split(',').map((s) => s.trim()).filter(Boolean),
      budget: jobBudget,
      date: new Date().toISOString().slice(0, 10),
    });
    setJobTitle('');
    setJobSkills('');
    setJobBudget('');
    setModalType(null);
  };

  return (
    <div>
      {/* Client Overview Banner */}
      <div
        className="card"
        style={{
          marginBottom: '1.75rem',
          padding: '1.25rem 1.75rem',
          background: 'linear-gradient(90deg, rgba(14, 165, 233, 0.08) 0%, rgba(30, 41, 59, 0.4) 100%)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          flexWrap: 'wrap',
          gap: '1rem',
        }}
      >
        <div>
          <h2 style={{ fontSize: '1.15rem', display: 'flex', alignItems: 'center', gap: '0.6rem' }}>
            <span>Talent Review Kanban Pipeline</span>
            <span className="badge badge-submitted">4 Active Stages</span>
          </h2>
          <div style={{ fontSize: '0.78rem', color: 'var(--text-muted)' }}>
            Review candidate submissions from HR, set interview schedules, extend offers, or report leavers.
          </div>
        </div>

        <div style={{ display: 'flex', gap: '1rem', alignItems: 'center' }}>
          <div style={{ fontSize: '0.8rem', color: 'var(--text-secondary)' }}>
            <span style={{ color: '#38bdf8', fontWeight: '700' }}>{toReview.length}</span> To Review • <span style={{ color: '#a5b4fc', fontWeight: '700' }}>{interview.length}</span> In Interview • <span style={{ color: '#6ee7b7', fontWeight: '700' }}>{joined.length}</span> Active Hires
          </div>
        </div>
      </div>

      {/* Kanban Board Grid */}
      <div className="kanban-grid">
        {/* Column 1: To Review */}
        <div className="kanban-column">
          <div className="kanban-column-header" style={{ borderTop: '3px solid #06b6d4' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
              <span>📥 To Review</span>
              <span className="badge badge-submitted">{toReview.length}</span>
            </div>
            <span style={{ fontSize: '0.72rem', color: 'var(--text-muted)' }}>New Profiles</span>
          </div>

          <div className="kanban-cards-area">
            {toReview.length === 0 ? (
              <div style={{ padding: '2rem', textAlign: 'center', color: 'var(--text-muted)', fontSize: '0.8rem' }}>
                No candidate profiles awaiting review.
              </div>
            ) : (
              toReview.map((c) => (
                <div key={c.id} className="candidate-card">
                  <div className="candidate-card-header">
                    <div>
                      <div className="candidate-card-title">{c.name}</div>
                      <div className="candidate-card-subtitle">{c.location} • {c.experienceYears}y exp</div>
                    </div>
                    <span className="badge badge-submitted">Review</span>
                  </div>

                  <div className="candidate-card-skills">
                    {c.skills?.slice(0, 3).map((s) => (
                      <span key={s} className="skill-tag">{s}</span>
                    ))}
                  </div>

                  <div className="candidate-card-footer">
                    <span className="ctc-text">
                      ₹{c.ctcCurrent ? (c.ctcCurrent / 100000).toFixed(1) + ' LPA' : 'CTC on request'}
                    </span>
                    <div style={{ display: 'flex', gap: '0.35rem' }}>
                      <button
                        className="btn btn-secondary btn-sm"
                        style={{ padding: '2px 7px', fontSize: '0.72rem' }}
                        onClick={() => onReviewCandidate(c)}
                      >
                        📄 Resume
                      </button>
                      <button
                        className="btn btn-primary btn-sm"
                        style={{ padding: '2px 7px', fontSize: '0.72rem' }}
                        onClick={() => {
                          setSelectedCandidate(c);
                          setModalType('interview');
                        }}
                      >
                        📅 Interview
                      </button>
                      <button
                        className="btn btn-danger btn-sm"
                        style={{ padding: '2px 7px', fontSize: '0.72rem' }}
                        onClick={() => {
                          setSelectedCandidate(c);
                          setModalType('reject');
                        }}
                      >
                        ✕
                      </button>
                    </div>
                  </div>
                </div>
              ))
            )}
          </div>
        </div>

        {/* Column 2: Interview Scheduled */}
        <div className="kanban-column">
          <div className="kanban-column-header" style={{ borderTop: '3px solid #6366f1' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
              <span>📅 Interview</span>
              <span className="badge badge-interview">{interview.length}</span>
            </div>
            <span style={{ fontSize: '0.72rem', color: 'var(--text-muted)' }}>Scheduled</span>
          </div>

          <div className="kanban-cards-area">
            {interview.length === 0 ? (
              <div style={{ padding: '2rem', textAlign: 'center', color: 'var(--text-muted)', fontSize: '0.8rem' }}>
                No active interviews currently scheduled.
              </div>
            ) : (
              interview.map((c) => (
                <div key={c.id} className="candidate-card">
                  <div className="candidate-card-header">
                    <div>
                      <div className="candidate-card-title">{c.name}</div>
                      <div className="candidate-card-subtitle">{c.interviewDate ? new Date(c.interviewDate).toLocaleDateString() : 'Date TBD'}</div>
                    </div>
                    <span className="badge badge-interview">Round 1</span>
                  </div>

                  <div style={{ fontSize: '0.75rem', color: '#c7d2fe', background: 'rgba(99, 102, 241, 0.1)', padding: '4px 8px', borderRadius: 'var(--radius-sm)' }}>
                    Mode: {c.interviewMode || 'Google Meet'}
                  </div>

                  <div className="candidate-card-footer">
                    <button
                      className="btn btn-danger btn-sm"
                      style={{ padding: '2px 7px', fontSize: '0.72rem' }}
                      onClick={() => {
                        setSelectedCandidate(c);
                        setModalType('reject');
                      }}
                    >
                      Reject
                    </button>
                    <button
                      className="btn btn-success btn-sm"
                      style={{ padding: '2px 7px', fontSize: '0.72rem' }}
                      onClick={() => onTransitionStatus(c.id, 'selected')}
                    >
                      ✓ Select / Offer
                    </button>
                  </div>
                </div>
              ))
            )}
          </div>
        </div>

        {/* Column 3: Selected / Offer Extended */}
        <div className="kanban-column">
          <div className="kanban-column-header" style={{ borderTop: '3px solid #a855f7' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
              <span>🎉 Selected</span>
              <span className="badge badge-selected">{selected.length}</span>
            </div>
            <span style={{ fontSize: '0.72rem', color: 'var(--text-muted)' }}>Offer Extended</span>
          </div>

          <div className="kanban-cards-area">
            {selected.length === 0 ? (
              <div style={{ padding: '2rem', textAlign: 'center', color: 'var(--text-muted)', fontSize: '0.8rem' }}>
                No candidates with pending offer extensions.
              </div>
            ) : (
              selected.map((c) => (
                <div key={c.id} className="candidate-card">
                  <div className="candidate-card-header">
                    <div>
                      <div className="candidate-card-title">{c.name}</div>
                      <div className="candidate-card-subtitle">{c.email}</div>
                    </div>
                    <span className="badge badge-selected">Offer</span>
                  </div>

                  <div style={{ fontSize: '0.78rem', color: '#e9d5ff' }}>
                    Offer Extended: Target joining in 30 days
                  </div>

                  <div className="candidate-card-footer">
                    <button
                      className="btn btn-danger btn-sm"
                      style={{ padding: '2px 7px', fontSize: '0.72rem' }}
                      onClick={() => {
                        setSelectedCandidate(c);
                        setModalType('reject');
                      }}
                    >
                      Declined
                    </button>
                    <button
                      className="btn btn-success btn-sm"
                      style={{ padding: '2px 7px', fontSize: '0.72rem' }}
                      onClick={() => onTransitionStatus(c.id, 'joined')}
                    >
                      🚀 Confirm Joined
                    </button>
                  </div>
                </div>
              ))
            )}
          </div>
        </div>

        {/* Column 4: Joined (With Terminate/Leaver trigger) */}
        <div className="kanban-column">
          <div className="kanban-column-header" style={{ borderTop: '3px solid #10b981' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
              <span>🌟 Joined</span>
              <span className="badge badge-joined">{joined.length}</span>
            </div>
            <span style={{ fontSize: '0.72rem', color: 'var(--text-muted)' }}>Active Hires</span>
          </div>

          <div className="kanban-cards-area">
            {joined.length === 0 ? (
              <div style={{ padding: '2rem', textAlign: 'center', color: 'var(--text-muted)', fontSize: '0.8rem' }}>
                No active hired personnel in this tenant view.
              </div>
            ) : (
              joined.map((c) => (
                <div key={c.id} className="candidate-card" style={{ borderColor: 'rgba(16, 185, 129, 0.3)' }}>
                  <div className="candidate-card-header">
                    <div>
                      <div className="candidate-card-title">{c.name}</div>
                      <div className="candidate-card-subtitle">Active Employee</div>
                    </div>
                    <span className="badge badge-joined">Employed</span>
                  </div>

                  <div style={{ fontSize: '0.75rem', color: '#a7f3d0' }}>
                    Location: {c.location} • Compensation: ₹{(c.ctcExpected || c.ctcCurrent || 2000000) / 100000} LPA
                  </div>

                  <div className="candidate-card-footer">
                    <span style={{ fontSize: '0.72rem', color: 'var(--text-muted)' }}>Feedback loop</span>
                    {/* Terminate (Leaver) Action - Triggers Exclusion */}
                    <button
                      className="btn btn-danger btn-sm"
                      style={{ padding: '3px 8px', fontSize: '0.72rem' }}
                      onClick={() => {
                        setSelectedCandidate(c);
                        setModalType('terminate');
                      }}
                      title="Terminate employee and trigger the Leaver exclusion loop"
                    >
                      🛑 Mark Left (Leaver)
                    </button>
                  </div>
                </div>
              ))
            )}
          </div>
        </div>
      </div>

      {/* Modal: Select for Interview */}
      {modalType === 'interview' && selectedCandidate && (
        <div className="modal-overlay" onClick={() => setModalType(null)}>
          <div className="card" style={{ width: '90%', maxWidth: '480px' }} onClick={(e) => e.stopPropagation()}>
            <div className="card-header">
              <h3 style={{ fontSize: '1.05rem' }}>📅 Select Candidate for Interview</h3>
              <button className="btn btn-ghost btn-sm" onClick={() => setModalType(null)}>✕</button>
            </div>
            <form onSubmit={handleConfirmInterview} style={{ padding: '1.25rem', display: 'flex', flexDirection: 'column', gap: '1rem' }}>
              <div>Candidate: <strong>{selectedCandidate.name}</strong> ({selectedCandidate.email})</div>
              <div className="form-group">
                <label className="form-label">Date & Time</label>
                <input
                  type="datetime-local"
                  className="form-input"
                  value={interviewDate}
                  onChange={(e) => setInterviewDate(e.target.value)}
                  required
                />
              </div>
              <div className="form-group">
                <label className="form-label">Interview Mode</label>
                <select className="form-select" value={interviewMode} onChange={(e) => setInterviewMode(e.target.value)}>
                  <option value="Google Meet">Google Meet</option>
                  <option value="Zoom">Zoom</option>
                  <option value="In-Person Office">In-Person Office</option>
                </select>
              </div>
              <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '0.5rem' }}>
                <button type="button" className="btn btn-secondary" onClick={() => setModalType(null)}>Cancel</button>
                <button type="submit" className="btn btn-primary">Schedule & Notify HR</button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Modal: Reject Candidate */}
      {modalType === 'reject' && selectedCandidate && (
        <div className="modal-overlay" onClick={() => setModalType(null)}>
          <div className="card" style={{ width: '90%', maxWidth: '480px' }} onClick={(e) => e.stopPropagation()}>
            <div className="card-header">
              <h3 style={{ fontSize: '1.05rem' }}>❌ Reject Candidate Profile</h3>
              <button className="btn btn-ghost btn-sm" onClick={() => setModalType(null)}>✕</button>
            </div>
            <form onSubmit={handleConfirmReject} style={{ padding: '1.25rem', display: 'flex', flexDirection: 'column', gap: '1rem' }}>
              <div>Candidate: <strong>{selectedCandidate.name}</strong></div>
              <div className="form-group">
                <label className="form-label">Reason for Rejection *</label>
                <select className="form-select" value={rejectReason} onChange={(e) => setRejectReason(e.target.value)}>
                  <option value="Missing required technical skills">Missing required technical skills</option>
                  <option value="Salary expectation exceeds budget">Salary expectation exceeds budget</option>
                  <option value="Cultural fit / Communication">Cultural fit / Communication</option>
                  <option value="Candidate accepted another offer">Candidate accepted another offer</option>
                  <option value="Failed coding test">Failed coding test</option>
                </select>
              </div>
              <div className="form-group">
                <label className="form-label">Client Feedback for Recruiter</label>
                <textarea
                  className="form-textarea"
                  value={rejectFeedback}
                  onChange={(e) => setRejectFeedback(e.target.value)}
                  placeholder="Provide constructive feedback for the candidate..."
                  rows={3}
                />
              </div>
              <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '0.5rem' }}>
                <button type="button" className="btn btn-secondary" onClick={() => setModalType(null)}>Cancel</button>
                <button type="submit" className="btn btn-danger">Confirm Rejection</button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Modal: Terminate Employee (Leaver) - CRITICAL BUSINESS RULE */}
      {modalType === 'terminate' && selectedCandidate && (
        <div className="modal-overlay" onClick={() => setModalType(null)}>
          <div className="card" style={{ width: '90%', maxWidth: '520px', border: '1px solid #ef4444' }} onClick={(e) => e.stopPropagation()}>
            <div className="card-header" style={{ background: 'rgba(239, 68, 68, 0.1)' }}>
              <h3 style={{ fontSize: '1.05rem', color: '#fca5a5' }}>🛡️ Terminate Employee (Leaver Loop)</h3>
              <button className="btn btn-ghost btn-sm" onClick={() => setModalType(null)}>✕</button>
            </div>
            <form onSubmit={handleConfirmTerminate} style={{ padding: '1.25rem', display: 'flex', flexDirection: 'column', gap: '1rem' }}>
              <div style={{ fontSize: '0.85rem', color: '#fecaca', background: 'rgba(239, 68, 68, 0.15)', padding: '0.75rem', borderRadius: 'var(--radius-sm)' }}>
                <strong>Important Policy Enforcement:</strong> Marking <strong>{selectedCandidate.name}</strong> as "Left Company" will immediately execute the Leaver state transition, setting <code>is_blacklisted = TRUE</code> in the master candidate repository to exclude them from future searches.
              </div>

              <div className="form-group">
                <label className="form-label">Exit Date *</label>
                <input
                  type="date"
                  className="form-input"
                  value={exitDate}
                  onChange={(e) => setExitDate(e.target.value)}
                  required
                />
              </div>

              <div className="form-group">
                <label className="form-label">Exit Reason / Separation Type</label>
                <select className="form-select" value={exitReason} onChange={(e) => setExitReason(e.target.value)}>
                  <option value="Contract Completed">Contract Completed</option>
                  <option value="Voluntary Resignation">Voluntary Resignation</option>
                  <option value="Performance Separation">Performance Separation</option>
                  <option value="Relocation">Relocation</option>
                  <option value="Ineligible for Rehire">Ineligible for Rehire (Blacklist)</option>
                </select>
              </div>

              <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '0.5rem', marginTop: '0.5rem' }}>
                <button type="button" className="btn btn-secondary" onClick={() => setModalType(null)}>Cancel</button>
                <button type="submit" className="btn btn-danger">Confirm Separation & Blacklist</button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Modal: New Job Request */}
      {modalType === 'new-job' && (
        <div className="modal-overlay" onClick={() => setModalType(null)}>
          <div className="card" style={{ width: '90%', maxWidth: '500px' }} onClick={(e) => e.stopPropagation()}>
            <div className="card-header">
              <h3 style={{ fontSize: '1.05rem' }}>📝 Submit Job Requirement</h3>
              <button className="btn btn-ghost btn-sm" onClick={() => setModalType(null)}>✕</button>
            </div>
            <form onSubmit={handleCreateJob} style={{ padding: '1.25rem', display: 'flex', flexDirection: 'column', gap: '1rem' }}>
              <div className="form-group">
                <label className="form-label">Role Title *</label>
                <input
                  type="text"
                  className="form-input"
                  placeholder="e.g. Senior Java / Spring Boot Engineer"
                  value={jobTitle}
                  onChange={(e) => setJobTitle(e.target.value)}
                  required
                />
              </div>
              <div className="form-group">
                <label className="form-label">Required Skills (Comma-separated)</label>
                <input
                  type="text"
                  className="form-input"
                  placeholder="Java, Spring Boot, PostgreSQL, Docker"
                  value={jobSkills}
                  onChange={(e) => setJobSkills(e.target.value)}
                  required
                />
              </div>
              <div className="form-group">
                <label className="form-label">Annual Budget / Compensation</label>
                <input
                  type="text"
                  className="form-input"
                  placeholder="e.g. ₹28 - 35 LPA or $140k"
                  value={jobBudget}
                  onChange={(e) => setJobBudget(e.target.value)}
                />
              </div>
              <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '0.5rem' }}>
                <button type="button" className="btn btn-secondary" onClick={() => setModalType(null)}>Cancel</button>
                <button type="submit" className="btn btn-primary">Submit to HR Team</button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
