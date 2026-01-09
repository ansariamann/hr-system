import { Routes, Route, Navigate } from "react-router-dom";
import ClientApp from "./apps/client/ClientApp";
import HrApp from "./apps/hr/HrApp";

// Make sure to remove old imports that might conflict
// import HrApp from "./apps/hr/HrApp"; // To be implemented

export default function App() {
  return (
    <Routes>
      {/* Route for Client Portal */}
      <Route path="/portal/*" element={<ClientApp />} />

      {/* Route for HR Dashboard (Admin) */}
      <Route path="/admin/*" element={<HrApp />} />

      {/* Default Redirect */}
      <Route path="*" element={<Navigate to="/portal/auth" replace />} />
    </Routes>
  );
}
