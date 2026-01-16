import axios, { type InternalAxiosRequestConfig, type AxiosResponse, type AxiosError } from "axios";

// Environment variables should be defined in .env
const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || "http://localhost:8000";

// Define strict types for API responses
export interface ApiResponse<T = any> {
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
        // Add HR token to requests
        const hrToken = localStorage.getItem("hr_token");

        if (hrToken) {
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
        // Handle 401 Unauthorized
        if (error.response?.status === 401) {
            // Clear HR token and redirect to login
            localStorage.removeItem("hr_token");
            window.location.href = "/login";
        }

        return Promise.reject(error);
    }
);
