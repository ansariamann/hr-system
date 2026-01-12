import type { AuthProvider } from "@refinedev/core";
import { apiClient } from "../../shared/api/client";

export const authProvider: AuthProvider = {
    login: async ({ email, password }) => {
        try {
            const { data } = await apiClient.post("/auth/login", new URLSearchParams({
                username: email,
                password: password,
            }), {
                headers: {
                    "Content-Type": "application/x-www-form-urlencoded"
                }
            });

            if (data.access_token) {
                localStorage.setItem("hr_token", data.access_token);
                return {
                    success: true,
                    redirectTo: "/",
                };
            }

            return {
                success: false,
                error: {
                    name: "LoginError",
                    message: "Invalid credentials",
                },
            };
        } catch (error: any) {
            console.error("Login failed:", error);
            let detail = error.response?.data?.error?.message || error.response?.data?.detail || error.message;
            if (typeof detail === 'object') {
                detail = JSON.stringify(detail);
            }
            return {
                success: false,
                error: {
                    name: "LoginError",
                    message: detail || "Invalid email or password",
                },
            };
        }
    },
    logout: async () => {
        localStorage.removeItem("hr_token");
        return {
            success: true,
            redirectTo: "/login",
        };
    },
    check: async () => {
        const token = localStorage.getItem("hr_token");
        if (token) {
            return {
                authenticated: true,
            };
        }

        return {
            authenticated: false,
            redirectTo: "/login",
        };
    },
    getPermissions: async () => null,
    getIdentity: async () => {
        const token = localStorage.getItem("hr_token");
        if (!token) return null;

        if (token === "dev_token") {
            return {
                id: 999,
                name: "Dev User",
                avatar: "https://i.pravatar.cc/150",
            };
        }

        try {
            const { data } = await apiClient.get("/auth/me");
            return {
                id: data.id,
                name: data.email,
                avatar: "https://i.pravatar.cc/150",
            };
        } catch (error) {
            return null;
        }
    },
    onError: async (error) => {
        if (error.status === 401 || error.response?.status === 401) {
            return {
                logout: true,
            };
        }

        return { error };
    },
};
