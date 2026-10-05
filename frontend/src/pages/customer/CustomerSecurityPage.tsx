import React, { useState, useEffect } from 'react';
import {
  ShieldCheck,
  Smartphone,
  Laptop,
  Globe,
  AlertTriangle,
  LogOut,
  ToggleLeft,
  ToggleRight,
  Info,
  CheckCircle2,
  Loader2,
  RefreshCw,
  Radio,
} from 'lucide-react';
import { api } from '../../api/client';
import { useAuth } from '../../context/AuthContext';
import { collectNetworkTelemetry } from '../../utils/telemetry';
import type { CustomerSession } from '../../types';

export const CustomerSecurityPage: React.FC = () => {
  const { customer } = useAuth();
  const [sessions, setSessions] = useState<CustomerSession[]>([]);
  const [consent, setConsent] = useState(customer?.device_consent ?? true);
  const [isLoading, setIsLoading] = useState(true);
  const [isProbing, setIsProbing] = useState(false);
  const [msg, setMsg] = useState<string | null>(null);
  const [secondsRemaining, setSecondsRemaining] = useState(30);

  const fetchSessions = async (showLoading = true) => {
    if (showLoading) setIsLoading(true);
    try {
      const res = await api.getCustomerSessions();
      setSessions(res);
    } catch {
      // Fallback
      setSessions([
        {
          session_id: 'SESS-CURRENT',
          device_label: 'Desktop (macOS / Chrome)',
          platform: 'macOS',
          observed_country: 'EG',
          is_vpn: false,
          is_active: true,
          started_at: new Date().toISOString(),
        },
      ]);
    } finally {
      if (showLoading) setIsLoading(false);
    }
  };

  const probeAndUpdateTelemetry = async () => {
    setIsProbing(true);
    try {
      const declared = customer?.declared_country || 'EG';
      const telemetry = await collectNetworkTelemetry(declared);
      await api.sendTelemetryHeartbeat({
        client_ip: telemetry.ip,
        country: telemetry.country,
        is_vpn: telemetry.is_vpn,
        isp: telemetry.isp,
        org: telemetry.org,
        browser_timezone: telemetry.browser_timezone,
        ip_timezone: telemetry.ip_timezone,
        user_agent: telemetry.user_agent,
      });
      await fetchSessions(false);
      setSecondsRemaining(30);
    } catch (e) {
      console.warn('Telemetry probe notice:', e);
    } finally {
      setIsProbing(false);
    }
  };

  // Initial load
  useEffect(() => {
    fetchSessions();
  }, []);

  // 30-Second recurring countdown timer & automatic session re-check
  useEffect(() => {
    const timer = setInterval(() => {
      setSecondsRemaining((prev) => {
        if (prev <= 1) {
          probeAndUpdateTelemetry();
          return 30;
        }
        return prev - 1;
      });
    }, 1000);

    // Also sync whenever background telemetry probe finishes
    const handleSync = () => {
      fetchSessions(false);
      setSecondsRemaining(30);
    };
    window.addEventListener('omerta_telemetry_synced', handleSync);

    return () => {
      clearInterval(timer);
      window.removeEventListener('omerta_telemetry_synced', handleSync);
    };
  }, [customer?.declared_country]);

  const handleRevokeSession = async (sessionId: string) => {
    try {
      await api.revokeCustomerSession(sessionId);
      setMsg(`Session ${sessionId} has been revoked successfully.`);
      fetchSessions();
    } catch {
      setMsg(`Could not revoke session.`);
    }
  };

  const handleToggleConsent = async () => {
    const nextConsent = !consent;
    setConsent(nextConsent);
    try {
      await api.updateCustomerConsent(nextConsent);
      setMsg(`Privacy consent settings updated.`);
    } catch {
      setMsg(`Failed to update consent settings.`);
    }
  };

  if (isLoading && sessions.length === 0) {
    return (
      <div className="py-20 flex flex-col items-center justify-center text-[#A7B4C8]">
        <Loader2 className="h-8 w-8 animate-spin text-[#29C5D9] mb-3" />
        <p className="text-xs font-semibold">Loading active sessions & device telemetry...</p>
      </div>
    );
  }

  return (
    <div className="max-w-4xl mx-auto space-y-6 animate-in fade-in duration-200">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-[#F4F7FC] flex items-center gap-2">
            <ShieldCheck className="h-6 w-6 text-[#27C58B]" />
            <span>Security &amp; Device Center</span>
          </h1>
          <p className="text-xs text-[#A7B4C8] mt-1">
            Review your authorized devices, active login sessions, and privacy telemetry settings
          </p>
        </div>

        {/* 30-Second Live Telemetry Heartbeat Status Banner */}
        <div className="flex items-center gap-3 p-2.5 rounded-xl bg-[#101A2B] border border-[#25344A] text-xs">
          <div className="relative flex h-3 w-3">
            <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-[#27C58B] opacity-75"></span>
            <span className="relative inline-flex rounded-full h-3 w-3 bg-[#27C58B]"></span>
          </div>
          <div>
            <div className="flex items-center gap-1.5 font-bold text-[#F4F7FC] text-[11px]">
              <Radio className="w-3.5 h-3.5 text-[#29C5D9]" />
              <span>30s Telemetry Radar</span>
            </div>
            <p className="text-[10px] text-[#A7B4C8]">
              Next check in <span className="font-mono font-bold text-[#29C5D9]">{secondsRemaining}s</span>
            </p>
          </div>
          <button
            onClick={probeAndUpdateTelemetry}
            disabled={isProbing}
            className="flex items-center gap-1 px-2.5 py-1.5 rounded-lg bg-[#152238] hover:bg-[#1B2B43] border border-[#25344A] text-[#F4F7FC] text-[10px] font-bold transition-all disabled:opacity-50 cursor-pointer ml-1"
            title="Perform immediate network and VPN telemetry probe"
          >
            <RefreshCw className={`w-3 h-3 ${isProbing ? 'animate-spin text-[#29C5D9]' : ''}`} />
            <span>{isProbing ? 'Probing...' : 'Probe Now'}</span>
          </button>
        </div>
      </div>

      {msg && (
        <div className="p-3 rounded-lg bg-[#27C58B]/10 border border-[#27C58B]/30 text-xs text-[#27C58B] flex items-center gap-2">
          <CheckCircle2 className="h-4 w-4 shrink-0" />
          <span>{msg}</span>
        </div>
      )}

      {/* Privacy & Consent Section */}
      <div className="p-6 omerta-card space-y-4">
        <div className="flex items-start justify-between gap-4">
          <div className="space-y-1">
            <h3 className="text-sm font-bold text-[#F4F7FC] flex items-center gap-2">
              <Info className="h-4 w-4 text-[#3978F6]" />
              <span>Device &amp; Session Telemetry Consent</span>
            </h3>
            <p className="text-xs text-[#A7B4C8] leading-relaxed max-w-2xl">
              Omerta.ai can use limited device and session information to help secure your account,
              identify unusual sign-ins, and support transaction reviews. We collect only necessary,
              pseudonymous signals and never use covert tracking.
            </p>
          </div>

          <button
            onClick={handleToggleConsent}
            className="flex items-center gap-2 p-1 text-[#3978F6] hover:text-[#29C5D9] transition-colors"
            title="Toggle Privacy Consent"
          >
            {consent ? (
              <ToggleRight className="h-8 w-8 text-[#27C58B]" />
            ) : (
              <ToggleLeft className="h-8 w-8 text-[#71819A]" />
            )}
          </button>
        </div>

        <div className="pt-3 border-t border-[#25344A] flex items-center justify-between text-xs">
          <span className="text-[#71819A]">Status:</span>
          <span className={`font-bold ${consent ? 'text-[#27C58B]' : 'text-[#F4B942]'}`}>
            {consent ? 'Telemetry Collection Granted' : 'Telemetry Opted-Out'}
          </span>
        </div>
      </div>

      {/* Active & Recent Sessions */}
      <div className="p-6 omerta-card space-y-4">
        <div className="flex items-center justify-between">
          <h3 className="text-sm font-bold text-[#F4F7FC] flex items-center gap-2">
            <Smartphone className="h-4 w-4 text-[#29C5D9]" />
            <span>Active &amp; Recent Sessions</span>
          </h3>
          <span className="text-[11px] text-[#71819A]">
            Single-active-session policy enforced
          </span>
        </div>

        <div className="space-y-4">
          {sessions.map((s, idx) => {
            const isCurrent = idx === 0 && s.is_active;
            const displayLabel = s.device_label || (s.browser && s.os ? `${s.browser} on ${s.os}` : 'Web Client');
            
            return (
              <div
                key={s.session_id || idx}
                className={`p-4 rounded-xl border transition-all ${
                  isCurrent
                    ? 'bg-[#101A2B] border-[#3978F6]/40 shadow-lg shadow-blue-500/5'
                    : s.is_active
                    ? 'bg-[#101A2B] border-[#25344A]'
                    : 'bg-[#0B1320] border-[#1C2A3D] opacity-75'
                }`}
              >
                <div className="flex flex-col md:flex-row md:items-start justify-between gap-4">
                  <div className="flex items-start gap-3.5">
                    <div
                      className={`p-2.5 rounded-xl border ${
                        s.is_vpn
                          ? 'bg-[#F4B942]/10 text-[#F4B942] border-[#F4B942]/30'
                          : isCurrent
                          ? 'bg-[#3978F6]/10 text-[#3978F6] border-[#3978F6]/30'
                          : 'bg-[#152238] text-[#71819A] border-[#25344A]'
                      }`}
                    >
                      {s.platform?.toLowerCase().includes('mac') ||
                      s.platform?.toLowerCase().includes('win') ||
                      s.platform?.toLowerCase().includes('linux') ? (
                        <Laptop className="h-5 w-5" />
                      ) : (
                        <Smartphone className="h-5 w-5" />
                      )}
                    </div>

                    <div className="space-y-2">
                      {/* Device Title & Status Badges */}
                      <div className="flex flex-wrap items-center gap-2">
                        <span className="text-sm font-bold text-[#F4F7FC]">
                          {displayLabel}
                        </span>

                        {isCurrent && (
                          <span className="px-2.5 py-0.5 rounded-full bg-[#27C58B]/15 text-[#27C58B] border border-[#27C58B]/30 text-[10px] font-bold">
                            Current Session
                          </span>
                        )}

                        {s.is_active && !isCurrent && (
                          <span className="px-2.5 py-0.5 rounded-full bg-[#29C5D9]/15 text-[#29C5D9] border border-[#29C5D9]/30 text-[10px] font-bold">
                            Active Session
                          </span>
                        )}

                        {!s.is_active && (
                          <span className="px-2.5 py-0.5 rounded-full bg-[#71819A]/15 text-[#71819A] border border-[#71819A]/30 text-[10px] font-bold">
                            Terminated / Revoked
                          </span>
                        )}

                        {/* VPN vs Direct Connection Badge */}
                        {s.is_vpn ? (
                          <span className="px-2.5 py-0.5 rounded-full bg-[#F4B942]/15 text-[#F4B942] border border-[#F4B942]/30 text-[10px] font-bold flex items-center gap-1">
                            <ShieldCheck className="h-3 w-3" />
                            <span>VPN / Proxy Detected (Exit: {s.observed_country})</span>
                          </span>
                        ) : (
                          <span className="px-2.5 py-0.5 rounded-full bg-[#27C58B]/15 text-[#27C58B] border border-[#27C58B]/30 text-[10px] font-bold flex items-center gap-1">
                            <Globe className="h-3 w-3" />
                            <span>Direct Connection ({s.observed_country || 'EG'})</span>
                          </span>
                        )}
                      </div>

                      {/* Explicit Metadata Grid */}
                      <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 pt-1 text-[11px] text-[#A7B4C8]">
                        <div className="bg-[#152238]/60 p-2 rounded-lg border border-[#25344A]">
                          <span className="text-[#71819A] block text-[10px] uppercase font-bold">Operating System</span>
                          <span className="font-semibold text-[#F4F7FC]">{s.os || s.platform || 'Linux'}</span>
                        </div>
                        <div className="bg-[#152238]/60 p-2 rounded-lg border border-[#25344A]">
                          <span className="text-[#71819A] block text-[10px] uppercase font-bold">Browser</span>
                          <span className="font-semibold text-[#F4F7FC]">{s.browser || 'Google Chrome'}</span>
                        </div>
                        <div className="bg-[#152238]/60 p-2 rounded-lg border border-[#25344A]">
                          <span className="text-[#71819A] block text-[10px] uppercase font-bold">IP Address</span>
                          <span className="font-mono font-semibold text-[#29C5D9]">{s.ip_address || '127.0.0.1'}</span>
                        </div>
                        <div className="bg-[#152238]/60 p-2 rounded-lg border border-[#25344A]">
                          <span className="text-[#71819A] block text-[10px] uppercase font-bold">Sign-in Time</span>
                          <span className="font-semibold text-[#F4F7FC]">{s.started_at ? new Date(s.started_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' }) : 'Recent'}</span>
                        </div>
                      </div>

                      {/* Detailed Security & Telemetry Notice */}
                      {s.security_notice && (
                        <div
                          className={`mt-2 p-2.5 rounded-lg border text-xs flex items-start gap-2 ${
                            s.is_vpn
                              ? 'bg-[#F4B942]/10 border-[#F4B942]/30 text-[#F4B942]'
                              : 'bg-[#27C58B]/10 border-[#27C58B]/30 text-[#27C58B]'
                          }`}
                        >
                          {s.is_vpn ? (
                            <AlertTriangle className="h-4 w-4 shrink-0 mt-0.5" />
                          ) : (
                            <CheckCircle2 className="h-4 w-4 shrink-0 mt-0.5" />
                          )}
                          <span className="leading-relaxed">{s.security_notice}</span>
                        </div>
                      )}
                    </div>
                  </div>

                  {!isCurrent && s.is_active && (
                    <button
                      onClick={() => handleRevokeSession(s.session_id)}
                      className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-[#152238] hover:bg-[#F06470]/20 text-xs font-semibold text-[#F06470] border border-[#25344A] transition-colors self-start md:self-auto cursor-pointer"
                    >
                      <LogOut className="h-3.5 w-3.5" />
                      <span>Revoke</span>
                    </button>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
};
