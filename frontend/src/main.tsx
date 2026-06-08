import React from "react";
import ReactDOM from "react-dom/client";
import {
  BrowserRouter,
  Navigate,
  Route,
  Routes,
  useLocation,
} from "react-router-dom";
import "./index.css";
import { AuthProvider, useAuth } from "./auth";
import { Spinner } from "./components/ui";
import Layout from "./components/Layout";
import Login from "./pages/Login";
import Signup from "./pages/Signup";
import Dashboard from "./pages/Dashboard";
import Onboarding from "./pages/Onboarding";
import LinkedIn from "./pages/LinkedIn";
import Campaigns from "./pages/Campaigns";
import CampaignEditor from "./pages/CampaignEditor";
import Queue from "./pages/Queue";
import Deals from "./pages/Deals";
import Settings from "./pages/Settings";

function RequireAuth({ children }: { children: React.ReactNode }) {
  const { me, loading } = useAuth();
  const location = useLocation();
  if (loading) return <Spinner />;
  if (!me) return <Navigate to="/login" state={{ from: location }} replace />;
  return <>{children}</>;
}

function App() {
  return (
    <Routes>
      <Route path="/login" element={<Login />} />
      <Route path="/signup" element={<Signup />} />
      <Route path="/onboarding" element={<RequireAuth><Onboarding /></RequireAuth>} />
      <Route
        element={
          <RequireAuth>
            <Layout />
          </RequireAuth>
        }
      >
        <Route path="/" element={<Dashboard />} />
        <Route path="/campaigns" element={<Campaigns />} />
        <Route path="/campaigns/new" element={<CampaignEditor />} />
        <Route path="/campaigns/:id" element={<CampaignEditor />} />
        <Route path="/queue" element={<Queue />} />
        <Route path="/deals" element={<Deals />} />
        <Route path="/linkedin" element={<LinkedIn />} />
        <Route path="/settings" element={<Settings />} />
      </Route>
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <BrowserRouter>
      <AuthProvider>
        <App />
      </AuthProvider>
    </BrowserRouter>
  </React.StrictMode>
);
