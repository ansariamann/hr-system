import React, { useState, useEffect, useCallback } from 'react';
import { BrowserRouter, Routes, Route, Navigate, useLocation } from 'react-router-dom';
import { api } from './api';
import { HrNavbar } from './components/HrNavbar';
import { ClientNavbar } from './components/ClientNavbar';
import { HrDashboard } from './components/HrDashboard';
import { ClientPortal } from './components/ClientPortal';
import { SplitScreenReview } from './components/SplitScreenReview';
import { ScheduleModal } from './components/ScheduleModal';
import { AddCandidateModal } from './components/AddCandidateModal';

// Dedicated HR Power Portal View
function HrPortalView({
  candidates,
  onReviewCandidate,
  onScheduleInterview,
  onSendToClient,
  onToggleBlacklist,
  onResetData,
  onOpenAddModal,
  isSseActive,
  lastSseEvent,
}) {
  const [activeTab, setActiveTab] = useState('candidates');

  return (
    <div>
      {/* Dedicated HR Navbar (No Client Portal Switcher) */}
      <HrNavbar
        onNewCandidate={onOpenAddModal}
        isSseActive={isSseActive}
        activeTab={activeTab}
        setActiveTab={setActiveTab}
      />

      {/* SSE Live Event Stream Ticker for HR Admins */}
      <div className="notification-ticker">
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.65rem' }}>
          <span style={{ color: '#818cf8', fontWeight: '700' }}>[HR STREAM]</span>
          <span>{lastSseEvent || 'Listening for live candidate applications & client review actions...'}</span>
        </div>
        <div style={{ fontSize: '0.72rem', color: 'var(--text-muted)' }}>
          HTTP/2 Simplex SSE Active
        </div>
      </div>

      <main className="main-content">
        <HrDashboard
          candidates={candidates}
          onReviewCandidate={onReviewCandidate}
          onScheduleInterview={onScheduleInterview}
          onSendToClient={onSendToClient}
          onToggleBlacklist={onToggleBlacklist}
          onResetData={onResetData}
        />
      </main>
    </div>
  );
}

// Dedicated Client Portal View (External Client Isolation)
function ClientPortalView({
  candidates,
  onTransitionStatus,
  onReviewCandidate,
  onAddJob,
}) {
  const [isRequestRoleOpen, setIsRequestRoleOpen] = useState(false);

  return (
    <div>
      {/* Dedicated Client Navbar (No HR Switcher) */}
      <ClientNavbar onRequestRole={() => setIsRequestRoleOpen(true)} />

      <main className="main-content">
        <ClientPortal
          candidates={candidates}
          onTransitionStatus={onTransitionStatus}
          onReviewCandidate={onReviewCandidate}
          onAddJob={onAddJob}
          requestRoleOpen={isRequestRoleOpen}
          onRequestRoleClose={() => setIsRequestRoleOpen(false)}
        />
      </main>
    </div>
  );
}

