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
    // Not logged in - redirect to appropriate login page
    if (requireAdmin) {
      return <Navigate to="/admin/login" replace />;
    }
    if (requireClient) {
      return <Navigate to="/client/login" replace />;
    }
    return <Navigate to="/admin/login" replace />;
  }

  // Check role-based access
  if (requireAdmin && user.userType !== "admin") {
    return <Navigate to="/client/login" replace />;
  }

  if (requireClient && user.userType !== "client") {
    return <Navigate to="/admin/login" replace />;
  }

  return children;
}
