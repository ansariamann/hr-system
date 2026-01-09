import { Outlet, NavLink } from "react-router-dom";
import { LayoutDashboard, Users, FileText, Settings, LogOut } from "lucide-react";
import { cn } from "../utils/cn";
import { Button } from "../components/ui/Button";

const navigation = [
    { name: "Dashboard", href: "/", icon: LayoutDashboard },
    { name: "Candidates", href: "/candidates", icon: Users },
    { name: "Applications", href: "/applications", icon: FileText },
    { name: "Settings", href: "/settings", icon: Settings },
];

export default function DashboardLayout() {
    return (
        <div className="flex min-h-screen bg-gray-100 dark:bg-gray-900">
            {/* Sidebar */}
            <div className="hidden w-64 flex-col border-r bg-white dark:bg-gray-800 md:flex">
                <div className="flex h-16 items-center px-6 border-b">
                    <span className="text-xl font-bold tracking-tight text-primary-600 dark:text-primary-400">
                        HR System
                    </span>
                </div>
                <nav className="flex-1 space-y-1 px-4 py-6">
                    {navigation.map((item) => (
                        <NavLink
                            key={item.name}
                            to={item.href}
                            className={({ isActive }) =>
                                cn(
                                    "flex items-center gap-3 rounded-md px-3 py-2 text-sm font-medium transition-colors",
                                    isActive
                                        ? "bg-primary/10 text-primary-600 dark:text-primary-400"
                                        : "text-gray-600 hover:bg-gray-50 hover:text-gray-900 dark:text-gray-300 dark:hover:bg-gray-700 dark:hover:text-white"
                                )
                            }
                        >
                            <item.icon className="h-5 w-5" />
                            {item.name}
                        </NavLink>
                    ))}
                </nav>
                <div className="p-4 border-t">
                    <Button variant="outline" className="w-full justify-start gap-3">
                        <LogOut className="h-4 w-4" />
                        Logout
                    </Button>
                </div>
            </div>

            {/* Main Content */}
            <div className="flex flex-1 flex-col">
                <header className="flex h-16 items-center justify-between border-b bg-white px-6 dark:bg-gray-800 md:hidden">
                    <span className="text-xl font-bold tracking-tight text-primary-600 dark:text-primary-400">
                        HR System
                    </span>
                    {/* Mobile menu button would go here */}
                </header>

                <main className="flex-1 overflow-y-auto p-6">
                    <div className="mx-auto max-w-7xl">
                        <Outlet />
                    </div>
                </main>
            </div>
        </div>
    );
}
