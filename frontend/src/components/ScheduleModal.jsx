import React, { useState } from 'react';

export function ScheduleModal({ candidate, onClose, onSchedule }) {
  const [interviewDate, setInterviewDate] = useState(new Date().toISOString().slice(0, 16));
  const [mode, setMode] = useState('Google Meet');
  const [notes, setNotes] = useState('Technical interview round 1: architecture & system design.');

  const handleSubmit = (e) => {
    e.preventDefault();
    onSchedule(candidate.id, {
      interviewDate,
      interviewMode: mode,
      notes,
    });
    onClose();
  };

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="card" style={{ width: '90%', maxWidth: '520px' }} onClick={(e) => e.stopPropagation()}>
        <div className="card-header">
          <h2 style={{ fontSize: '1.15rem' }}>📅 Schedule Interview</h2>
          <button className="btn btn-ghost btn-sm" onClick={onClose}>✕</button>
        </div>

        <form onSubmit={handleSubmit} style={{ padding: '1.5rem', display: 'flex', flexDirection: 'column', gap: '1.15rem' }}>
          <div>
            <div style={{ fontSize: '0.82rem', color: 'var(--text-muted)' }}>Candidate</div>
            <div style={{ fontSize: '1.05rem', fontWeight: '700' }}>{candidate.name}</div>
            <div style={{ fontSize: '0.78rem', color: '#818cf8' }}>{candidate.email}</div>
          </div>

          <div className="form-group">
            <label className="form-label">Interview Date & Time *</label>
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
            <select className="form-select" value={mode} onChange={(e) => setMode(e.target.value)}>
              <option value="Google Meet">Google Meet (Online)</option>
              <option value="Zoom">Zoom</option>
              <option value="Microsoft Teams">Microsoft Teams</option>
              <option value="In-Person Office">In-Person Office</option>
            </select>
          </div>

          <div className="form-group">
            <label className="form-label">Agenda / Instructions</label>
            <textarea
              className="form-textarea"
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
              rows={3}
            />
          </div>

          <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '0.75rem', marginTop: '0.5rem' }}>
            <button type="button" className="btn btn-secondary" onClick={onClose}>Cancel</button>
            <button type="submit" className="btn btn-primary">Confirm & Schedule</button>
          </div>
        </form>
      </div>
    </div>
  );
}
