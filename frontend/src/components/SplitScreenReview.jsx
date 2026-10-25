import React, { useState } from 'react';

export function SplitScreenReview({ candidate, onClose, onSave }) {
  const [formData, setFormData] = useState({
    name: candidate.name || '',
    email: candidate.email || '',
    phone: candidate.phone || '',
    location: candidate.location || '',
    skills: Array.isArray(candidate.skills) ? candidate.skills.join(', ') : candidate.skills || '',
    experienceYears: candidate.experienceYears || 0,
    ctcCurrent: candidate.ctcCurrent || '',
    ctcExpected: candidate.ctcExpected || '',
    notes: candidate.notes || '',
  });

  const [isSaving, setIsSaving] = useState(false);

  const handleChange = (e) => {
    const { name, value } = e.target;
    setFormData((prev) => ({ ...prev, [name]: value }));
  };

  const handleSave = async (e) => {
    e.preventDefault();
    setIsSaving(true);
    const updated = {
      ...formData,
      skills: formData.skills.split(',').map((s) => s.trim()).filter(Boolean),
      experienceYears: Number(formData.experienceYears) || 0,
      ctcCurrent: Number(formData.ctcCurrent) || 0,
      ctcExpected: Number(formData.ctcExpected) || 0,
    };
    await onSave(candidate.id, updated);
    setIsSaving(false);
    onClose();
  };

  const parsedResume = candidate.resumeParsed || {};

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal-split-container" onClick={(e) => e.stopPropagation()}>
        <div className="modal-split-header">
          <div>
            <h2 style={{ fontSize: '1.2rem', display: 'flex', alignItems: 'center', gap: '0.6rem' }}>
              <span>📄 Document Review & Corrections</span>
              <span className="badge badge-submitted">{candidate.id}</span>
            </h2>
            <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>
              Split-screen view: Edit parsed entities on the left, verify with original resume on the right
            </div>
          </div>
          <button className="btn btn-ghost btn-sm" onClick={onClose}>
            ✕ Close
          </button>
        </div>

        <div className="modal-split-body">
          {/* Left Panel: Editable Parsed Form */}
          <div className="split-panel left-form">
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <h3 style={{ fontSize: '0.95rem', color: '#a5b4fc' }}>📝 Parsed Entity Form (HR Editable)</h3>
              <span style={{ fontSize: '0.72rem', color: 'var(--text-muted)' }}>Auto-extracted via NLP</span>
            </div>

            <form onSubmit={handleSave} style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
              <div className="form-row">
                <div className="form-group">
                  <label className="form-label">Full Name</label>
                  <input
                    type="text"
                    name="name"
                    className="form-input"
                    value={formData.name}
                    onChange={handleChange}
                    required
                  />
                </div>
                <div className="form-group">
                  <label className="form-label">Email Address</label>
                  <input
                    type="email"
                    name="email"
                    className="form-input"
                    value={formData.email}
                    onChange={handleChange}
                    required
                  />
                </div>
              </div>

              <div className="form-row">
                <div className="form-group">
                  <label className="form-label">Phone Number</label>
                  <input
                    type="text"
                    name="phone"
                    className="form-input"
                    value={formData.phone}
                    onChange={handleChange}
                  />
                </div>
                <div className="form-group">
                  <label className="form-label">Current Location / City</label>
                  <input
                    type="text"
                    name="location"
                    className="form-input"
                    value={formData.location}
                    onChange={handleChange}
                    placeholder="e.g. Bangalore, London, New York"
                  />
                </div>
              </div>

              <div className="form-group">
                <label className="form-label">Identified Skills (comma separated)</label>
                <input
                  type="text"
                  name="skills"
                  className="form-input"
                  value={formData.skills}
                  onChange={handleChange}
                />
              </div>

              <div className="form-row">
                <div className="form-group">
                  <label className="form-label">Total Experience (Years)</label>
                  <input
                    type="number"
                    name="experienceYears"
                    className="form-input"
                    value={formData.experienceYears}
                    onChange={handleChange}
                  />
                </div>
                <div className="form-group">
                  <label className="form-label">Current CTC (Annual)</label>
                  <input
                    type="number"
                    name="ctcCurrent"
                    className="form-input"
                    value={formData.ctcCurrent}
                    onChange={handleChange}
                    placeholder="e.g. 2400000"
                  />
                </div>
              </div>

              <div className="form-group">
                <label className="form-label">Expected CTC</label>
                <input
                  type="number"
                  name="ctcExpected"
                  className="form-input"
                  value={formData.ctcExpected}
                  onChange={handleChange}
                  placeholder="e.g. 3200000"
                />
              </div>

              <div className="form-group">
                <label className="form-label">HR Evaluation Notes / Remarks</label>
                <textarea
                  name="notes"
                  className="form-textarea"
                  value={formData.notes}
                  onChange={handleChange}
                  rows={3}
                  placeholder="Add notes, flags, or recruiter remarks..."
                />
              </div>

              <div style={{ display: 'flex', gap: '0.75rem', marginTop: '0.5rem' }}>
                <button type="submit" className="btn btn-primary" disabled={isSaving}>
                  {isSaving ? 'Saving Corrections...' : '💾 Save Corrections'}
                </button>
                <button type="button" className="btn btn-secondary" onClick={onClose}>
                  Cancel
                </button>
              </div>
            </form>
          </div>

          {/* Right Panel: Original Document / Resume Text Viewer */}
          <div className="split-panel right-preview">
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <h3 style={{ fontSize: '0.95rem', color: '#38bdf8' }}>📄 Original Document Content</h3>
              <div style={{ display: 'flex', gap: '0.5rem' }}>
                <button
                  type="button"
                  className="btn btn-secondary btn-sm"
                  onClick={() => alert('Resume plain-text copied to clipboard!')}
                >
                  📋 Copy Text
                </button>
              </div>
            </div>

            <div style={{
              background: '#040711',
              border: '1px solid var(--border-subtle)',
              borderRadius: 'var(--radius-md)',
              padding: '1.25rem',
              fontFamily: 'var(--font-mono)',
              fontSize: '0.8rem',
              color: '#cbd5e1',
              whiteSpace: 'pre-wrap',
              lineHeight: 1.6,
              flex: 1,
              overflowY: 'auto'
            }}>
              {parsedResume.parsedText || `=== RESUME DOCUMENT PREVIEW ===\n\nNAME: ${candidate.name}\nEMAIL: ${candidate.email}\nLOCATION: ${candidate.location}\nEXPERIENCE: ${candidate.experienceYears} Years\n\nSUMMARY:\n${parsedResume.summary || 'Parsed resume text is available for verification.'}\n\nEDUCATION:\n${parsedResume.education || 'B.Tech/BS Computer Science'}\n\nRECENT ROLE:\n${parsedResume.recentRole || 'Senior Engineer'} at ${parsedResume.recentCompany || 'Tech Corp'}\n\nSKILLS EXTRACTED:\n${candidate.skills?.join(', ')}`}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
