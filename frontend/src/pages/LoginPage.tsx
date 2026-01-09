import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { Button } from "../components/ui/Button";
import { Input } from "../components/ui/Input";
import { Card, CardHeader, CardTitle, CardDescription, CardContent, CardFooter } from "../components/ui/Card";
import { ArrowRight, Loader2 } from "lucide-react";

export default function LoginPage() {
    const [isLoading, setIsLoading] = useState(false);
    const navigate = useNavigate();

    const handleLogin = (e: React.FormEvent) => {
        e.preventDefault();
        setIsLoading(true);
        // Simulate login
        setTimeout(() => {
            setIsLoading(false);
            navigate("/");
        }, 1500);
    };

    return (
        <Card className="border-0 shadow-2xl bg-white/80 backdrop-blur-sm dark:bg-gray-800/80">
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
                        <Input id="email" type="email" placeholder="m@example.com" required disabled={isLoading} />
                    </div>
                    <div className="grid gap-2">
                        <label htmlFor="password" className="text-sm font-medium leading-none peer-disabled:cursor-not-allowed peer-disabled:opacity-70">Password</label>
                        <Input id="password" type="password" required disabled={isLoading} />
                    </div>
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
    );
}
