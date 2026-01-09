import { AuthProvider } from "@refinedev/core";
import { apiClient } from "../../shared/api/client";

export const authProvider: AuthProvider = {
    login: async ({ email, password }) => {
        try {
            const { data } = await apiClient.post("/auth/login", {
                username: email,
                password: password,
            }, {
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
        } catch (error) {
            return {
                success: false,
                error: {
                    name: "LoginError",
                    message: "Invalid email or password",
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
