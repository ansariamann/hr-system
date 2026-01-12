import { Routes, Route, Navigate } from "react-router-dom";
import PortalLogin from "./pages/PortalLogin";
import PortalDashboard from "./pages/PortalDashboard";
import AuthLayout from "./layouts/AuthLayout";

export default function ClientApp() {
    return (
        <Routes>
            {/* Auth routes under /portal/auth */}
            <Route path="auth" element={<AuthLayout />}>
                {/* /portal/auth -> /portal/auth/verify */}
                <Route index element={<Navigate to="verify" />} />
                <Route path="verify" element={<PortalLogin />} />
            </Route>

            {/* Dashboard at /portal */}
            <Route index element={<PortalDashboard />} />
        </Routes>
    );
}
