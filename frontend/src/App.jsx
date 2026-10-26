import React, { useState, useEffect, useCallback } from "react";
import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import { ConfigProvider } from "antd";
import { api } from "./api";
import { AuthProvider } from "./contexts/AuthContext";
import { ProtectedRoute } from "./components/ProtectedRoute";
import { AdminLogin } from "./pages/AdminLogin";
import { ClientLogin } from "./pages/ClientLogin";
import { HrNavbar } from "./components/HrNavbar";
import { ClientNavbar } from "./components/ClientNavbar";
import { DashboardOverview } from "./components/DashboardOverview";
import { HrDashboard } from "./components/HrDashboard";
import { ApplicationsView } from "./components/ApplicationsView";
import { JobsView } from "./components/JobsView";
import { InterviewsView } from "./components/InterviewsView";
import { HrCopilot } from "./components/HrCopilot";
import { CandidateDetailModal } from "./components/CandidateDetailModal";
import { ClientPortal } from "./components/ClientPortal";
import { SplitScreenReview } from "./components/SplitScreenReview";
import { ScheduleModal } from "./components/ScheduleModal";
import { AddCandidateModal } from "./components/AddCandidateModal";
import { ClientsView } from "./components/ClientsView";
import { AssignCandidateModal } from "./components/AssignCandidateModal";

// Enterprise HR Portal View (Master branch capabilities + AI Copilot)
function HrPortalView({
  candidates,
  clients,
  onReviewCandidate,
  onScheduleInterview,
  onSendToClient,
  onOpenAssignModal,
  onCreateClient,
  onUpdateClient,
  onDeleteClient,
  onInviteClient,
  onToggleBlacklist,
  onResetData,
  onOpenAddModal,
  isSseActive,
  lastSseEvent,
}) {
  const [activeTab, setActiveTab] = useState("dashboard");
  const [selectedCandidate, setSelectedCandidate] = useState(null);

  return (
    <div style={{ minHeight: "100vh", backgroundColor: "#f8fafc" }}>
      {/* Enterprise Ant Design Navigation Header */}
      <HrNavbar
        onNewCandidate={onOpenAddModal}
        isSseActive={isSseActive}
        activeTab={activeTab}
        setActiveTab={setActiveTab}
      />

      {/* SSE Real-Time Stream Ticker */}
      <div className="notification-ticker">
        <div style={{ display: "flex", alignItems: "center", gap: "0.65rem" }}>
          <span style={{ color: "#818cf8", fontWeight: "700" }}>
            [LIVE SSE STREAM]
          </span>
          <span>
            {lastSseEvent ||
              "Connected to real-time event stream. Listening for candidate applications & FSM transitions..."}
          </span>
        </div>
        <div style={{ fontSize: "0.72rem", color: "var(--text-muted)" }}>
          Simplex SSE Active • Port 8080
        </div>
      </div>

      {/* Main Tab Content */}
      <main style={{ maxWidth: 1400, margin: "0 auto", padding: "20px 24px 60px 24px" }}>
        {activeTab === "dashboard" && (
          <DashboardOverview
            candidates={candidates}
            onNavigateTab={setActiveTab}
            onOpenAddModal={onOpenAddModal}
          />
        )}

        {activeTab === "clients" && (
          <ClientsView
            clients={clients}
            candidates={candidates}
            onCreateClient={onCreateClient}
            onUpdateClient={onUpdateClient}
            onDeleteClient={onDeleteClient}
            onInviteClient={onInviteClient}
            onOpenAssignModal={onOpenAssignModal}
            onSelectCandidate={(c) => setSelectedCandidate(c)}
          />
        )}

        {activeTab === "candidates" && (
          <HrDashboard
            candidates={candidates}
            clients={clients}
            onReviewCandidate={onReviewCandidate}
            onScheduleInterview={onScheduleInterview}
            onSendToClient={onSendToClient}
            onOpenAssignModal={onOpenAssignModal}
            onToggleBlacklist={onToggleBlacklist}
            onResetData={onResetData}
            onSelectCandidate={(c) => setSelectedCandidate(c)}
          />
        )}

        {activeTab === "applications" && (
          <ApplicationsView
            candidates={candidates}
            onSelectCandidate={(c) => setSelectedCandidate(c)}
          />
        )}

        {activeTab === "jobs" && <JobsView />}

        {activeTab === "interviews" && (
          <InterviewsView
            candidates={candidates}
            onScheduleInterview={onScheduleInterview}
            onSelectCandidate={(c) => setSelectedCandidate(c)}
          />
        )}
      </main>

      {/* HR Copilot Floating AI Assistant */}
      <HrCopilot candidates={candidates} />

      {/* Candidate Profile Details Modal */}
      <CandidateDetailModal
        candidate={selectedCandidate}
        visible={!!selectedCandidate}
        onClose={() => setSelectedCandidate(null)}
        onReviewCandidate={onReviewCandidate}
        onScheduleInterview={onScheduleInterview}
        onSendToClient={onSendToClient}
        onOpenAssignModal={onOpenAssignModal}
      />
    </div>
  );
}

