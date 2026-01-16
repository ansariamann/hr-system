import { Routes, Route, Navigate } from "react-router-dom";
import HrApp from "./apps/hr/HrApp";
import LoginPage from "./pages/LoginPage";

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route path="/admin/*" element={<HrApp />} />
      <Route path="*" element={<Navigate to="/login" replace />} />
    </Routes>
  );
}
