import { Routes, Route, Navigate } from "react-router-dom";
import PortalLogin from "./pages/PortalLogin";
import PortalDashboard from "./pages/PortalDashboard";
import AuthLayout from "./layouts/AuthLayout";

export default function ClientApp() {
    return (
        <Routes>
            <Route path="auth" element={<AuthLayout />}>
                <Route index element={<Navigate to="verify" />} />
                <Route path="verify" element={<PortalLogin />} />
            </Route>

            <Route path="/" element={<PortalDashboard />} />
        </Routes>
    );
}