// Root Application Controller
export default function App() {
  const [candidates, setCandidates] = useState([]);
  const [loading, setLoading] = useState(true);

  // Modals
  const [reviewingCandidate, setReviewingCandidate] = useState(null);
  const [schedulingCandidate, setSchedulingCandidate] = useState(null);
  const [isAddModalOpen, setIsAddModalOpen] = useState(false);

  // Notifications & Realtime SSE
  const [toasts, setToasts] = useState([]);
  const [lastSseEvent, setLastSseEvent] = useState(null);
  const [isSseActive, setIsSseActive] = useState(true);

  const showToast = useCallback((message, type = 'info') => {
    const id = Date.now();
    setToasts((prev) => [...prev, { id, message, type }]);
    setTimeout(() => {
      setToasts((prev) => prev.filter((t) => t.id !== id));
    }, 4500);
  }, []);

  // Fetch candidates on load
  const loadCandidates = useCallback(async () => {
    setLoading(true);
    try {
      const data = await api.getCandidates({ excludeLeavers: false });
      setCandidates(data);
    } catch (err) {
      console.error('Failed to load candidates:', err);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadCandidates();
  }, [loadCandidates]);

  // Simulated SSE Heartbeat & Live Client Updates Ticker
  useEffect(() => {
    const timer = setInterval(() => {
      const events = [
        { type: 'HEARTBEAT', text: 'SSE connection active • Tenant isolation verified' },
        { type: 'CANDIDATE_INGESTED', text: 'SendGrid Webhook parsed new resume attachment' },
        { type: 'FSM_SYNC', text: 'Client Acme Corp reviewed submitted candidate' },
      ];
      const ev = events[Math.floor(Math.random() * events.length)];
      setLastSseEvent(ev.text);
    }, 20000);

    return () => clearInterval(timer);
  }, []);

  // Handle Split Screen Correction Save
  const handleSaveCorrections = async (candidateId, updatedData) => {
    const res = await api.updateCandidate(candidateId, updatedData);
    setCandidates((prev) => prev.map((c) => (c.id === candidateId ? { ...c, ...res } : c)));
    showToast(`Saved corrections for ${updatedData.name}`, 'success');
  };

  // Handle Interview Schedule
  const handleScheduleInterview = async (candidateId, interviewData) => {
    const updated = await api.transitionStatus(candidateId, 'interview_scheduled', interviewData);
    setCandidates((prev) => prev.map((c) => (c.id === candidateId ? updated : c)));
    showToast(`Interview scheduled for ${updated.name} on ${new Date(interviewData.interviewDate).toLocaleDateString()}`, 'success');
  };

  // Handle Client / HR Status Transition
  const handleTransitionStatus = async (candidateId, newStatus, payload = {}) => {
    const updated = await api.transitionStatus(candidateId, newStatus, payload);
    setCandidates((prev) => prev.map((c) => (c.id === candidateId ? updated : c)));

    if (newStatus === 'left_company') {
      showToast(`⚠️ Candidate ${updated.name} terminated. Excluded from master talent pool!`, 'error');
    } else {
      showToast(`Status updated to "${newStatus.replace('_', ' ').toUpperCase()}" for ${updated.name}`, 'success');
    }
  };

  // Handle Send Profile to Client
  const handleSendToClient = async (candidateId) => {
    const updated = await api.transitionStatus(candidateId, 'submitted');
    setCandidates((prev) => prev.map((c) => (c.id === candidateId ? updated : c)));
    showToast(`Profile for ${updated.name} submitted to Client Portal Kanban!`, 'info');
  };

  // Handle Add Candidate
  const handleAddCandidate = async (newCand) => {
    const created = await api.addCandidate(newCand);
    setCandidates((prev) => [created, ...prev]);
    showToast(`Candidate ${created.name} ingested successfully!`, 'success');
  };

  // Handle Reset Demo Data
  const handleResetData = () => {
    const fresh = api.resetDemoData();
    setCandidates(fresh);
    showToast('Demo candidate database reset to blueprint defaults.', 'info');
  };

  // Handle Job Post from Client
  const handleAddJob = (job) => {
    showToast(`New job requisition posted: "${job.title}". HR notified.`, 'success');
  };

  if (loading) {
    return (
      <div style={{ textAlign: 'center', padding: '5rem', color: 'var(--text-muted)' }}>
        Loading ATS Enterprise records...
      </div>
    );
  }

  return (
    <BrowserRouter>
      {/* Route Definitions: Fully Separate Portals */}
      <Routes>
        {/* HR Power Dashboard (Internal Recruiters Only) */}
        <Route
          path="/"
          element={
            <HrPortalView
              candidates={candidates}
              onReviewCandidate={(c) => setReviewingCandidate(c)}
              onScheduleInterview={(c) => setSchedulingCandidate(c)}
              onSendToClient={handleSendToClient}
              onToggleBlacklist={(id) => handleTransitionStatus(id, 'left_company')}
              onResetData={handleResetData}
              onOpenAddModal={() => setIsAddModalOpen(true)}
              isSseActive={isSseActive}
              lastSseEvent={lastSseEvent}
            />
          }
        />
        <Route
          path="/hr/*"
          element={
            <Navigate to="/" replace />
          }
        />

        {/* Client Portal (External Clients Only - No HR Switcher) */}
        <Route
          path="/portal"
          element={
            <ClientPortalView
              candidates={candidates}
              onTransitionStatus={handleTransitionStatus}
              onReviewCandidate={(c) => setReviewingCandidate(c)}
              onAddJob={handleAddJob}
            />
          }
        />
        <Route
          path="/client/*"
          element={
            <Navigate to="/portal" replace />
          }
        />

        {/* Catch-all redirect to HR Dashboard */}
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>

      {/* Split-Screen Document & Parsed Form Review Modal */}
      {reviewingCandidate && (
        <SplitScreenReview
          candidate={reviewingCandidate}
          onClose={() => setReviewingCandidate(null)}
          onSave={handleSaveCorrections}
        />
      )}

      {/* Schedule Interview Modal */}
      {schedulingCandidate && (
        <ScheduleModal
          candidate={schedulingCandidate}
          onClose={() => setSchedulingCandidate(null)}
          onSchedule={handleScheduleInterview}
        />
      )}

      {/* Add Candidate Modal */}
      {isAddModalOpen && (
        <AddCandidateModal
          onClose={() => setIsAddModalOpen(false)}
          onAdd={handleAddCandidate}
        />
      )}

      {/* Toast Notification Container */}
      <div className="toast-container">
        {toasts.map((t) => (
          <div key={t.id} className={`toast toast-${t.type}`}>
            <span>{t.type === 'error' ? '🛑' : t.type === 'success' ? '✅' : 'ℹ️'}</span>
            <span>{t.message}</span>
          </div>
        ))}
      </div>
    </BrowserRouter>
  );
}
