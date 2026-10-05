import React from 'react';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { AuthProvider, useAuth } from './context/AuthContext';
import { ThemeProvider } from './context/ThemeContext';
import { AppLayout } from './components/layout/AppLayout';

// Auth Pages
import { LoginPage } from './pages/LoginPage';
import { RegisterPage } from './pages/RegisterPage';
import { ForgotPasswordPage } from './pages/ForgotPasswordPage';
import { ResetPasswordPage } from './pages/ResetPasswordPage';

// Admin / Intelligence Pages
import { DashboardPage as AdminDashboardPage } from './pages/DashboardPage';
import { TransactionsPage as AdminTransactionsPage } from './pages/TransactionsPage';
import { TransactionDetailPage } from './pages/TransactionDetailPage';
import { RiskMonitoringPage } from './pages/RiskMonitoringPage';
import { InvestigationsPage } from './pages/InvestigationsPage';
import { CustomersPage as AdminUsersPage } from './pages/CustomersPage';
import { AccountsPage as AdminAccountsPage } from './pages/AccountsPage';
import { DevicesPage as AdminDevicesPage } from './pages/DevicesPage';
import { NetworkAnalysisPage } from './pages/NetworkAnalysisPage';
import { ReportsPage } from './pages/ReportsPage';
import { AnalyticsPage } from './pages/AnalyticsPage';
import { AuditLogsPage } from './pages/AuditLogsPage';
import { AiAssistantPage } from './pages/AiAssistantPage';
import { SettingsPage } from './pages/SettingsPage';

// Customer Banking Pages
import { CustomerDashboardPage } from './pages/customer/CustomerDashboardPage';
import { SendMoneyPage } from './pages/customer/SendMoneyPage';
import { CustomerAccountsPage } from './pages/customer/CustomerAccountsPage';
import { CustomerTransactionsPage } from './pages/customer/CustomerTransactionsPage';
import { CustomerSecurityPage } from './pages/customer/CustomerSecurityPage';
import { CustomerProfilePage } from './pages/customer/CustomerProfilePage';

// Protected Route Component
const ProtectedRoute: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const { isAuthenticated, isLoading } = useAuth();

  if (isLoading) {
    return (
      <div className="min-h-screen bg-[#080D19] flex flex-col items-center justify-center text-[#A7B4C8]">
        <div className="w-8 h-8 border-2 border-[#29C5D9] border-t-transparent rounded-full animate-spin mb-4" />
        <p className="text-sm font-medium text-[#F4F7FC]">Authenticating Omerta.ai Session...</p>
      </div>
    );
  }

  if (!isAuthenticated) {
    return <Navigate to="/login" replace />;
  }

  return <>{children}</>;
};

// Role-based Root Redirector
const RootRedirector: React.FC = () => {
  const { user } = useAuth();
  const role = user?.role;

  if (role === 'CUSTOMER') {
    return <Navigate to="/customer/dashboard" replace />;
  }
  if (role === 'SENIOR_INVESTIGATOR' || role === 'INVESTIGATOR') {
    return <Navigate to="/admin/investigations" replace />;
  }
  if (role === 'AUDITOR' || role === 'COMPLIANCE_AUDITOR') {
    return <Navigate to="/admin/audit-logs" replace />;
  }
  return <Navigate to="/admin/dashboard" replace />;
};

export const App: React.FC = () => {
  return (
    <ThemeProvider>
      <AuthProvider>
        <BrowserRouter>
          <Routes>
            {/* Public Authentication Routes */}
            <Route path="/login" element={<LoginPage />} />
            <Route path="/register" element={<RegisterPage />} />
            <Route path="/forgot-password" element={<ForgotPasswordPage />} />
            <Route path="/reset-password" element={<ResetPasswordPage />} />

            {/* Protected Layout Container */}
            <Route
              element={
                <ProtectedRoute>
                  <AppLayout />
                </ProtectedRoute>
              }
            >
              {/* Root redirect */}
              <Route path="/" element={<RootRedirector />} />

              {/* Customer Banking Portal Routes */}
              <Route path="/customer">
                <Route index element={<Navigate to="/customer/dashboard" replace />} />
                <Route path="dashboard" element={<CustomerDashboardPage />} />
                <Route path="accounts" element={<CustomerAccountsPage />} />
                <Route path="transfer" element={<SendMoneyPage />} />
                <Route path="transactions" element={<CustomerTransactionsPage />} />
                <Route path="security" element={<CustomerSecurityPage />} />
                <Route path="profile" element={<CustomerProfilePage />} />
              </Route>

              {/* Admin Control Center Routes */}
              <Route path="/admin">
                <Route index element={<RootRedirector />} />
                <Route path="dashboard" element={<AdminDashboardPage />} />
                <Route path="users" element={<AdminUsersPage />} />
                <Route path="customers" element={<AdminUsersPage />} />
                <Route path="accounts" element={<AdminAccountsPage />} />
                <Route path="transactions" element={<AdminTransactionsPage />} />
                <Route path="transactions/:id" element={<TransactionDetailPage />} />
                <Route path="risk-monitoring" element={<RiskMonitoringPage />} />
                <Route path="investigations" element={<InvestigationsPage />} />
                <Route path="devices" element={<AdminDevicesPage />} />
                <Route path="network" element={<NetworkAnalysisPage />} />
                <Route path="network-analysis" element={<NetworkAnalysisPage />} />
                <Route path="reports" element={<ReportsPage />} />
                <Route path="analytics" element={<AnalyticsPage />} />
                <Route path="audit-logs" element={<AuditLogsPage />} />
                <Route path="ai-assistant" element={<AiAssistantPage />} />
                <Route path="settings" element={<SettingsPage />} />
              </Route>

              {/* Legacy fallback aliases */}
              <Route path="/dashboard" element={<RootRedirector />} />
              <Route path="/transactions" element={<Navigate to="/admin/transactions" replace />} />
              <Route path="/transactions/:id" element={<TransactionDetailPage />} />
              <Route path="/risk-monitoring" element={<Navigate to="/admin/risk-monitoring" replace />} />
              <Route path="/investigations" element={<Navigate to="/admin/investigations" replace />} />
              <Route path="/customers" element={<Navigate to="/admin/users" replace />} />
              <Route path="/accounts" element={<Navigate to="/admin/accounts" replace />} />
              <Route path="/devices" element={<Navigate to="/admin/devices" replace />} />
              <Route path="/network-analysis" element={<Navigate to="/admin/network-analysis" replace />} />
              <Route path="/reports" element={<Navigate to="/admin/reports" replace />} />
              <Route path="/analytics" element={<Navigate to="/admin/analytics" replace />} />
              <Route path="/audit-logs" element={<Navigate to="/admin/audit-logs" replace />} />
              <Route path="/settings" element={<Navigate to="/admin/settings" replace />} />
            </Route>

            {/* Catch-all Fallback */}
            <Route path="*" element={<Navigate to="/" replace />} />
          </Routes>
        </BrowserRouter>
      </AuthProvider>
    </ThemeProvider>
  );
};

export default App;
