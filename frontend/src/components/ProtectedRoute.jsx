import React from "react";
import { Navigate } from "react-router-dom";
import { useAuth } from "../contexts/AuthContext";

export function ProtectedRoute({
  children,
  requireAdmin = false,
  requireClient = false,
}) {
  const { user, loading } = useAuth();

  if (loading) {
    return (
      <div
        style={{
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          minHeight: "100vh",
          color: "var(--text-muted)",
        }}
      >
        <div style={{ textAlign: "center" }}>
          <div style={{ fontSize: "1.5rem", marginBottom: "1rem" }}>🔐</div>
          <div>Verifying authentication...</div>
        </div>
      </div>
    );
  }

  if (!user) {
    if (requireAdmin) {
      return <Navigate to="/admin/login" replace />;
    }
    if (requireClient) {
      return <Navigate to="/client/login" replace />;
    }
    return <Navigate to="/admin/login" replace />;
  }

  // Check role-based access based on server-verified role
  const roleUpper = (user.role || "").toUpperCase();
  const isClientRole = roleUpper.includes("CLIENT");
  const isAdminRole = !isClientRole;

  if (requireAdmin && !isAdminRole) {
    // Client role user attempted to access Admin dashboard -> redirect to client portal
    return <Navigate to="/portal/dashboard" replace />;
  }

  if (requireClient && !isClientRole) {
    // Admin/HR role user attempted to access Client portal -> redirect to HR dashboard
    return <Navigate to="/hr/dashboard" replace />;
  }

  return children;
}
