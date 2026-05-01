import React, { useState, useEffect } from "react";
import "./App.css";
import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import { AuthProvider, useAuth } from "./contexts/AuthContext";
import Layout from "./components/Layout";
import SuperAdminLayout from "./components/SuperAdminLayout";
import LoginPage from "./pages/LoginPage";
import DashboardPage from "./pages/DashboardPage";
import PatientsPage from "./pages/PatientsPage";
import AppointmentsPage from "./pages/AppointmentsPage";
import CalendarPage from "./pages/CalendarPage";
import CallLogsPage from "./pages/CallLogsPage";
import AnalyticsPage from "./pages/AnalyticsPage";
import SettingsPage from "./pages/SettingsPage";
import InsurancePage from "./pages/InsurancePage";
import ManagePage from "./pages/ManagePage";
import BillingPage from "./pages/BillingPage";
import AuditPage from "./pages/AuditPage";
import OnboardingWizard from "./pages/OnboardingWizard";
import PracticeSettingsPage from "./pages/PracticeSettingsPage";
import SuperAdminRetellPage from "./pages/SuperAdminRetellPage";
import SuperAdminDashboardPage from "./pages/SuperAdminDashboardPage";
import SuperAdminPracticesPage from "./pages/SuperAdminPracticesPage";
import SuperAdminLLMPage from "./pages/SuperAdminLLMPage";
import ErrorBoundary from "./components/ErrorBoundary";
import axios from "axios";

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
const API = `${BACKEND_URL}/api`;

function LoadingScreen() {
  return (
    <div className="flex items-center justify-center min-h-screen bg-gray-50">
      <div className="text-center">
        <div className="w-10 h-10 border-3 border-teal-600 border-t-transparent rounded-full animate-spin mx-auto" />
        <p className="text-sm text-gray-500 mt-3">Loading...</p>
      </div>
    </div>
  );
}

/**
 * PracticeRoute — for the regular clinic UI. Blocks super_admins (they
 * belong in /admin). Sends practices in onboarding to the wizard.
 */
function PracticeRoute({ children, allowOnboarding = false }) {
  const { user, loading, practice, isSuperAdmin } = useAuth();
  if (loading) return <LoadingScreen />;
  if (!user) return <Navigate to="/login" replace />;
  if (isSuperAdmin) return <Navigate to="/admin" replace />;
  if (practice?.settings && practice?.status === 'onboarding' && !allowOnboarding) {
    return <Navigate to="/onboarding" replace />;
  }
  return children;
}

/**
 * SuperAdminRoute — for the Platform Console. Hard-blocks anyone
 * who is not a super_admin (sends practice users to their dashboard).
 */
function SuperAdminRoute({ children }) {
  const { user, loading, isSuperAdmin } = useAuth();
  if (loading) return <LoadingScreen />;
  if (!user) return <Navigate to="/login" replace />;
  if (!isSuperAdmin) return <Navigate to="/dashboard" replace />;
  return children;
}

function PracticePage({ component: Component, ...props }) {
  const { user, token } = useAuth();
  const [notifications, setNotifications] = useState([]);

  useEffect(() => {
    if (user && token) {
      fetchNotifications();
      const interval = setInterval(fetchNotifications, 30000);
      return () => clearInterval(interval);
    }
  }, [user, token]);

  const fetchNotifications = async () => {
    try {
      const res = await axios.get(`${API}/notifications`, {
        headers: { Authorization: `Bearer ${token}` }
      });
      setNotifications(res.data);
    } catch {}
  };

  const handleNotificationRead = async (id) => {
    try {
      await axios.post(`${API}/notifications/${id}/read`, {}, {
        headers: { Authorization: `Bearer ${token}` }
      });
      setNotifications(prev => prev.map(n => n.id === id ? { ...n, status: 'read' } : n));
    } catch {}
  };

  return (
    <PracticeRoute>
      <Layout notifications={notifications} onNotificationRead={handleNotificationRead}>
        <ErrorBoundary label="Page" onReset={() => window.location.reload()}>
          <Component {...props} />
        </ErrorBoundary>
      </Layout>
    </PracticeRoute>
  );
}

function SuperAdminPage({ component: Component, ...props }) {
  return (
    <SuperAdminRoute>
      <SuperAdminLayout>
        <ErrorBoundary label="Page" onReset={() => window.location.reload()}>
          <Component {...props} />
        </ErrorBoundary>
      </SuperAdminLayout>
    </SuperAdminRoute>
  );
}

function AppContent() {
  const { user, practice, isSuperAdmin } = useAuth();
  const isOnboarding = practice?.status === 'onboarding';

  // Where authenticated users land
  const homeFor = () => {
    if (!user) return '/login';
    if (isSuperAdmin) return '/admin';
    return isOnboarding ? '/onboarding' : '/dashboard';
  };

  return (
    <Routes>
      <Route path="/login" element={user ? <Navigate to={homeFor()} replace /> : <LoginPage />} />
      <Route path="/signup" element={<OnboardingWizard />} />
      <Route path="/onboarding" element={
        <PracticeRoute allowOnboarding={true}>
          <OnboardingWizard />
        </PracticeRoute>
      } />

      {/* Practice Portal — clinic admins, staff, providers, auditors */}
      <Route path="/dashboard" element={<PracticePage component={DashboardPage} />} />
      <Route path="/patients" element={<PracticePage component={PatientsPage} />} />
      <Route path="/appointments" element={<PracticePage component={AppointmentsPage} />} />
      <Route path="/calendar" element={<PracticePage component={CalendarPage} />} />
      <Route path="/call-logs" element={<PracticePage component={CallLogsPage} />} />
      <Route path="/analytics" element={<PracticePage component={AnalyticsPage} />} />
      <Route path="/settings" element={<PracticePage component={SettingsPage} />} />
      <Route path="/practice-settings" element={<PracticePage component={PracticeSettingsPage} />} />
      <Route path="/insurance" element={<PracticePage component={InsurancePage} />} />
      <Route path="/manage" element={<PracticePage component={ManagePage} />} />
      <Route path="/billing" element={<PracticePage component={BillingPage} />} />
      <Route path="/audit" element={<PracticePage component={AuditPage} />} />

      {/* Platform Console — super admins only */}
      <Route path="/admin" element={<SuperAdminPage component={SuperAdminDashboardPage} />} />
      <Route path="/admin/practices" element={<SuperAdminPage component={SuperAdminPracticesPage} />} />
      <Route path="/admin/retell" element={<SuperAdminPage component={SuperAdminRetellPage} />} />
      <Route path="/admin/llm" element={<SuperAdminPage component={SuperAdminLLMPage} />} />

      <Route path="*" element={<Navigate to={homeFor()} replace />} />
    </Routes>
  );
}

function App() {
  return (
    <div className="App">
      <BrowserRouter>
        <AuthProvider>
          <AppContent />
        </AuthProvider>
      </BrowserRouter>
    </div>
  );
}

export default App;
