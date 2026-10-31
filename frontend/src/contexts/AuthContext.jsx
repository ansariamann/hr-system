import React, { createContext, useContext, useState, useEffect, useCallback } from "react";
import { api, authApi, clearAuthToken, getAuthToken, ApiError } from "../api";

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);

  const logout = useCallback(() => {
    clearAuthToken();
    if (typeof window !== "undefined") {
      localStorage.removeItem("user");
      // Remove any leftover keys
      localStorage.removeItem("accessToken");
      localStorage.removeItem("ats_candidates_db");
      localStorage.removeItem("ats_clients_db");
      localStorage.removeItem("ats_jobs_db");
    }
    setUser(null);
  }, []);

  // Listen to 401 unauthorized events from api.js
  useEffect(() => {
    const handleUnauthorized = () => {
      logout();
    };
    window.addEventListener("ats:unauthorized", handleUnauthorized);
    return () => {
      window.removeEventListener("ats:unauthorized", handleUnauthorized);
    };
  }, [logout]);

  // Verify session on mount with /auth/me
  useEffect(() => {
    let isMounted = true;
    async function initAuth() {
      const token = getAuthToken();
      if (!token) {
        if (isMounted) setLoading(false);
        return;
      }

      try {
        const me = await authApi.me();
        if (me && isMounted) {
          const roleUpper = (me.role || "").toUpperCase();
          const userType = roleUpper.includes("CLIENT") ? "client" : "admin";
          const verifiedUser = {
            id: me.id,
            email: me.email,
            name: me.name,
            role: roleUpper,
            clientId: me.clientId,
            userType,
          };
          setUser(verifiedUser);
          localStorage.setItem("user", JSON.stringify(verifiedUser));
        } else if (isMounted) {
          logout();
        }
      } catch (err) {
        console.warn("Failed to verify existing session:", err.message);
        if (isMounted) {
          logout();
        }
      } finally {
        if (isMounted) {
          setLoading(false);
        }
      }
    }

    initAuth();
    return () => {
      isMounted = false;
    };
  }, [logout]);

  const login = async (email, password) => {
    try {
      // 1. Authenticate with backend and receive JWT
      const loginRes = await api.login(email, password);
      if (!loginRes || !loginRes.token) {
        return { success: false, error: "No token returned by server" };
      }

      // 2. Fetch authoritative profile from /auth/me
      let me;
      try {
        me = await authApi.me();
      } catch (meErr) {
        console.warn("Could not fetch /auth/me after login:", meErr);
        me = {
          id: loginRes.userId,
          email: loginRes.email || email,
          role: loginRes.role,
        };
      }

      const roleUpper = ((me && me.role) || loginRes.role || "").toUpperCase();
      const userType = roleUpper.includes("CLIENT") ? "client" : "admin";

      const verifiedUser = {
        id: (me && me.id) || loginRes.userId,
        email: (me && me.email) || email,
        name: (me && me.name) || email,
        role: roleUpper,
        clientId: me && me.clientId,
        userType,
      };

      setUser(verifiedUser);
      localStorage.setItem("user", JSON.stringify(verifiedUser));

      return { success: true, user: verifiedUser };
    } catch (error) {
      console.error("Login failed:", error);
      return {
        success: false,
        error: error instanceof ApiError ? error.message : (error.message || "Invalid credentials"),
      };
    }
  };

  const value = {
    user,
    login,
    logout,
    loading,
    isAuthenticated: !!user,
    isAdmin: user?.userType === "admin",
    isClient: user?.userType === "client",
    role: user?.role || null,
  };

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error("useAuth must be used within an AuthProvider");
  }
  return context;
}
