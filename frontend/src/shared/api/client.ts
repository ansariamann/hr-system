import axios, { InternalAxiosRequestConfig, AxiosResponse, AxiosError } from "axios";

// Environment variables should be defined in .env
const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || "http://localhost:8000";

// Define strict types for API responses
interface ApiResponse<T = any> {
    data: T;
    message?: string;
    status: "success" | "error";
}

// Create axios instance
export const apiClient = axios.create({
    baseURL: API_BASE_URL,
    headers: {
        "Content-Type": "application/json",
    },
    timeout: 10000,
});

// Request Interceptor
apiClient.interceptors.request.use(
    (config: InternalAxiosRequestConfig) => {
        // Check for different token types
        const hrToken = localStorage.getItem("hr_token");
        const clientToken = localStorage.getItem("client_magic_token");

        // Logic to determine which token to use could be based on URL or app context
        // For now, if we are in /portal routes, prefer client token
        if (window.location.pathname.startsWith("/portal") && clientToken) {
            config.headers.Authorization = `Bearer ${clientToken}`;
        } else if (hrToken) {
            config.headers.Authorization = `Bearer ${hrToken}`;
        }

        return config;
    },
    (error: AxiosError) => {
        return Promise.reject(error);
    }
);

// Response Interceptor
apiClient.interceptors.response.use(
    (response: AxiosResponse) => {
        return response;
    },
    async (error: AxiosError) => {
        const originalRequest = error.config;

        // Handle 401 Unauthorized
        if (error.response?.status === 401) {
            // Clear tokens if invalid
            if (window.location.pathname.startsWith("/portal")) {
                localStorage.removeItem("client_magic_token");
                // Redirect to portal login if needed, or let the app handle it
                window.location.href = "/portal/auth";
            } else {
                localStorage.removeItem("hr_token");
                window.location.href = "/login";
            }
        }

        return Promise.reject(error);
    }
);
