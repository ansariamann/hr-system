import React, { useState } from 'react';
import { Upload, FileText, CheckCircle2, Loader2 } from 'lucide-react';
import { api } from '../api';

export function AddCandidateModal({ onClose, onAdd, clients = [] }) {
  const [formData, setFormData] = useState({
    name: '',
    email: '',
    phone: '',
    location: 'Bangalore',
    clientId: '',
    clientName: '',
    skills: 'Java, Spring Boot, React',
    experienceYears: 4,
    ctcCurrent: 1500000,
    ctcExpected: 2200000,
    notes: 'Ingested candidate via HR direct input.',
    resumeText: '',
  });

  const [uploading, setUploading] = useState(false);
  const [uploadedFileName, setUploadedFileName] = useState('');

  const handleFileUpload = async (e) => {
    const file = e.target.files?.[0];
    if (!file) return;

    setUploading(true);
    setUploadedFileName(file.name);
    try {
      const candidate = await api.uploadResume(file, formData.clientId);
      if (candidate) {
        setFormData((prev) => ({
          ...prev,
          name: candidate.name || prev.name,
          email: candidate.email || prev.email,
          phone: candidate.phone || prev.phone,
          location: candidate.location || prev.location,
          skills: Array.isArray(candidate.skills) ? candidate.skills.join(', ') : (candidate.skills || prev.skills),
          experienceYears: candidate.experienceYears || prev.experienceYears,
          resumeText: candidate.resumeParsed?.parsedText || candidate.notes || prev.resumeText,
          notes: `Parsed resume document: ${file.name}`,
        }));
      }
    } catch (err) {
      console.error("Resume file parse error:", err);
    } finally {
      setUploading(false);
    }
  };

  const handleChange = (e) => {
    const { name, value } = e.target;
    if (name === 'clientId') {
      const selected = clients.find((c) => c.id === value);
      setFormData((prev) => ({
        ...prev,
        clientId: value,
        clientName: selected ? selected.name : '',
      }));
    } else {
      setFormData((prev) => ({ ...prev, [name]: value }));
    }
  };

  const handleSubmit = (e) => {
    e.preventDefault();
    onAdd({
      ...formData,
      skills: typeof formData.skills === 'string'
        ? formData.skills.split(',').map((s) => s.trim()).filter(Boolean)
        : formData.skills,
      experienceYears: Number(formData.experienceYears) || 0,
      ctcCurrent: Number(formData.ctcCurrent) || 0,
      ctcExpected: Number(formData.ctcExpected) || 0,
      selectedClientName: formData.clientName,
      resumeParsed: {
        summary: `Candidate profile for ${formData.name}`,
        parsedText: formData.resumeText || `RESUME: ${formData.name}\nEmail: ${formData.email}\nSkills: ${formData.skills}`,
      },
    });
    onClose();
  };

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div
        className="card"
        style={{ width: '90%', maxWidth: '640px', maxHeight: '90vh', overflowY: 'auto' }}
        onClick={(e) => e.stopPropagation()}
      >
        <div className="card-header">
          <h2 style={{ fontSize: '1.15rem' }}>✨ Ingest New Candidate</h2>
          <button className="btn btn-ghost btn-sm" onClick={onClose}>✕</button>
        </div>

        <form onSubmit={handleSubmit} style={{ padding: '1.5rem', display: 'flex', flexDirection: 'column', gap: '1rem' }}>
          {/* Resume Upload Dropzone */}
          <div
            style={{
              border: '2px dashed #cbd5e1',
              borderRadius: 8,
              padding: '16px',
              textAlign: 'center',
              background: '#f8fafc',
              cursor: 'pointer',
              position: 'relative',
            }}
          >
            <input
              type="file"
              accept=".pdf,.doc,.docx,.txt"
              onChange={handleFileUpload}
              style={{
                position: 'absolute',
                top: 0,
                left: 0,
                width: '100%',
                height: '100%',
                opacity: 0,
                cursor: 'pointer',
              }}
            />
            {uploading ? (
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 8, color: '#4f46e5' }}>
                <Loader2 size={20} className="animate-spin" />
                <span>Extracting resume text & auto-populating fields...</span>
              </div>
            ) : uploadedFileName ? (
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 8, color: '#16a34a' }}>
                <CheckCircle2 size={20} />
                <span>Loaded <strong>{uploadedFileName}</strong> (Fields auto-populated below)</span>
              </div>
            ) : (
              <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 4, color: '#64748b' }}>
                <Upload size={24} color="#6366f1" />
                <span style={{ fontSize: 13, fontWeight: 600, color: '#334155' }}>
                  Click or drag resume (PDF, DOCX) to auto-fill candidate details
                </span>
                <span style={{ fontSize: 11, color: '#94a3b8' }}>
                  Instant text extraction via Apache PDFBox / OCR
                </span>
              </div>
            )}
          </div>

          <div className="form-row">
            <div className="form-group">
              <label className="form-label">Full Name *</label>
              <input type="text" name="name" className="form-input" value={formData.name} onChange={handleChange} required />
            </div>
            <div className="form-group">
              <label className="form-label">Email Address *</label>
              <input type="email" name="email" className="form-input" value={formData.email} onChange={handleChange} required />
            </div>
          </div>

          <div className="form-row">
            <div className="form-group">
              <label className="form-label">Phone</label>
              <input type="text" name="phone" className="form-input" value={formData.phone} onChange={handleChange} />
            </div>
            <div className="form-group">
              <label className="form-label">City / Location</label>
              <input type="text" name="location" className="form-input" value={formData.location} onChange={handleChange} />
            </div>
          </div>

          <div className="form-group">
            <label className="form-label">Assign to Client Organization (Optional)</label>
            <select
              name="clientId"
              className="form-input"
              value={formData.clientId}
              onChange={handleChange}
            >
              <option value="">-- No Client (Pool / General Database) --</option>
              {clients.map((c) => (
                <option key={c.id} value={c.id}>
                  {c.name} ({c.industry || "General"})
                </option>
              ))}
            </select>
          </div>

          <div className="form-group">
            <label className="form-label">Skills (Comma-separated)</label>
            <input type="text" name="skills" className="form-input" value={formData.skills} onChange={handleChange} />
          </div>

          <div className="form-row">
            <div className="form-group">
              <label className="form-label">Experience (Years)</label>
              <input type="number" name="experienceYears" className="form-input" value={formData.experienceYears} onChange={handleChange} />
            </div>
            <div className="form-group">
              <label className="form-label">Current CTC</label>
              <input type="number" name="ctcCurrent" className="form-input" value={formData.ctcCurrent} onChange={handleChange} />
            </div>
          </div>

          <div className="form-group">
            <label className="form-label">Raw Resume Text / Summary</label>
            <textarea
              name="resumeText"
              className="form-textarea"
              placeholder="Paste raw resume text or candidate bio..."
              value={formData.resumeText}
              onChange={handleChange}
              rows={3}
            />
          </div>

          <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '0.75rem', marginTop: '0.5rem' }}>
            <button type="button" className="btn btn-secondary" onClick={onClose}>Cancel</button>
            <button type="submit" className="btn btn-primary">Ingest Profile</button>
          </div>
        </form>
      </div>
    </div>
  );
}