// Dedicated Client Portal View
function ClientPortalView({
  candidates,
  onTransitionStatus,
  onReviewCandidate,
  onAddJob,
}) {
  const [isRequestRoleOpen, setIsRequestRoleOpen] = useState(false);

  return (
    <div>
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
  const [clients, setClients] = useState([]);
  const [loading, setLoading] = useState(true);

  // Modals
  const [reviewingCandidate, setReviewingCandidate] = useState(null);
  const [schedulingCandidate, setSchedulingCandidate] = useState(null);
  const [assigningCandidate, setAssigningCandidate] = useState(null);
  const [isAddModalOpen, setIsAddModalOpen] = useState(false);

  // Notifications & Realtime SSE
  const [toasts, setToasts] = useState([]);
  const [lastSseEvent, setLastSseEvent] = useState(null);
  const [isSseActive, setIsSseActive] = useState(true);

  const showToast = useCallback((message, type = "info") => {
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
      console.error("Failed to load candidates:", err);
    } finally {
      setLoading(false);
    }
  }, []);

  // Fetch clients on load
  const loadClients = useCallback(async () => {
    try {
      const data = await api.getClients();
      setClients(data);
    } catch (err) {
      console.error("Failed to load clients:", err);
    }
  }, []);

  useEffect(() => {
    loadCandidates();
    loadClients();
  }, [loadCandidates, loadClients]);

  // Simulated SSE Heartbeat & Live Client Updates Ticker
  useEffect(() => {
    const timer = setInterval(() => {
      const events = [
        {
          type: "HEARTBEAT",
          text: "SSE connection active • Tenant isolation verified",
        },
        {
          type: "CANDIDATE_INGESTED",
          text: "SendGrid Webhook parsed new resume attachment",
        },
        {
          type: "FSM_SYNC",
          text: "Client reviewed submitted candidate profile",
        },
      ];
      const ev = events[Math.floor(Math.random() * events.length)];
      setLastSseEvent(ev.text);
    }, 20000);

    return () => clearInterval(timer);
  }, []);

  // Handle Split Screen Correction Save
  const handleSaveCorrections = async (candidateId, updatedData) => {
    const res = await api.updateCandidate(candidateId, updatedData);
    setCandidates((prev) =>
      prev.map((c) => (c.id === candidateId ? { ...c, ...res } : c))
    );
    showToast(`Saved corrections for ${updatedData.name}`, "success");
  };

  // Handle Interview Schedule
  const handleScheduleInterview = async (candidateId, interviewData) => {
    const updated = await api.transitionStatus(
      candidateId,
      "interview_scheduled",
      interviewData
    );
    setCandidates((prev) =>
      prev.map((c) => (c.id === candidateId ? updated : c))
    );
    showToast(
      `Interview scheduled for ${updated.name} on ${new Date(
        interviewData.interviewDate
      ).toLocaleDateString()}`,
      "success"
    );
  };

  // Handle Client / HR Status Transition
  const handleTransitionStatus = async (
    candidateId,
    newStatus,
    payload = {}
  ) => {
    const updated = await api.transitionStatus(candidateId, newStatus, payload);
    setCandidates((prev) =>
      prev.map((c) => (c.id === candidateId ? updated : c))
    );

    if (newStatus === "left_company") {
      showToast(
        `⚠️ Candidate ${updated.name} quarantined. Excluded from master talent pool!`,
        "error"
      );
    } else {
      showToast(
        `Status updated to "${newStatus.replace("_", " ").toUpperCase()}" for ${updated.name}`,
        "success"
      );
    }
  };

  // Handle Send Profile to Client
  const handleSendToClient = async (candidateId) => {
    const cand = candidates.find((c) => c.id === candidateId);
    if (cand) {
      setAssigningCandidate(cand);
    } else {
      const updated = await api.transitionStatus(candidateId, "submitted");
      setCandidates((prev) =>
        prev.map((c) => (c.id === candidateId ? updated : c))
      );
      showToast(
        `Profile for ${updated.name} submitted to Client Portal Kanban!`,
        "info"
      );
    }
  };

  // Handle Assign Candidate to Client
  const handleAssignCandidate = async (candidateId, clientId, clientName, notes, targetRole) => {
    const updated = await api.assignCandidateToClient(candidateId, clientId, clientName, notes);
    setCandidates((prev) =>
      prev.map((c) =>
        c.id === candidateId
          ? {
              ...c,
              ...updated,
              clientId,
              clientName,
              selectedClientName: clientName,
              currentStatus: "submitted",
            }
          : c
      )
    );

    // Refresh clients with updated counts
    const freshClients = await api.getClients();
    setClients(freshClients);

    showToast(
      `Candidate profile successfully assigned to ${clientName} and submitted to Client Portal!`,
      "success"
    );
  };

  // Handle Create Client Organization
  const handleCreateClient = async (clientData) => {
    const created = await api.createClient(clientData);
    setClients((prev) => [created, ...prev]);
    showToast(`Client organization "${created.name}" provisioned successfully!`, "success");
    return created;
  };

  // Handle Update Client Organization
  const handleUpdateClient = async (clientId, clientData) => {
    const updated = await api.updateClient(clientId, clientData);
    setClients((prev) =>
      prev.map((c) => (c.id === clientId ? { ...c, ...updated } : c))
    );
    showToast(`Client "${updated.name}" updated.`, "success");
    return updated;
  };

  // Handle Delete Client Organization
  const handleDeleteClient = async (clientId) => {
    await api.deleteClient(clientId);
    setClients((prev) => prev.filter((c) => c.id !== clientId));
    showToast("Client organization deleted.", "info");
  };

  // Handle Invite Client Admin
  const handleInviteClient = async (clientId) => {
    return await api.inviteClientUser(clientId);
  };

  // Handle Add Candidate
  const handleAddCandidate = async (newCand) => {
    const created = await api.addCandidate(newCand);
    setCandidates((prev) => [created, ...prev]);
    const freshClients = await api.getClients();
    setClients(freshClients);
    showToast(`Candidate ${created.name} ingested successfully!`, "success");
  };

  // Handle Reset Demo Data
  const handleResetData = () => {
    const fresh = api.resetDemoData();
    setCandidates(fresh);
    api.getClients().then(setClients);
    showToast("Candidate and client databases reset to defaults.", "info");
  };

  // Handle Job Post from Client
  const handleAddJob = (job) => {
    showToast(
      `New job requisition posted: "${job.title}". HR notified.`,
      "success"
    );
  };

  if (loading) {
    return (
      <div
        style={{
          display: "flex",
          justifyContent: "center",
          alignItems: "center",
          height: "100vh",
          backgroundColor: "#f8fafc",
          color: "#64748b",
          fontSize: 15,
        }}
      >
        Loading ATS Enterprise Portal...
      </div>
    );
  }

  return (
    <ConfigProvider
      theme={{
        token: {
          colorPrimary: "#4f46e5",
          borderRadius: 8,
          fontFamily: "'Inter', -apple-system, BlinkMacSystemFont, sans-serif",
        },
      }}
    >
      <BrowserRouter>
        <AuthProvider>
          {/* Route Definitions */}
          <Routes>
            <Route path="/admin/login" element={<AdminLogin />} />
            <Route path="/client/login" element={<ClientLogin />} />

            {/* HR Power Dashboard (Protected - Admin Only) */}
            <Route
              path="/hr/dashboard"
              element={
                <ProtectedRoute requireAdmin>
                  <HrPortalView
                    candidates={candidates}
                    clients={clients}
                    onReviewCandidate={(c) => setReviewingCandidate(c)}
                    onScheduleInterview={(c) => setSchedulingCandidate(c)}
                    onSendToClient={handleSendToClient}
                    onOpenAssignModal={(c) => setAssigningCandidate(c)}
                    onCreateClient={handleCreateClient}
                    onUpdateClient={handleUpdateClient}
                    onDeleteClient={handleDeleteClient}
                    onInviteClient={handleInviteClient}
                    onToggleBlacklist={(id) =>
                      handleTransitionStatus(id, "left_company")
                    }
                    onResetData={handleResetData}
                    onOpenAddModal={() => setIsAddModalOpen(true)}
                    isSseActive={isSseActive}
                    lastSseEvent={lastSseEvent}
                  />
                </ProtectedRoute>
              }
            />

            {/* Client Portal (Protected - Client Only) */}
            <Route
              path="/portal/dashboard"
              element={
                <ProtectedRoute requireClient>
                  <ClientPortalView
                    candidates={candidates}
                    onTransitionStatus={handleTransitionStatus}
                    onReviewCandidate={(c) => setReviewingCandidate(c)}
                    onAddJob={handleAddJob}
                  />
                </ProtectedRoute>
              }
            />

            {/* Redirects */}
            <Route path="/" element={<Navigate to="/admin/login" replace />} />
            <Route path="/admin" element={<Navigate to="/hr/dashboard" replace />} />
            <Route path="/admin/*" element={<Navigate to="/hr/dashboard" replace />} />
            <Route path="/hr" element={<Navigate to="/hr/dashboard" replace />} />
            <Route path="/hr/*" element={<Navigate to="/hr/dashboard" replace />} />
            <Route path="/portal" element={<Navigate to="/portal/dashboard" replace />} />
            <Route path="/portal/*" element={<Navigate to="/portal/dashboard" replace />} />
            <Route path="/client" element={<Navigate to="/client/login" replace />} />
            <Route path="/client/*" element={<Navigate to="/client/login" replace />} />
            <Route path="*" element={<Navigate to="/admin/login" replace />} />
          </Routes>

          {/* Split-Screen Resume Review Modal */}
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

          {/* Assign Candidate to Client Modal */}
          {assigningCandidate && (
            <AssignCandidateModal
              visible={!!assigningCandidate}
              candidate={assigningCandidate}
              clients={clients}
              onClose={() => setAssigningCandidate(null)}
              onAssign={handleAssignCandidate}
            />
          )}

          {/* Add Candidate Modal */}
          {isAddModalOpen && (
            <AddCandidateModal
              clients={clients}
              onClose={() => setIsAddModalOpen(false)}
              onAdd={handleAddCandidate}
            />
          )}

          {/* Toast Notification Container */}
          <div className="toast-container">
            {toasts.map((t) => (
              <div key={t.id} className={`toast toast-${t.type}`}>
                <span>
                  {t.type === "error" ? "🛑" : t.type === "success" ? "✅" : "ℹ️"}
                </span>
                <span>{t.message}</span>
              </div>
            ))}
          </div>
        </AuthProvider>
      </BrowserRouter>
    </ConfigProvider>
  );
}
