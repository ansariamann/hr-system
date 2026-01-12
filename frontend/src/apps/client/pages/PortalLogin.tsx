import { useState } from "react";
import { useNavigate, useLocation } from "react-router-dom";
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from "../../../shared/components/ui/Card";
import { Loader2 } from "lucide-react";
import { apiClient } from "../../../shared/api/client";

export default function PortalLogin() {
    const navigate = useNavigate();
    const location = useLocation();
    const [email, setEmail] = useState("");
    const [password, setPassword] = useState("");
    const [isLoading, setIsLoading] = useState(false);
    const [error, setError] = useState("");

    const handleLogin = async (e: React.FormEvent) => {
        e.preventDefault();
        setIsLoading(true);
        setError("");

        try {
            const formData = new URLSearchParams({
                username: email,
                password: password,
            });

            const { data } = await apiClient.post("/auth/login", formData, {
                headers: {
                    "Content-Type": "application/x-www-form-urlencoded",
                },
            });

            if (data.access_token) {
                // Determine context based on URL
                if (location.pathname.startsWith("/admin") || location.pathname.startsWith("/login")) {
                    localStorage.setItem("hr_token", data.access_token);
                    // Refine will handle redirect usually, but if this is custom:
                    window.location.href = "/admin";
                } else {
                    localStorage.setItem("client_magic_token", data.access_token);
                    navigate("/portal/");
                }
            }
        } catch (err: any) {
            console.error(err);
            setError(err.response?.data?.detail || "Invalid email or password");
        } finally {
            setIsLoading(false);
        }
    };

    return (
        <div className="flex min-h-screen items-center justify-center bg-gray-50 p-4">
            <Card className="w-full max-w-md border-0 shadow-lg bg-white">
                <CardHeader className="text-center">
                    <CardTitle className="text-2xl font-bold">Sign In</CardTitle>
                    <CardDescription>Enter your credentials to access the system</CardDescription>
                </CardHeader>
                <CardContent>
                    <form onSubmit={handleLogin} className="space-y-4">
                        <div className="space-y-2">
                            <label className="text-sm font-medium leading-none" htmlFor="email">Email</label>
                            <input
                                id="email"
                                type="email"
                                className="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background"
                                placeholder="name@example.com"
                                value={email}
                                onChange={(e) => setEmail(e.target.value)}
                                required
                            />
                        </div>
                        <div className="space-y-2">
                            <label className="text-sm font-medium leading-none" htmlFor="password">Password</label>
                            <input
                                id="password"
                                type="password"
                                className="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background"
                                value={password}
                                onChange={(e) => setPassword(e.target.value)}
                                required
                            />
                        </div>

                        {error && (
                            <div className="text-sm text-red-500 font-medium text-center">
                                {error}
                            </div>
                        )}

                        <button
                            type="submit"
                            disabled={isLoading}
                            className="w-full inline-flex h-10 items-center justify-center rounded-md bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700 disabled:opacity-50"
                        >
                            {isLoading && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
                            Sign In
                        </button>
                    </form>
                </CardContent>
            </Card>
        </div>
    );
}
