import React from "react";
import { Button, Dropdown, Space, Avatar, Badge, Tooltip } from "antd";
import {
  LayoutDashboard,
  Users,
  FileText,
  Briefcase,
  Calendar,
  LogOut,
  Plus,
  ShieldCheck,
  Building2,
  Layers,
  Mail,
} from "lucide-react";
import { useAuth } from "../contexts/AuthContext";
import { useNavigate } from "react-router-dom";

export function HrNavbar({
  onNewCandidate,
  onOpenBulkUpload,
  onOpenEmailPipeline,
  isSseActive,
  activeTab,
  setActiveTab,
}) {
  const { user, logout } = useAuth();
  const navigate = useNavigate();

  const handleLogout = () => {
    logout();
    navigate("/admin/login");
  };

  const userMenuItems = [
    {
      key: "user-info",
      label: (
        <div style={{ padding: "4px 8px" }}>
          <div style={{ fontWeight: 600, color: "#0f172a" }}>
            {user?.email || "admin@ats-enterprise.io"}
          </div>
          <div style={{ fontSize: 11, color: "#64748b" }}>
            Role: {user?.role || "SUPER_ADMIN"}
          </div>
        </div>
      ),
      disabled: true,
    },
    { type: "divider" },
    {
      key: "logout",
      danger: true,
      icon: <LogOut size={14} />,
      label: "Sign Out",
      onClick: handleLogout,
    },
  ];

  const navItems = [
    { key: "dashboard", label: "Dashboard", icon: <LayoutDashboard size={15} /> },
    { key: "clients", label: "Clients", icon: <Building2 size={15} /> },
    { key: "candidates", label: "Master Database", icon: <Users size={15} /> },
    { key: "applications", label: "Applications", icon: <FileText size={15} /> },
    { key: "jobs", label: "Jobs", icon: <Briefcase size={15} /> },
    { key: "interviews", label: "Interviews", icon: <Calendar size={15} /> },
  ];

  return (
    <header
      style={{
        display: "flex",
        alignItems: "center",
        justifyContent: "space-between",
        padding: "0 24px",
        height: "64px",
        backgroundColor: "#ffffff",
        borderBottom: "1px solid #e2e8f0",
        position: "sticky",
        top: 0,
        zIndex: 100,
        boxShadow: "0 1px 3px rgba(0,0,0,0.03)",
      }}
    >
      {/* Brand Logo & Name */}
      <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
        <div
          style={{
            width: 36,
            height: 36,
            borderRadius: 8,
            background: "linear-gradient(135deg, #4f46e5 0%, #7c3aed 100%)",
            color: "#ffffff",
            fontWeight: 800,
            fontSize: 16,
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            boxShadow: "0 2px 8px rgba(79, 70, 229, 0.3)",
          }}
        >
          ATS
        </div>
        <div>
          <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
            <span style={{ fontWeight: 700, fontSize: 15, color: "#0f172a" }}>
              Enterprise HR
            </span>
            <span
              style={{
                fontSize: 10,
                fontWeight: 700,
                backgroundColor: "#e0e7ff",
                color: "#4338ca",
                padding: "1px 6px",
                borderRadius: 4,
              }}
            >
              ADMIN
            </span>
          </div>
          <div style={{ fontSize: 11, color: "#64748b", lineHeight: 1 }}>
            Talent Acquisition & Intelligence
          </div>
        </div>
      </div>

      {/* Navigation Tabs */}
      <nav style={{ display: "flex", gap: 4, alignItems: "center" }}>
        {navItems.map((item) => {
          const isActive = activeTab === item.key;
          return (
            <button
              key={item.key}
              onClick={() => setActiveTab(item.key)}
              style={{
                display: "flex",
                alignItems: "center",
                gap: 6,
                padding: "8px 14px",
                border: "none",
                borderRadius: 8,
                background: isActive ? "#eff6ff" : "transparent",
                color: isActive ? "#2563eb" : "#475569",
                fontWeight: isActive ? 600 : 500,
                fontSize: 13,
                cursor: "pointer",
                transition: "all 150ms ease",
              }}
            >
              {item.icon}
              <span>{item.label}</span>
            </button>
          );
        })}
      </nav>

      {/* Actions & User Section */}
      <div style={{ display: "flex", alignItems: "center", gap: 14 }}>
        {/* SSE Live Status */}
        <div
          style={{
            display: "flex",
            alignItems: "center",
            gap: 6,
            padding: "4px 10px",
            background: "#f0fdf4",
            border: "1px solid #bbf7d0",
            borderRadius: 16,
            fontSize: 11,
            color: "#166534",
            fontWeight: 500,
          }}
          title="Server-Sent Events Real-Time Sync"
        >
          <span
            style={{
              width: 7,
              height: 7,
              borderRadius: "50%",
              backgroundColor: isSseActive ? "#22c55e" : "#eab308",
              display: "inline-block",
            }}
          />
          <span>{isSseActive ? "Live SSE Active" : "Syncing"}</span>
        </div>

        {/* Email Ingestion Pipeline Button */}
        <Tooltip title="View IMAP email resume pipeline & trigger inbox scan">
          <Button
            icon={<Mail size={14} style={{ marginRight: 2 }} />}
            onClick={onOpenEmailPipeline}
            style={{
              borderRadius: 8,
              fontSize: 13,
              borderColor: "#c7d2fe",
              color: "#4f46e5",
            }}
          >
            Email Pipeline
          </Button>
        </Tooltip>

        {/* Bulk Resume Upload CTA */}
        <Tooltip title="Bulk drag-and-drop multiple candidate resumes (PDF/DOCX)">
          <Button
            icon={<Layers size={14} style={{ marginRight: 2 }} />}
            onClick={onOpenBulkUpload}
            style={{
              borderRadius: 8,
              fontSize: 13,
              borderColor: "#c7d2fe",
              color: "#4f46e5",
            }}
          >
            Bulk Upload
          </Button>
        </Tooltip>

        {/* Ingest Candidate CTA */}
        <Button
          type="primary"
          icon={<Plus size={14} style={{ marginRight: 2 }} />}
          onClick={onNewCandidate}
          style={{
            background: "#4f46e5",
            borderRadius: 8,
            fontWeight: 500,
            fontSize: 13,
            boxShadow: "0 2px 6px rgba(79, 70, 229, 0.25)",
          }}
        >
          Ingest Candidate
        </Button>

        {/* User Profile Dropdown */}
        <Dropdown menu={{ items: userMenuItems }} placement="bottomRight" trigger={["click"]}>
          <div
            style={{
              display: "flex",
              alignItems: "center",
              gap: 8,
              cursor: "pointer",
              padding: "4px 8px",
              borderRadius: 8,
            }}
          >
            <Avatar
              style={{
                backgroundColor: "#4f46e5",
                fontWeight: 600,
                fontSize: 13,
              }}
            >
              {user?.email ? user.email.slice(0, 2).toUpperCase() : "HR"}
            </Avatar>
          </div>
        </Dropdown>
      </div>
    </header>
  );
}
