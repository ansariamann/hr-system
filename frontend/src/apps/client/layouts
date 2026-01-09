import { Outlet } from "react-router-dom";

export default function AuthLayout() {
    return (
        <div className="flex min-h-screen items-center justify-center bg-gray-50 dark:bg-gray-900">
            <div className="w-full max-w-md space-y-8 px-4 sm:px-6 lg:px-8">
                <div className="relative">
                    <div className="absolute -left-4 -top-4 h-72 w-72 animate-blob rounded-full bg-purple-300 opacity-70 mix-blend-multiply blur-xl filter dark:bg-purple-900"></div>
                    <div className="animation-delay-2000 absolute -right-4 -top-4 h-72 w-72 animate-blob rounded-full bg-yellow-300 opacity-70 mix-blend-multiply blur-xl filter dark:bg-yellow-900"></div>
                    <div className="animation-delay-4000 absolute -bottom-8 left-20 h-72 w-72 animate-blob rounded-full bg-pink-300 opacity-70 mix-blend-multiply blur-xl filter dark:bg-pink-900"></div>
                    <div className="relative">
                        <Outlet />
                    </div>
                </div>
            </div>
        </div>
    );
}
