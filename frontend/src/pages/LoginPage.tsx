import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { Button } from "../shared/components/ui/Button";
import { Input } from "../components/ui/Input";
import { Card, CardHeader, CardTitle, CardDescription, CardContent, CardFooter } from "../components/ui/Card";
import { ArrowRight, Loader2, AlertCircle } from "lucide-react";
import { apiClient } from "../shared/api/client";

export default function LoginPage() {
    const [isLoading, setIsLoading] = useState(false);
    const [error, setError] = useState<string | null>(null);
    const navigate = useNavigate();

    const handleLogin = async (e: React.FormEvent) => {
        e.preventDefault();
        setIsLoading(true);
        setError(null);

        const formData = new FormData(e.target as HTMLFormElement);
        const email = formData.get("email") as string;
        const password = formData.get("password") as string;

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
                // Redirect to admin dashboard
                window.location.href = "/admin";
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
            <Card className="w-full max-w-md border-0 shadow-2xl bg-white/80 backdrop-blur-sm dark:bg-gray-800/80">
                <CardHeader className="space-y-1">
                    <CardTitle className="text-2xl font-bold tracking-tight text-center">
                        Welcome back
                    </CardTitle>
                    <CardDescription className="text-center">
                        Enter your email to sign in to your account
                    </CardDescription>
                </CardHeader>
                <form onSubmit={handleLogin}>
                    <CardContent className="grid gap-4">
                        <div className="grid gap-2">
                            <label htmlFor="email" className="text-sm font-medium leading-none peer-disabled:cursor-not-allowed peer-disabled:opacity-70">Email</label>
                            <Input id="email" name="email" type="email" placeholder="m@example.com" required disabled={isLoading} />
                        </div>
                        <div className="grid gap-2">
                            <label htmlFor="password" className="text-sm font-medium leading-none peer-disabled:cursor-not-allowed peer-disabled:opacity-70">Password</label>
                            <Input id="password" name="password" type="password" required disabled={isLoading} />
                        </div>
                        {error && (
                            <div className="flex items-center gap-2 text-sm text-red-500 bg-red-50 p-3 rounded-md">
                                <AlertCircle className="h-4 w-4" />
                                {error}
                            </div>
                        )}
                    </CardContent>
                    <CardFooter className="flex flex-col gap-4">
                        <Button className="w-full" type="submit" disabled={isLoading}>
                            {isLoading && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
                            Sign In
                            {!isLoading && <ArrowRight className="ml-2 h-4 w-4" />}
                        </Button>
                        <div className="text-sm text-muted-foreground text-center">
                            Don't have an account?{" "}
                            <Link to="/register" className="text-primary hover:underline">
                                Contact Admin
                            </Link>
                        </div>
                    </CardFooter>
                </form>
            </Card>
        </div>
    );
}
