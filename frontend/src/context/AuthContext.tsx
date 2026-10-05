import React, { createContext, useContext, useEffect, useState } from 'react';
import { api } from '../api/client';
import { collectNetworkTelemetry } from '../utils/telemetry';
import type { CustomerProfile, User, UserRole } from '../types';

interface AuthContextType {
  user: User | null;
  customer: CustomerProfile | null;
  token: string | null;
  sessionError: string | null;
  isAuthenticated: boolean;
  isLoading: boolean;
  login: (username: string, password?: string, force_login?: boolean) => Promise<any>;
  register: (data: any) => Promise<any>;
  logout: () => void;
  switchDemoRole: (role: UserRole) => Promise<void>;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export const AuthProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [user, setUser] = useState<User | null>(() => {
    const saved = localStorage.getItem('omerta_user');
    return saved ? JSON.parse(saved) : null;
  });

  const [customer, setCustomer] = useState<CustomerProfile | null>(() => {
    const saved = localStorage.getItem('omerta_customer');
    return saved ? JSON.parse(saved) : null;
  });

  const [token, setToken] = useState<string | null>(() => localStorage.getItem('omerta_token') || null);
  const [isLoading, setIsLoading] = useState(false);

  const [sessionError, setSessionError] = useState<string | null>(null);

  useEffect(() => {
    if (token) {
      localStorage.setItem('omerta_token', token);
    } else {
      localStorage.removeItem('omerta_token');
    }
  }, [token]);

  useEffect(() => {
    if (user) {
      localStorage.setItem('omerta_user', JSON.stringify(user));
    } else {
      localStorage.removeItem('omerta_user');
    }
  }, [user]);

  useEffect(() => {
    if (customer) {
      localStorage.setItem('omerta_customer', JSON.stringify(customer));
    } else {
      localStorage.removeItem('omerta_customer');
    }
  }, [customer]);

  // Handle remote session revocation or token expiration
  useEffect(() => {
    const handleUnauthorized = (e: any) => {
      const msg = e?.detail?.message || 'Your session was terminated because this account signed in elsewhere.';
      setSessionError(msg);
      logout();
    };

    window.addEventListener('omerta_unauthorized', handleUnauthorized);
    return () => window.removeEventListener('omerta_unauthorized', handleUnauthorized);
  }, []);

  // 30-Second Recurring Network Telemetry Probe & Active Session Synchronizer
  useEffect(() => {
    if (!token || !user) return;

    const runTelemetrySync = async () => {
      try {
        const declared = customer?.declared_country || 'EG';
        const telemetry = await collectNetworkTelemetry(declared);
        const res = await api.sendTelemetryHeartbeat({
          client_ip: telemetry.ip,
          country: telemetry.country,
          is_vpn: telemetry.is_vpn,
          isp: telemetry.isp,
          org: telemetry.org,
          browser_timezone: telemetry.browser_timezone,
          ip_timezone: telemetry.ip_timezone,
          user_agent: telemetry.user_agent,
        });

        // If backend locked admin due to VPN
        if (res?.locked || res?.status === 'LOCKED' || res?.error === 'ADMIN_VPN_SECURITY_LOCK') {
          setSessionError(res.message || 'Security Alert: Administrator account locked due to VPN/Proxy connection detection.');
          logout();
          return;
        }

        // Notify active pages (e.g. CustomerSecurityPage, RiskMonitoringPage)
        window.dispatchEvent(
          new CustomEvent('omerta_telemetry_synced', {
            detail: { telemetry, res },
          })
        );
      } catch (err: any) {
        if (err?.status === 401) {
          // Token or session was revoked
          logout();
        }
      }
    };

    // Run first probe shortly after login, then every 30 seconds
    const initialTimer = setTimeout(runTelemetrySync, 1000);
    const interval = setInterval(runTelemetrySync, 30000);

    return () => {
      clearTimeout(initialTimer);
      clearInterval(interval);
    };
  }, [token, user, customer?.declared_country]);


  const login = async (
    username: string,
    password = 'Password123!',
    force_login = false
  ) => {
    setIsLoading(true);
    try {
      // Gather real network telemetry and detect active VPN/Proxy
      const telemetry = await collectNetworkTelemetry('EG');

      const res = await api.login({
        username,
        password,
        force_login,
        is_vpn: telemetry.is_vpn,
        client_ip: telemetry.ip,
        country: telemetry.country,
        isp: telemetry.isp,
        org: telemetry.org,
        browser_timezone: telemetry.browser_timezone,
        ip_timezone: telemetry.ip_timezone,
      });

      setToken(res.access_token);
      setUser(res.user);
      if (res.customer) {
        setCustomer(res.customer);
      } else {
        setCustomer(null);
      }
      setSessionError(null);
      return res;
    } finally {
      setIsLoading(false);
    }
  };

  const register = async (data: any) => {
    setIsLoading(true);
    try {
      const telemetry = await collectNetworkTelemetry(data.country || 'EG');
      const payload = {
        ...data,
        is_vpn: telemetry.is_vpn,
        client_ip: telemetry.ip,
        observed_country: telemetry.country,
        isp: telemetry.isp,
        org: telemetry.org,
        browser_timezone: telemetry.browser_timezone,
        ip_timezone: telemetry.ip_timezone,
      };

      const res = await api.register(payload);
      setToken(res.access_token);
      setUser(res.user);
      setCustomer(res.customer);
      return res;
    } finally {
      setIsLoading(false);
    }
  };

  const switchDemoRole = async (role: UserRole) => {
    const roleProfiles: Record<string, { username: string; pass: string; name: string }> = {
      CUSTOMER: { username: 'ziad@omerta.ai', pass: 'Customer@2026!', name: 'Ziad Karim' },
      ADMINISTRATOR: { username: 'admin@omerta.ai', pass: 'AdminPass123!', name: 'Dr. Sarah Al-Rashid' },
      SUB_ADMINISTRATOR: { username: 'admin@omerta.ai', pass: 'AdminPass123!', name: 'Operations Sub-Admin' },
      FRAUD_ANALYST: { username: 'analyst@omerta.ai', pass: 'AnalystPass123!', name: 'Tariq Mansour' },
      SENIOR_INVESTIGATOR: { username: 'investigator@omerta.ai', pass: 'InvestigatorPass123!', name: 'Laila El-Kady' },
      INVESTIGATOR: { username: 'investigator@omerta.ai', pass: 'InvestigatorPass123!', name: 'Laila El-Kady' },
      AUDITOR: { username: 'auditor@omerta.ai', pass: 'AuditorPass123!', name: 'Omar Farooq' },
      COMPLIANCE_AUDITOR: { username: 'auditor@omerta.ai', pass: 'AuditorPass123!', name: 'Omar Farooq' },
    };

    const profile = roleProfiles[role];
    if (profile) {
      await login(profile.username, profile.pass, true);
    }
  };

  const logout = () => {
    setUser(null);
    setCustomer(null);
    setToken(null);
    localStorage.removeItem('omerta_token');
    localStorage.removeItem('omerta_user');
    localStorage.removeItem('omerta_customer');
  };

  return (
    <AuthContext.Provider
      value={{
        user,
        customer,
        token,
        sessionError,
        isAuthenticated: !!user && !!token,
        isLoading,
        login,
        register,
        logout,
        switchDemoRole,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
};

export const useAuth = (): AuthContextType => {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
};
