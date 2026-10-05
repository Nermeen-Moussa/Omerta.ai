import React, { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import {
  Users,
  Search,
  RefreshCw,
  ChevronLeft,
  ChevronRight,
  UserPlus,
  ShieldCheck,
  CheckCircle2,
  Mail,
  Shield,
  Key,
  AlertCircle,
  FileCheck,
  DollarSign,
  ScrollText,
  PhoneCall,
  Unlock,
  AlertTriangle,
  Trash2,
  Sparkles,
  Bot,
  ShieldAlert,
  MessageSquare,
  ArrowUpRight,
} from 'lucide-react';
import { api } from '../api/client';
import type { CustomerItem } from '../types';
import { RiskBadge } from '../components/common/RiskBadge';
import { Modal } from '../components/common/Modal';

interface StaffUser {
  id: string;
  user_id: number;
  full_name: string;
  email: string;
  username: string;
  role: string;
  is_active: boolean;
  is_super_admin?: boolean;
  can_delete?: boolean;
  privileges: string[];
  created_at: string | null;
}

const PRIVILEGE_DEFINITIONS: Record<string, { label: string; icon: any; desc: string }> = {
  manage_users: {
    label: 'User Management',
    icon: Users,
    desc: 'Activate, suspend, and manage customer profiles',
  },
  review_flagged_transactions: {
    label: 'Flagged Reviews',
    icon: ShieldCheck,
    desc: 'Review transactions exceeding risk threshold (> 40.00)',
  },
  adjust_balances: {
    label: 'Balance Adjustments',
    icon: DollarSign,
    desc: 'Execute ledger-backed demo balance adjustments',
  },
  view_audit_logs: {
    label: 'Audit & Telemetry',
    icon: ScrollText,
    desc: 'Inspect security sessions and immutable audit events',
  },
  export_reports: {
    label: 'Compliance Reports',
    icon: FileCheck,
    desc: 'Generate & export regulatory SAR / AML reports',
  },
  manage_staff: {
    label: 'Staff Administration',
    icon: Key,
    desc: 'Create and assign privileges to sub-admin accounts',
  },
};

export const CustomersPage: React.FC = () => {
  const [activeTab, setActiveTab] = useState<'customers' | 'problem_customers' | 'staff'>('customers');

  // Customers state
  const [customers, setCustomers] = useState<CustomerItem[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState('');
  const [typeFilter, setTypeFilter] = useState('');
  const [riskFilter, setRiskFilter] = useState('');
  const [page, setPage] = useState(1);
  const [selectedCustomer, setSelectedCustomer] = useState<any | null>(null);

  // Problem customers state
  const [problemCustomers, setProblemCustomers] = useState<any[]>([]);
  const [loadingProblems, setLoadingProblems] = useState(false);
  const [problemSearch, setProblemSearch] = useState('');
  const [callModalCust, setCallModalCust] = useState<any | null>(null);
  const [emailModalCust, setEmailModalCust] = useState<any | null>(null);
  const [emailSubject, setEmailSubject] = useState('Omerta.ai Security Clearance: Action Required');
  const [emailBody, setEmailBody] = useState('');
  const [emailSubmitting, setEmailSubmitting] = useState(false);
  const [custAgenticModal, setCustAgenticModal] = useState<any | null>(null);
  const [custAgenticLoading, setCustAgenticLoading] = useState(false);

  // Staff state
  const [staffList, setStaffList] = useState<StaffUser[]>([]);
  const [staffLoading, setStaffLoading] = useState(false);
  const [createStaffOpen, setCreateStaffOpen] = useState(false);
  const [staffSuccess, setStaffSuccess] = useState<string | null>(null);
  const [staffError, setStaffError] = useState<string | null>(null);
  const [isSubmittingStaff, setIsSubmittingStaff] = useState(false);

  // New staff form data
  const [newStaff, setNewStaff] = useState({
    full_name: '',
    email: '',
    username: '',
    password: '',
    role: 'ADMINISTRATOR',
    privileges: ['manage_users', 'review_flagged_transactions', 'adjust_balances', 'view_audit_logs', 'export_reports', 'manage_staff'],
  });

  const fetchCustomers = async () => {
    setLoading(true);
    try {
      const res = await api.getCustomers({
        search,
        customer_type: typeFilter,
        risk_level: riskFilter,
        page,
        page_size: 20,
      });
      setCustomers(res.items || []);
      setTotal(res.total || 0);
    } catch (err) {
      console.error('Failed to load customers', err);
    } finally {
      setLoading(false);
    }
  };

  const fetchProblemCustomers = async () => {
    setLoadingProblems(true);
    try {
      const res = await api.getProblemCustomers();
      setProblemCustomers(res || []);
    } catch (err) {
      console.error('Failed to load problem customers', err);
    } finally {
      setLoadingProblems(false);
    }
  };

  const fetchStaff = async () => {
    setStaffLoading(true);
    try {
      const res = await api.getAdminStaff();
      setStaffList(res || []);
    } catch {
      setStaffList([
        {
          id: 'USR-ADMIN',
          user_id: 1,
          full_name: 'Dr. Sarah Al-Rashid',
          email: 'admin@omerta.ai',
          username: 'admin@omerta.ai',
          role: 'ADMINISTRATOR',
          is_active: true,
          is_super_admin: true,
          can_delete: false,
          privileges: ['manage_users', 'review_flagged_transactions', 'adjust_balances', 'view_audit_logs', 'export_reports', 'manage_staff'],
          created_at: new Date().toISOString(),
        },
        {
          id: 'USR-ANALYST',
          user_id: 2,
          full_name: 'Tariq Mansour',
          email: 'analyst@omerta.ai',
          username: 'analyst@omerta.ai',
          role: 'FRAUD_ANALYST',
          is_active: true,
          is_super_admin: false,
          can_delete: true,
          privileges: ['review_flagged_transactions', 'view_audit_logs', 'export_reports'],
          created_at: new Date().toISOString(),
        },
        {
          id: 'USR-INVESTIGATOR',
          user_id: 3,
          full_name: 'Laila El-Kady',
          email: 'investigator@omerta.ai',
          username: 'investigator@omerta.ai',
          role: 'SENIOR_INVESTIGATOR',
          is_active: true,
          is_super_admin: false,
          can_delete: true,
          privileges: ['manage_users', 'review_flagged_transactions', 'view_audit_logs', 'export_reports'],
          created_at: new Date().toISOString(),
        },
      ]);
    } finally {
      setStaffLoading(false);
    }
  };

  useEffect(() => {
    if (activeTab === 'customers') {
      fetchCustomers();
    } else if (activeTab === 'problem_customers') {
      fetchProblemCustomers();
    } else {
      fetchStaff();
    }
  }, [activeTab, page, typeFilter, riskFilter]);

  const handleSearchSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    setPage(1);
    fetchCustomers();
  };

  const handleOpen360 = async (c: CustomerItem) => {
    try {
      const res = await api.getCustomer360(c.external_id);
      setSelectedCustomer(res);
    } catch (err) {
      console.error('Failed to load customer 360', err);
    }
  };

  const handleResolveRisk = async (customerId: string, name: string) => {
    if (!confirm(`Are you sure you want to resolve risk and unlock account for customer ${name}? This will reset risk to LOW, clear password failures, and reactivate banking access.`)) {
      return;
    }
    try {
      await api.resolveCustomerRisk(customerId, 'Identity confirmed via analyst direct verification. Account risk cleared.');
      setStaffSuccess(`Risk successfully cleared for ${name}. Account restored to LOW risk.`);
      fetchProblemCustomers();
    } catch (err: any) {
      alert(err.message || 'Failed to resolve customer risk.');
    }
  };

  const handleOpenCallModal = (c: any) => {
    setCallModalCust(c);
  };

  const handleOpenEmailModal = (c: any) => {
    setEmailModalCust(c);
    setEmailSubject(`Omerta.ai Security Clearance: Action Required for ${c.name}`);
    setEmailBody(
      `Dear ${c.name},\n\nWe detected a security event on your Omerta.ai account (${c.omerta_user_number}): "${c.primary_reason}".\n\nOur compliance and security team is currently reviewing your account. Please confirm your recent activity or reach out to our customer operations hotline at +20 2 3333 4444.\n\nSincerely,\nOmerta.ai Security & Risk Operations`
    );
  };

  const handleSendEmailNotice = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!emailModalCust) return;
    setEmailSubmitting(true);
    try {
      await api.notifyCustomer(emailModalCust.customer_id, {
        channel: 'EMAIL',
        subject: emailSubject,
        message: emailBody,
      });
      setStaffSuccess(`Security notice sent to ${emailModalCust.name} (${emailModalCust.email}).`);
      setEmailModalCust(null);
    } catch (err: any) {
      alert(err.message || 'Failed to send security notice.');
    } finally {
      setEmailSubmitting(false);
    }
  };

  const handleOpenCustomerAgenticModal = async (c: any) => {
    setCustAgenticLoading(true);
    setCustAgenticModal({
      customer_id: c.customer_id,
      omerta_user_number: c.omerta_user_number,
      name: c.name,
      email: c.email,
      phone: c.phone,
      risk_level: c.risk_level,
      status: c.status,
    });
    try {
      const summary = await api.getProblemCustomerAgenticSummary(c.customer_id);
      setCustAgenticModal(summary);
    } catch {
      setCustAgenticModal({
        customer_id: c.customer_id,
        omerta_user_number: c.omerta_user_number,
        name: c.name,
        email: c.email,
        phone: c.phone,
        risk_level: c.risk_level,
        status: c.status,
        forensic_findings: [
          {
            category: 'AUTHENTICATION_RISK',
            severity: 'CRITICAL',
            finding: c.primary_reason || 'Excessive verification failures observed.',
            action_required: 'Direct identity verification required before unlocking.',
          },
        ],
        agentic_agents: [
          { agent: 'IdentityVerificationAgent', verdict: 'FLAGGED' },
          { agent: 'NetworkTelemetryAgent', verdict: 'EVALUATED' },
          { agent: 'GeographicVelocityAgent', verdict: 'ACTIVE' },
          { agent: 'ComplianceResolutionAgent', verdict: 'ACTION_REQUIRED' },
        ],
        recommended_resolution: "Confirm customer identity by phone, then click 'Resolve & Unlock'.",
      });
    } finally {
      setCustAgenticLoading(false);
    }
  };

  const handleDeleteStaff = async (userId: string, fullName: string) => {
    if (!confirm(`Are you sure you want to revoke and delete staff account for ${fullName}? This will immediately terminate all active sessions.`)) {
      return;
    }
    try {
      await api.deleteAdminStaff(userId);
      setStaffSuccess(`Staff account for '${fullName}' has been revoked and deactivated.`);
      fetchStaff();
    } catch (err: any) {
      alert(err.message || 'Failed to revoke staff account.');
    }
  };

  const handleTogglePrivilege = (priv: string) => {
    setNewStaff((prev) => {
      const exists = prev.privileges.includes(priv);
      return {
        ...prev,
        privileges: exists ? prev.privileges.filter((p) => p !== priv) : [...prev.privileges, priv],
      };
    });
  };

  const handleCreateStaff = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newStaff.full_name || !newStaff.email || !newStaff.username || !newStaff.password) {
      setStaffError('Please complete all required fields.');
      return;
    }
    if (newStaff.password.length < 8) {
      setStaffError('Password must be at least 8 characters long.');
      return;
    }

    setIsSubmittingStaff(true);
    setStaffError(null);
    setStaffSuccess(null);

    try {
      await api.createAdminStaff(newStaff);
      setStaffSuccess(`Staff account '${newStaff.full_name}' (${newStaff.role}) created successfully.`);
      setCreateStaffOpen(false);
      setNewStaff({
        full_name: '',
        email: '',
        username: '',
        password: '',
        role: 'ADMINISTRATOR',
        privileges: ['manage_users', 'review_flagged_transactions', 'adjust_balances', 'view_audit_logs', 'export_reports', 'manage_staff'],
      });
      fetchStaff();
    } catch (err: any) {
      setStaffError(err.message || 'Failed to create staff account.');
    } finally {
      setIsSubmittingStaff(false);
    }
  };

  const filteredProblems = problemCustomers.filter(
    (c) =>
      c.name.toLowerCase().includes(problemSearch.toLowerCase()) ||
      c.omerta_user_number.toLowerCase().includes(problemSearch.toLowerCase()) ||
      c.email.toLowerCase().includes(problemSearch.toLowerCase()) ||
      c.phone.includes(problemSearch)
  );

  return (
    <div className="space-y-6 animate-in fade-in duration-200">
      {/* Tab Switcher Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-[#F4F7FC] flex items-center gap-2">
            <Users className="h-6 w-6 text-[#3978F6]" />
            <span>Platform User &amp; Staff Administration</span>
          </h1>
          <p className="text-xs text-[#A7B4C8] mt-1">
            Super Administrator controls: Manage monitored customers, problem account lockouts, and provision Admin/Investigator/Analyst/Auditor staff
          </p>
        </div>

        {/* Tab Buttons */}
        <div className="flex items-center gap-2 p-1 rounded-xl bg-[#101A2B] border border-[#25344A]">
          <button
            onClick={() => setActiveTab('customers')}
            className={`px-4 py-2 rounded-lg text-xs font-bold transition-all cursor-pointer ${
              activeTab === 'customers'
                ? 'bg-[#3978F6] text-[#F4F7FC] shadow-sm'
                : 'text-[#A7B4C8] hover:text-[#F4F7FC]'
            }`}
          >
            Customer Accounts ({total})
          </button>

          <button
            onClick={() => setActiveTab('problem_customers')}
            className={`px-4 py-2 rounded-lg text-xs font-bold transition-all cursor-pointer flex items-center gap-1.5 ${
              activeTab === 'problem_customers'
                ? 'bg-[#F4B942] text-slate-950 shadow-sm'
                : 'text-[#A7B4C8] hover:text-[#F4F7FC]'
            }`}
          >
            <AlertTriangle className="w-3.5 h-3.5 text-amber-500" />
            <span>Problem Accounts ({problemCustomers.length})</span>
          </button>

          <button
            onClick={() => setActiveTab('staff')}
            className={`px-4 py-2 rounded-lg text-xs font-bold transition-all cursor-pointer flex items-center gap-1.5 ${
              activeTab === 'staff'
                ? 'bg-[#3978F6] text-[#F4F7FC] shadow-sm'
                : 'text-[#A7B4C8] hover:text-[#F4F7FC]'
            }`}
          >
            <ShieldCheck className="w-3.5 h-3.5" />
            <span>Staff &amp; Admins ({staffList.length})</span>
          </button>
        </div>
      </div>

      {/* SUCCESS TOAST */}
      {staffSuccess && (
        <div className="p-4 rounded-xl bg-[#27C58B]/15 border border-[#27C58B]/40 text-xs text-[#27C58B] flex items-center justify-between">
          <div className="flex items-center gap-2">
            <CheckCircle2 className="w-4 h-4 shrink-0" />
            <span className="font-semibold">{staffSuccess}</span>
          </div>
          <button onClick={() => setStaffSuccess(null)} className="text-xs hover:underline font-bold cursor-pointer">
            Dismiss
          </button>
        </div>
      )}

      {/* TAB 1: CUSTOMER DIRECTORY */}
      {activeTab === 'customers' && (
        <div className="space-y-4">
          {/* Search & Filters Toolbar */}
          <div className="p-4 rounded-xl bg-[#101A2B] border border-[#25344A] flex flex-col md:flex-row gap-3 items-center justify-between shadow-lg">
            <form onSubmit={handleSearchSubmit} className="relative w-full md:w-80">
              <input
                type="text"
                placeholder="Search customers (Name, ID, Omerta #)..."
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                className="w-full pl-9 pr-4 py-2 bg-[#080D19] border border-[#25344A] rounded-xl text-xs text-[#F4F7FC] placeholder-[#71819A] focus:outline-none focus:border-[#3978F6]"
              />
              <Search className="absolute left-3 top-2.5 h-4 w-4 text-[#71819A]" />
            </form>

            <div className="flex items-center gap-2 w-full md:w-auto overflow-x-auto">
              <select
                value={typeFilter}
                onChange={(e) => {
                  setTypeFilter(e.target.value);
                  setPage(1);
                }}
                className="px-3 py-2 bg-[#080D19] border border-[#25344A] rounded-xl text-xs text-[#F4F7FC] focus:outline-none focus:border-[#3978F6]"
              >
                <option value="">All Customer Types</option>
                <option value="INDIVIDUAL">Individual</option>
                <option value="BUSINESS">Business</option>
              </select>

              <select
                value={riskFilter}
                onChange={(e) => {
                  setRiskFilter(e.target.value);
                  setPage(1);
                }}
                className="px-3 py-2 bg-[#080D19] border border-[#25344A] rounded-xl text-xs text-[#F4F7FC] focus:outline-none focus:border-[#3978F6]"
              >
                <option value="">All Risk Levels</option>
                <option value="LOW">Low Risk</option>
                <option value="MODERATE">Moderate Risk</option>
                <option value="HIGH">High Risk</option>
                <option value="CRITICAL">Critical Risk</option>
              </select>

              <button
                onClick={fetchCustomers}
                className="p-2 rounded-xl bg-[#080D19] border border-[#25344A] hover:bg-[#152238] text-[#F4F7FC] cursor-pointer"
                title="Refresh Table"
              >
                <RefreshCw className={`h-4 w-4 ${loading ? 'animate-spin text-[#3978F6]' : ''}`} />
              </button>
            </div>
          </div>

          {/* Customers Table */}
          <div className="bg-[#101A2B] border border-[#25344A] rounded-xl overflow-hidden shadow-xl">
            <div className="overflow-x-auto">
              <table className="w-full text-left text-xs">
                <thead className="bg-[#080D19] text-[#A7B4C8] border-b border-[#25344A] uppercase text-[10px] tracking-wider font-bold">
                  <tr>
                    <th className="py-3.5 px-4">Customer Name &amp; Contact</th>
                    <th className="py-3.5 px-4">Omerta User #</th>
                    <th className="py-3.5 px-4">Type</th>
                    <th className="py-3.5 px-4">Admin Risk Rating</th>
                    <th className="py-3.5 px-4">Total EGP Balance</th>
                    <th className="py-3.5 px-4">Declared Country</th>
                    <th className="py-3.5 px-4 text-right">Actions</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-[#25344A]">
                  {loading ? (
                    <tr>
                      <td colSpan={7} className="py-12 text-center text-[#A7B4C8]">
                        <RefreshCw className="h-6 w-6 animate-spin mx-auto text-[#3978F6] mb-2" />
                        <span>Loading customer accounts...</span>
                      </td>
                    </tr>
                  ) : customers.length === 0 ? (
                    <tr>
                      <td colSpan={7} className="py-12 text-center text-[#A7B4C8]">
                        No customers matching search criteria found.
                      </td>
                    </tr>
                  ) : (
                    customers.map((c) => (
                      <tr key={c.id} className="hover:bg-[#152238]/60 transition-colors">
                        <td className="py-3.5 px-4">
                          <div className="font-bold text-[#F4F7FC]">{c.name}</div>
                          <div className="text-[11px] text-[#71819A] flex items-center gap-1">
                            <Mail className="w-3 h-3" />
                            <span>{c.email}</span>
                          </div>
                        </td>
                        <td className="py-3.5 px-4 font-mono font-bold text-[#29C5D9]">
                          {c.omerta_user_number}
                        </td>
                        <td className="py-3.5 px-4">
                          <span className="px-2 py-0.5 rounded text-[10px] font-bold bg-[#080D19] border border-[#25344A] text-[#A7B4C8]">
                            {c.customer_type}
                          </span>
                        </td>
                        <td className="py-3.5 px-4">
                          <RiskBadge level={c.risk_level} />
                        </td>
                        <td className="py-3.5 px-4 font-mono font-bold text-[#F4F7FC]">
                          {(c.total_balance ?? 0).toLocaleString(undefined, { minimumFractionDigits: 2 })} EGP
                        </td>
                        <td className="py-3.5 px-4 text-[#A7B4C8]">{c.country}</td>
                        <td className="py-3.5 px-4 text-right">
                          <button
                            onClick={() => handleOpen360(c)}
                            className="px-3 py-1.5 rounded-lg bg-[#152238] hover:bg-[#3978F6] text-xs font-bold text-[#F4F7FC] border border-[#25344A] transition-all cursor-pointer"
                          >
                            Customer 360°
                          </button>
                        </td>
                      </tr>
                    ))
                  )}
                </tbody>
              </table>
            </div>

            {/* Pagination footer */}
            <div className="p-4 border-t border-[#25344A] flex items-center justify-between text-xs text-[#A7B4C8]">
              <span>Showing {customers.length} of {total} registered customers</span>
              <div className="flex items-center gap-2">
                <button
                  disabled={page <= 1}
                  onClick={() => setPage(page - 1)}
                  className="p-1.5 rounded-lg bg-[#101A2B] hover:bg-[#152238] border border-[#25344A] text-[#F4F7FC] disabled:opacity-30 cursor-pointer"
                >
                  <ChevronLeft className="h-4 w-4" />
                </button>
                <span className="font-mono px-2">Page {page}</span>
                <button
                  disabled={page * 20 >= total}
                  onClick={() => setPage(page + 1)}
                  className="p-1.5 rounded-lg bg-[#101A2B] hover:bg-[#152238] border border-[#25344A] text-[#F4F7FC] disabled:opacity-30 cursor-pointer"
                >
                  <ChevronRight className="h-4 w-4" />
                </button>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* TAB 2: PROBLEM CUSTOMERS & LOCKOUT HUB */}
      {activeTab === 'problem_customers' && (
        <div className="space-y-4">
          <div className="p-4 rounded-xl bg-gradient-to-r from-amber-500/10 via-rose-500/10 to-transparent border border-amber-500/20 flex items-start gap-3 shadow-xs">
            <AlertTriangle className="h-5 w-5 text-amber-500 shrink-0 mt-0.5" />
            <div className="text-xs space-y-1">
              <p className="font-bold text-[#F4F7FC]">Customer Security &amp; Lockout Resolution Center</p>
              <p className="text-[#A7B4C8] leading-relaxed">
                Directly communicate with customers locked out due to 3 failed password attempts, VPN transfer restrictions, or high risk scores. Verify customer identity, dial their phone, dispatch security emails, and manually clear their risk back to active status.
              </p>
            </div>
          </div>

          {/* Search bar */}
          <div className="flex items-center justify-between gap-4">
            <div className="relative flex-1 max-w-md">
              <input
                type="text"
                placeholder="Search problem customers by name, Omerta #, phone, or email..."
                value={problemSearch}
                onChange={(e) => setProblemSearch(e.target.value)}
                className="w-full pl-3 pr-4 py-2 bg-[#101A2B] border border-[#25344A] rounded-xl text-xs text-[#F4F7FC] placeholder-[#71819A] focus:outline-none focus:border-[#F4B942]"
              />
            </div>
            <span className="text-xs font-bold text-[#A7B4C8] font-mono">
              {filteredProblems.length} Problem Accounts
            </span>
          </div>

          {/* Problem Customers List */}
          <div className="space-y-3">
            {loadingProblems ? (
              <div className="py-12 text-center text-[#A7B4C8]">
                <RefreshCw className="h-6 w-6 animate-spin mx-auto mb-2 text-[#F4B942]" />
                <span>Loading problem customers...</span>
              </div>
            ) : filteredProblems.length === 0 ? (
              <div className="py-12 text-center text-[#A7B4C8] bg-[#101A2B] border border-[#25344A] rounded-xl p-6">
                <CheckCircle2 className="h-8 w-8 text-[#27C58B] mx-auto mb-2" />
                <p className="text-[#F4F7FC] font-bold text-base">No problem customers currently flagged!</p>
                <p className="text-xs text-[#71819A] mt-1">All customer accounts are in good standing with zero lockouts.</p>
              </div>
            ) : (
              filteredProblems.map((c) => (
                <div
                  key={c.customer_id}
                  className="p-4 border border-amber-500/30 hover:border-amber-500/60 bg-[#101A2B] rounded-xl transition-all flex flex-col md:flex-row md:items-center justify-between gap-4 shadow-lg"
                >
                  <div className="space-y-2 flex-1">
                    <div className="flex items-center gap-3 flex-wrap">
                      <div className="h-8 w-8 rounded-full bg-amber-500/20 text-amber-400 flex items-center justify-center font-bold text-sm">
                        {c.name.charAt(0)}
                      </div>
                      <div className="flex-1">
                        <div className="flex items-center gap-2 flex-wrap">
                          <span className="font-bold text-[#F4F7FC] text-sm">{c.name}</span>
                          <span className="font-mono text-xs font-bold text-[#29C5D9]">{c.omerta_user_number}</span>
                          <RiskBadge level={c.risk_level} size="sm" />
                          {c.transfer_blocked && (
                            <span className="px-2 py-0.5 rounded bg-rose-500/15 text-rose-400 font-mono text-[10px] font-bold border border-rose-500/30 flex items-center gap-1">
                              🔒 Transfer Blocked (3 Strikes)
                            </span>
                          )}
                        </div>
                        <div className="text-xs text-[#71819A] flex items-center gap-3 mt-0.5 flex-wrap">
                          <span className="flex items-center gap-1 font-mono text-[#F4F7FC]">
                            📞 {c.phone}
                          </span>
                          <span>•</span>
                          <span className="flex items-center gap-1 text-[#F4F7FC]">
                            ✉️ {c.email}
                          </span>
                          <span>•</span>
                          <span className="font-mono font-bold text-[#27C58B]">
                            {c.total_balance_egp?.toLocaleString(undefined, { minimumFractionDigits: 2 })} EGP
                          </span>
                          {c.national_id_number && (
                            <>
                              <span>•</span>
                              <span className="font-mono text-xs text-[#29C5D9] bg-[#29C5D9]/10 px-1.5 py-0.5 rounded border border-[#29C5D9]/30">
                                ID: {c.national_id_number}
                              </span>
                            </>
                          )}
                        </div>
                      </div>
                    </div>

                    {/* Prominent Customer Issue & Ticket Banner */}
                    <Link
                      to={`/admin/support-cases?search=${encodeURIComponent(c.name || c.omerta_user_number || '')}`}
                      className="block p-2.5 rounded-lg bg-amber-500/10 hover:bg-amber-500/15 border border-amber-500/30 hover:border-amber-500/50 transition-all text-xs space-y-1 group cursor-pointer"
                      title="Click to open full chat conversation & document review"
                    >
                      <div className="flex items-center justify-between gap-2">
                        <span className="text-[10px] uppercase font-bold text-amber-400 flex items-center gap-1.5">
                          <AlertTriangle className="w-3.5 h-3.5" />
                          <span>Customer Issue &amp; Support Ticket:</span>
                        </span>
                        <span className="text-[10px] text-[#29C5D9] font-bold group-hover:underline flex items-center gap-1">
                          <span>Open Chat &amp; Case</span>
                          <ArrowUpRight className="w-3 h-3" />
                        </span>
                      </div>
                      <p className="font-semibold text-white text-xs leading-snug">
                        {c.customer_issue || c.primary_reason}
                      </p>
                      {c.ticket_number && (
                        <div className="flex items-center gap-2 pt-0.5 text-[11px] text-[#A7B4C8]">
                          <span className="font-mono text-[#29C5D9] font-bold">Ticket #{c.ticket_number}</span>
                          {c.ticket_status && (
                            <span className="px-1.5 py-0.2 rounded bg-[#080D19] border border-[#25344A] text-[#F4F7FC] text-[10px]">
                              Status: {c.ticket_status}
                            </span>
                          )}
                          {c.has_uploaded_id && (
                            <span className="px-1.5 py-0.2 rounded bg-[#27C58B]/20 text-[#27C58B] text-[10px] font-bold border border-[#27C58B]/30">
                              📄 National ID Attached
                            </span>
                          )}
                        </div>
                      )}
                    </Link>

                    {c.recent_audit_events && c.recent_audit_events.length > 0 && (
                      <div className="bg-[#080D19] p-2 rounded-lg border border-[#25344A] text-[11px] space-y-0.5">
                        <span className="text-[9px] text-[#71819A] uppercase font-bold tracking-wider">Latest Security Event:</span>
                        <p className="text-[#F4F7FC] font-mono text-[10px]">
                          [{c.recent_audit_events[0].event_type}] — {c.recent_audit_events[0].metadata?.description || 'Security threshold flagged'} ({new Date(c.recent_audit_events[0].created_at).toLocaleTimeString()})
                        </p>
                      </div>
                    )}
                  </div>

                  {/* Customer Contact & Resolution Actions */}
                  <div className="flex items-center gap-2 self-end md:self-center flex-wrap">
                    {/* Direct Support Chat & ID Cases */}
                    <Link
                      to={`/admin/support-cases?search=${encodeURIComponent(c.name || c.omerta_user_number || '')}`}
                      className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-cyan-600 hover:bg-cyan-500 text-slate-950 font-black text-xs transition-colors shadow-xs"
                      title="Open live support chat, view customer tickets & review National ID verification"
                    >
                      <MessageSquare className="h-3.5 w-3.5" />
                      <span>Support Chat &amp; Cases</span>
                    </Link>

                    <button
                      onClick={() => handleOpenCallModal(c)}
                      className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-[#3978F6] hover:bg-[#3978F6]/90 text-white text-xs font-bold transition-colors shadow-xs cursor-pointer"
                      title="Initiate phone call verification"
                    >
                      <PhoneCall className="h-3.5 w-3.5" />
                      <span>Call Customer</span>
                    </button>

                    <button
                      onClick={() => handleOpenEmailModal(c)}
                      className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-[#152238] hover:bg-[#1B2B43] text-[#F4F7FC] border border-[#25344A] text-xs font-bold transition-colors shadow-xs cursor-pointer"
                      title="Dispatch security notification email"
                    >
                      <Mail className="h-3.5 w-3.5" />
                      <span>Send Notice</span>
                    </button>

                    <button
                      onClick={() => handleOpenCustomerAgenticModal(c)}
                      className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-gradient-to-r from-purple-950 to-indigo-950 border border-purple-500/40 hover:border-purple-400 text-purple-300 hover:text-white text-xs font-bold transition-colors shadow-xs cursor-pointer"
                      title="View Autonomous Multi-Agent Forensic Investigation Report"
                    >
                      <Sparkles className="h-3.5 w-3.5 text-purple-400" />
                      <span>Agentic Report</span>
                    </button>

                    <button
                      onClick={() => handleResolveRisk(c.customer_id, c.name)}
                      className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-[#27C58B] hover:bg-[#27C58B]/90 text-slate-950 text-xs font-bold transition-colors shadow-xs cursor-pointer"
                      title="Manually clear risk rating to LOW and restore active status"
                    >
                      <Unlock className="h-3.5 w-3.5" />
                      <span>Resolve &amp; Unlock</span>
                    </button>
                  </div>
                </div>
              ))
            )}
          </div>
        </div>
      )}

      {/* TAB 3: SUB-ADMIN & STAFF ACCOUNTS */}
      {activeTab === 'staff' && (
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <div>
              <h2 className="text-base font-bold text-[#F4F7FC] flex items-center gap-2">
                <Shield className="w-5 h-5 text-[#3978F6]" />
                <span>Authorized Administrative &amp; Operational Staff</span>
              </h2>
              <p className="text-xs text-[#A7B4C8]">
                Super Administrator control: Provision co-administrators, fraud analysts, senior investigators, and compliance auditors
              </p>
            </div>

            <button
              onClick={() => {
                setStaffError(null);
                setCreateStaffOpen(true);
              }}
              className="px-4 py-2.5 rounded-xl bg-[#3978F6] hover:bg-[#3978F6]/90 text-xs font-bold text-[#F4F7FC] flex items-center gap-2 transition-all shadow-md shadow-blue-500/20 cursor-pointer"
            >
              <UserPlus className="w-4 h-4" />
              <span>Create Administrator / Staff</span>
            </button>
          </div>

          {/* Staff Table */}
          <div className="bg-[#101A2B] border border-[#25344A] rounded-xl overflow-hidden shadow-xl">
            <div className="overflow-x-auto">
              <table className="w-full text-left text-xs">
                <thead className="bg-[#080D19] text-[#A7B4C8] border-b border-[#25344A] uppercase text-[10px] tracking-wider font-bold">
                  <tr>
                    <th className="py-3.5 px-4">Staff Member</th>
                    <th className="py-3.5 px-4">Username &amp; ID</th>
                    <th className="py-3.5 px-4">Role</th>
                    <th className="py-3.5 px-4">Assigned Privileges</th>
                    <th className="py-3.5 px-4">Status</th>
                    <th className="py-3.5 px-4 text-right">Admin Actions</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-[#25344A]">
                  {staffLoading ? (
                    <tr>
                      <td colSpan={6} className="py-12 text-center text-[#A7B4C8]">
                        <RefreshCw className="h-6 w-6 animate-spin mx-auto text-[#3978F6] mb-2" />
                        <span>Loading staff roster...</span>
                      </td>
                    </tr>
                  ) : (
                    staffList.map((st) => (
                      <tr key={st.id} className="hover:bg-[#152238]/60 transition-colors">
                        <td className="py-3.5 px-4">
                          <div className="font-bold text-[#F4F7FC]">{st.full_name}</div>
                          <div className="text-[11px] text-[#71819A] flex items-center gap-1">
                            <Mail className="w-3 h-3" />
                            <span>{st.email}</span>
                          </div>
                        </td>
                        <td className="py-3.5 px-4 font-mono">
                          <div className="font-bold text-[#29C5D9]">{st.username}</div>
                          <div className="text-[10px] text-[#71819A]">{st.id}</div>
                        </td>
                        <td className="py-3.5 px-4">
                          <span
                            className={`px-2.5 py-1 rounded-full text-[10px] font-bold border ${
                              st.role === 'ADMINISTRATOR'
                                ? 'bg-[#3978F6]/15 border-[#3978F6]/40 text-[#3978F6]'
                                : st.role === 'SUB_ADMINISTRATOR'
                                ? 'bg-[#29C5D9]/15 border-[#29C5D9]/40 text-[#29C5D9]'
                                : st.role === 'FRAUD_ANALYST'
                                ? 'bg-[#F4B942]/15 border-[#F4B942]/40 text-[#F4B942]'
                                : 'bg-[#27C58B]/15 border-[#27C58B]/40 text-[#27C58B]'
                            }`}
                          >
                            {st.role.replace('_', ' ')}
                          </span>
                        </td>
                        <td className="py-3.5 px-4">
                          <div className="flex flex-wrap gap-1.5 max-w-md">
                            {st.privileges.map((p) => {
                              const def = PRIVILEGE_DEFINITIONS[p] || { label: p };
                              return (
                                <span
                                  key={p}
                                  className="px-2 py-0.5 rounded text-[10px] font-semibold bg-[#080D19] border border-[#25344A] text-[#A7B4C8]"
                                >
                                  {def.label}
                                </span>
                              );
                            })}
                          </div>
                        </td>
                        <td className="py-3.5 px-4">
                          <span
                            className={`px-2.5 py-0.5 rounded-full text-[10px] font-bold border ${
                              st.is_active
                                ? 'bg-[#27C58B]/15 border-[#27C58B]/40 text-[#27C58B]'
                                : 'bg-[#F06470]/15 border-[#F06470]/40 text-[#F06470]'
                            }`}
                          >
                            {st.is_active ? 'ACTIVE' : 'SUSPENDED'}
                          </span>
                        </td>
                        <td className="py-3.5 px-4 text-right">
                          {st.is_super_admin || st.username === 'admin' || st.email === 'admin@omerta.ai' ? (
                            <span className="px-2.5 py-1 rounded-lg bg-[#3978F6]/20 border border-[#3978F6]/40 text-[#29C5D9] text-[10px] font-bold inline-flex items-center gap-1">
                              🔒 Root Super Admin (Protected)
                            </span>
                          ) : (
                            <button
                              onClick={() => handleDeleteStaff(st.id, st.full_name)}
                              className="flex items-center gap-1 px-2.5 py-1 rounded-lg bg-rose-500/15 hover:bg-rose-500/30 text-rose-400 border border-rose-500/30 text-[10px] font-bold transition-all cursor-pointer ml-auto"
                              title="Revoke and delete staff credentials"
                            >
                              <Trash2 className="w-3 h-3" />
                              <span>Revoke Staff</span>
                            </button>
                          )}
                        </td>
                      </tr>
                    ))
                  )}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      )}

      {/* MODAL: DIRECT CALL CUSTOMER */}
      {callModalCust && (
        <Modal isOpen={!!callModalCust} onClose={() => setCallModalCust(null)} title={`Call Customer: ${callModalCust.name}`}>
          <div className="space-y-4">
            <div className="p-4 rounded-xl bg-blue-500/10 border border-blue-500/20 flex items-start gap-3 text-xs text-blue-300">
              <PhoneCall className="h-5 w-5 text-blue-400 shrink-0 mt-0.5" />
              <div>
                <p className="font-bold text-white">Direct Phone Verification Line</p>
                <p className="text-slate-300 mt-0.5">
                  Confirm the customer's identity, verify their recent transaction attempts, and advise them on secure password updates.
                </p>
              </div>
            </div>

            <div className="space-y-3 p-4 bg-slate-900 rounded-xl border border-slate-800 text-xs">
              <div className="flex justify-between items-center py-1 border-b border-slate-800">
                <span className="text-slate-400 font-medium">Customer Name</span>
                <span className="text-white font-bold">{callModalCust.name}</span>
              </div>
              <div className="flex justify-between items-center py-1 border-b border-slate-800">
                <span className="text-slate-400 font-medium">Registered Mobile</span>
                <span className="font-mono text-emerald-400 font-bold text-sm">{callModalCust.phone}</span>
              </div>
              <div className="flex justify-between items-center py-1 border-b border-slate-800">
                <span className="text-slate-400 font-medium">Omerta User #</span>
                <span className="font-mono text-cyan-400 font-bold">{callModalCust.omerta_user_number}</span>
              </div>
              <div className="flex justify-between items-center py-1">
                <span className="text-slate-400 font-medium">Declared Country</span>
                <span className="text-white font-bold">{callModalCust.country} (Cairo Time UTC+3)</span>
              </div>
            </div>

            <div className="flex items-center justify-end gap-3 pt-2">
              <button
                type="button"
                onClick={() => setCallModalCust(null)}
                className="px-4 py-2 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-300 text-xs font-semibold cursor-pointer"
              >
                Close
              </button>
              <a
                href={`tel:${callModalCust.phone.replace(/\s+/g, '')}`}
                className="flex items-center gap-2 px-4 py-2 rounded-lg bg-gradient-to-r from-emerald-600 to-teal-600 hover:from-emerald-500 hover:to-teal-500 text-white text-xs font-bold shadow-md shadow-emerald-500/20 cursor-pointer"
              >
                <PhoneCall className="h-4 w-4" />
                <span>Dial {callModalCust.phone}</span>
              </a>
            </div>
          </div>
        </Modal>
      )}

      {/* MODAL: SEND SECURITY EMAIL / SMS */}
      {emailModalCust && (
        <Modal isOpen={!!emailModalCust} onClose={() => setEmailModalCust(null)} title={`Send Security Notice to ${emailModalCust.name}`}>
          <form onSubmit={handleSendEmailNotice} className="space-y-4">
            <div className="space-y-1.5">
              <label className="text-xs font-bold text-slate-300">Recipient Email</label>
              <input
                type="text"
                readOnly
                value={emailModalCust.email}
                className="w-full px-3 py-2 bg-slate-900 border border-slate-700 rounded-lg text-xs font-mono text-slate-400"
              />
            </div>

            <div className="space-y-1.5">
              <label className="text-xs font-bold text-slate-300">Subject</label>
              <input
                type="text"
                value={emailSubject}
                onChange={(e) => setEmailSubject(e.target.value)}
                required
                className="w-full px-3 py-2 bg-slate-900 border border-slate-700 rounded-lg text-xs text-white focus:outline-none focus:border-cyan-400"
              />
            </div>

            <div className="space-y-1.5">
              <label className="text-xs font-bold text-slate-300">Message Content</label>
              <textarea
                rows={5}
                value={emailBody}
                onChange={(e) => setEmailBody(e.target.value)}
                required
                className="w-full px-3 py-2 bg-slate-900 border border-slate-700 rounded-lg text-xs text-white focus:outline-none focus:border-cyan-400 font-mono leading-relaxed"
              />
            </div>

            <div className="flex items-center justify-end gap-3 pt-2">
              <button
                type="button"
                onClick={() => setEmailModalCust(null)}
                className="px-4 py-2 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-300 text-xs font-semibold cursor-pointer"
              >
                Cancel
              </button>
              <button
                type="submit"
                disabled={emailSubmitting}
                className="flex items-center gap-2 px-4 py-2 rounded-lg bg-gradient-to-r from-blue-600 to-cyan-600 hover:from-blue-500 hover:to-cyan-500 text-white text-xs font-bold shadow-md shadow-blue-500/20 cursor-pointer"
              >
                <Mail className="h-4 w-4" />
                <span>{emailSubmitting ? 'Sending...' : 'Dispatch Security Email'}</span>
              </button>
            </div>
          </form>
        </Modal>
      )}

      {/* ========================================================================= */}
      {/* MODAL: PROBLEM CUSTOMER AGENTIC AI FORENSIC REPORT */}
      {/* ========================================================================= */}
      {custAgenticModal && (
        <Modal
          isOpen={!!custAgenticModal}
          onClose={() => setCustAgenticModal(null)}
          title={`🤖 Agentic AI Forensic Investigation: ${custAgenticModal.name}`}
        >
          <div className="space-y-4">
            {/* Header / Overview */}
            <div className="p-4 rounded-xl bg-gradient-to-r from-purple-950/70 via-indigo-950/70 to-[#101A2B] border border-purple-500/40 space-y-2 shadow-lg">
              <div className="flex items-center justify-between flex-wrap gap-2">
                <div className="flex items-center gap-2.5">
                  <div className="h-8 w-8 rounded-full bg-purple-500/20 text-purple-300 flex items-center justify-center font-bold text-sm border border-purple-500/30">
                    <Sparkles className="h-4 w-4 text-purple-400" />
                  </div>
                  <div>
                    <h3 className="text-sm font-bold text-white flex items-center gap-2">
                      <span>{custAgenticModal.name}</span>
                      <span className="font-mono text-xs text-cyan-300">({custAgenticModal.omerta_user_number})</span>
                    </h3>
                    <div className="text-[11px] text-[#A7B4C8] flex items-center gap-2 mt-0.5">
                      <span>📞 {custAgenticModal.phone}</span>
                      <span>•</span>
                      <span>✉️ {custAgenticModal.email}</span>
                    </div>
                  </div>
                </div>
                <div className="flex items-center gap-2">
                  <RiskBadge level={custAgenticModal.risk_level || 'HIGH'} size="sm" />
                  <span className="px-2 py-0.5 rounded bg-rose-500/20 text-rose-300 font-mono text-[10px] font-bold border border-rose-500/40">
                    {custAgenticModal.status === 'SUSPENDED' ? 'SUSPENDED & LOCKED' : 'ELEVATED RISK'}
                  </span>
                </div>
              </div>
            </div>

            {custAgenticLoading ? (
              <div className="py-8 text-center text-[#A7B4C8] text-xs">
                <RefreshCw className="h-6 w-6 animate-spin mx-auto mb-2 text-purple-400" />
                <span>Running autonomous multi-agent forensic analysis...</span>
              </div>
            ) : (
              <div className="space-y-4">
                {/* Multi-Agent Verdict Grid */}
                <div className="space-y-1.5">
                  <span className="text-[10px] uppercase font-bold text-[#A7B4C8] tracking-wider">Multi-Agent Security Consensus:</span>
                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
                    {custAgenticModal.agentic_agents?.map((ag: any, idx: number) => (
                      <div key={idx} className="p-2.5 rounded-lg bg-[#080D19] border border-[#25344A] flex items-center justify-between text-xs">
                        <span className="text-[#F4F7FC] font-semibold flex items-center gap-1.5">
                          <Bot className="h-3.5 w-3.5 text-purple-400" />
                          {ag.agent}
                        </span>
                        <span className={`font-mono text-[10px] font-bold px-2 py-0.5 rounded ${
                          ag.verdict === 'FLAGGED' || ag.verdict === 'VPN_RESTRICTED' || ag.verdict === 'ACTION_REQUIRED' || ag.verdict === 'ANOMALOUS_VELOCITY'
                            ? 'bg-rose-500/20 text-rose-300 border border-rose-500/30'
                            : 'bg-emerald-500/20 text-emerald-300 border border-emerald-500/30'
                        }`}>
                          {ag.verdict}
                        </span>
                      </div>
                    ))}
                  </div>
                </div>

                {/* Forensic Findings */}
                <div className="space-y-1.5">
                  <span className="text-[10px] uppercase font-bold text-[#A7B4C8] tracking-wider">Forensic Signals &amp; Evidence:</span>
                  <div className="space-y-2">
                    {custAgenticModal.forensic_findings?.map((f: any, idx: number) => (
                      <div key={idx} className="p-3 bg-[#080D19] rounded-xl border border-[#25344A] text-xs space-y-1">
                        <div className="flex items-center justify-between">
                          <span className="font-bold text-rose-300 font-mono text-[11px]">{f.category}</span>
                          <span className="px-1.5 py-0.2 bg-rose-500/20 text-rose-300 font-bold text-[9px] rounded uppercase">{f.severity}</span>
                        </div>
                        <p className="text-[#F4F7FC]">{f.finding}</p>
                        <p className="text-[#29C5D9] text-[11px] pt-1">👉 <strong>Required Action:</strong> {f.action_required}</p>
                      </div>
                    ))}
                  </div>
                </div>

                {/* Agent Recommendation */}
                <div className="p-3.5 rounded-xl bg-amber-500/10 border border-amber-500/20 text-xs text-amber-300 space-y-1">
                  <span className="font-bold block text-white flex items-center gap-1.5">
                    <ShieldAlert className="h-4 w-4 text-amber-400" />
                    Recommended Compliance Action:
                  </span>
                  <p className="text-[#A7B4C8] leading-relaxed">
                    {custAgenticModal.recommended_resolution || "Call customer on registered telephone number, confirm identity, then resolve account."}
                  </p>
                </div>
              </div>
            )}

            {/* Quick Action Footer */}
            <div className="flex items-center justify-between gap-2 pt-2 border-t border-[#25344A]">
              <button
                type="button"
                onClick={() => setCustAgenticModal(null)}
                className="px-4 py-2 rounded-lg bg-[#152238] hover:bg-[#1B2B43] text-[#F4F7FC] text-xs font-semibold cursor-pointer"
              >
                Close Report
              </button>

              <div className="flex items-center gap-2">
                <button
                  type="button"
                  onClick={() => {
                    const c = custAgenticModal;
                    setCustAgenticModal(null);
                    setCallModalCust(c);
                  }}
                  className="flex items-center gap-1.5 px-3 py-2 rounded-lg bg-[#3978F6] hover:bg-[#3978F6]/90 text-white text-xs font-bold shadow-xs cursor-pointer"
                >
                  <PhoneCall className="h-3.5 w-3.5" />
                  <span>Call {custAgenticModal.phone}</span>
                </button>

                <button
                  type="button"
                  onClick={() => {
                    const c = custAgenticModal;
                    setCustAgenticModal(null);
                    handleResolveRisk(c.customer_id, c.name);
                  }}
                  className="flex items-center gap-1.5 px-3.5 py-2 rounded-lg bg-[#27C58B] hover:bg-[#27C58B]/90 text-slate-950 text-xs font-bold shadow-xs cursor-pointer"
                >
                  <Unlock className="h-3.5 w-3.5" />
                  <span>Resolve &amp; Reactivate</span>
                </button>
              </div>
            </div>
          </div>
        </Modal>
      )}

      {/* CREATE SUB-ADMIN / STAFF MODAL */}
      <Modal
        isOpen={createStaffOpen}
        onClose={() => setCreateStaffOpen(false)}
        title="Provision Administrator / Operational Staff Account"
        subtitle="Create co-administrators, investigators, fraud analysts, or auditors with designated credentials"
        maxWidth="lg"
      >
        <form onSubmit={handleCreateStaff} className="space-y-4">
          {staffError && (
            <div className="p-3.5 rounded-xl bg-[#F06470]/10 border border-[#F06470]/30 text-xs text-[#F06470] flex items-center gap-2">
              <AlertCircle className="w-4 h-4 shrink-0" />
              <span>{staffError}</span>
            </div>
          )}

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            <div>
              <label className="block text-[11px] font-bold uppercase tracking-wider text-[#A7B4C8] mb-1">
                Full Name
              </label>
              <input
                type="text"
                required
                placeholder="e.g. Dr. Omar Mansour"
                value={newStaff.full_name}
                onChange={(e) => setNewStaff({ ...newStaff, full_name: e.target.value })}
                className="w-full px-3 py-2.5 bg-[#080D19] border border-[#25344A] rounded-xl text-xs text-[#F4F7FC] placeholder-[#71819A] focus:outline-none focus:border-[#3978F6]"
              />
            </div>

            <div>
              <label className="block text-[11px] font-bold uppercase tracking-wider text-[#A7B4C8] mb-1">
                Login Username
              </label>
              <input
                type="text"
                required
                placeholder="e.g. omar_admin"
                value={newStaff.username}
                onChange={(e) => setNewStaff({ ...newStaff, username: e.target.value })}
                className="w-full px-3 py-2.5 bg-[#080D19] border border-[#25344A] rounded-xl text-xs text-[#F4F7FC] placeholder-[#71819A] focus:outline-none focus:border-[#3978F6]"
              />
            </div>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            <div>
              <label className="block text-[11px] font-bold uppercase tracking-wider text-[#A7B4C8] mb-1">
                Official Email Address
              </label>
              <input
                type="email"
                required
                placeholder="e.g. omar@omerta.ai"
                value={newStaff.email}
                onChange={(e) => setNewStaff({ ...newStaff, email: e.target.value })}
                className="w-full px-3 py-2.5 bg-[#080D19] border border-[#25344A] rounded-xl text-xs text-[#F4F7FC] placeholder-[#71819A] focus:outline-none focus:border-[#3978F6]"
              />
            </div>

            <div>
              <label className="block text-[11px] font-bold uppercase tracking-wider text-[#A7B4C8] mb-1">
                Account Password
              </label>
              <input
                type="password"
                required
                placeholder="Min. 8 characters"
                value={newStaff.password}
                onChange={(e) => setNewStaff({ ...newStaff, password: e.target.value })}
                className="w-full px-3 py-2.5 bg-[#080D19] border border-[#25344A] rounded-xl text-xs text-[#F4F7FC] placeholder-[#71819A] focus:outline-none focus:border-[#3978F6]"
              />
            </div>
          </div>

          <div>
            <label className="block text-[11px] font-bold uppercase tracking-wider text-[#A7B4C8] mb-1">
              Designated Staff / Admin Role
            </label>
            <select
              value={newStaff.role}
              onChange={(e) => {
                const r = e.target.value;
                setNewStaff({
                  ...newStaff,
                  role: r,
                  privileges:
                    r === 'ADMINISTRATOR'
                      ? ['manage_users', 'review_flagged_transactions', 'adjust_balances', 'view_audit_logs', 'export_reports', 'manage_staff']
                      : r === 'FRAUD_ANALYST'
                      ? ['review_flagged_transactions', 'view_audit_logs', 'export_reports']
                      : r === 'SENIOR_INVESTIGATOR'
                      ? ['manage_users', 'review_flagged_transactions', 'view_audit_logs', 'export_reports']
                      : ['view_audit_logs', 'export_reports'],
                });
              }}
              className="w-full px-3 py-2.5 bg-[#080D19] border border-[#25344A] rounded-xl text-xs text-[#F4F7FC] focus:outline-none focus:border-[#3978F6]"
            >
              <option value="ADMINISTRATOR">Administrator / Co-Admin (Full Oversight, User Management, Thresholds)</option>
              <option value="FRAUD_ANALYST">Fraud Operations Analyst (Review Queue, Triage, Customer Verification)</option>
              <option value="SENIOR_INVESTIGATOR">Senior AML Investigator (SAR Dispositions, Case Dossiers)</option>
              <option value="AUDITOR">Compliance Auditor (Audit Trails, Telemetry, RegTech Inspection)</option>
            </select>
          </div>

          <div>
            <label className="block text-[11px] font-bold uppercase tracking-wider text-[#A7B4C8] mb-2">
              Assigned Privileges
            </label>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
              {Object.entries(PRIVILEGE_DEFINITIONS).map(([key, def]) => {
                const Icon = def.icon;
                const isChecked = newStaff.privileges.includes(key);
                return (
                  <div
                    key={key}
                    onClick={() => handleTogglePrivilege(key)}
                    className={`p-3 rounded-xl border flex items-center justify-between cursor-pointer transition-all ${
                      isChecked
                        ? 'bg-[#152238] border-[#3978F6]'
                        : 'bg-[#080D19] border-[#25344A] hover:bg-[#152238]/50'
                    }`}
                  >
                    <div className="flex items-center gap-3">
                      <div className={`p-1.5 rounded-lg ${isChecked ? 'bg-[#3978F6]/20 text-[#3978F6]' : 'bg-[#101A2B] text-[#71819A]'}`}>
                        <Icon className="w-4 h-4" />
                      </div>
                      <div>
                        <span className="text-xs font-bold text-[#F4F7FC] block">{def.label}</span>
                        <span className="text-[10px] text-[#A7B4C8]">{def.desc}</span>
                      </div>
                    </div>

                    <input
                      type="checkbox"
                      checked={isChecked}
                      onChange={() => {}}
                      className="h-4 w-4 rounded bg-[#101A2B] border-[#25344A] text-[#3978F6] focus:ring-0 cursor-pointer"
                    />
                  </div>
                );
              })}
            </div>
          </div>

          <div className="flex items-center justify-end gap-3 pt-4 border-t border-[#25344A]">
            <button
              type="button"
              onClick={() => setCreateStaffOpen(false)}
              className="px-4 py-2.5 rounded-xl bg-[#152238] hover:bg-[#1B2B43] border border-[#25344A] text-xs font-semibold text-[#F4F7FC] cursor-pointer"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={isSubmittingStaff}
              className="px-5 py-2.5 rounded-xl bg-[#3978F6] hover:bg-[#3978F6]/90 disabled:opacity-50 text-xs font-bold text-[#F4F7FC] shadow-md shadow-blue-500/25 cursor-pointer"
            >
              {isSubmittingStaff ? 'Creating Staff Account...' : 'Save & Provision Access'}
            </button>
          </div>
        </form>
      </Modal>

      {/* Customer 360 Modal */}
      {selectedCustomer && (
        <Modal
          isOpen={Boolean(selectedCustomer)}
          onClose={() => setSelectedCustomer(null)}
          title={`Customer 360° — ${selectedCustomer.customer.name}`}
          subtitle={`ID: ${selectedCustomer.customer.external_id} • Country: ${selectedCustomer.customer.country}`}
          maxWidth="2xl"
        >
          <div className="space-y-4 text-xs">
            <div className="p-4 rounded-xl bg-[#080D19] border border-[#25344A] grid grid-cols-2 gap-3">
              <div>
                <span className="text-[10px] text-[#71819A] uppercase">Email</span>
                <p className="font-bold text-[#F4F7FC]">{selectedCustomer.customer.email}</p>
              </div>
              <div>
                <span className="text-[10px] text-[#71819A] uppercase">Phone</span>
                <p className="font-mono text-[#F4F7FC]">{selectedCustomer.customer.phone || '—'}</p>
              </div>
              <div>
                <span className="text-[10px] text-[#71819A] uppercase">Omerta User #</span>
                <p className="font-mono font-bold text-[#29C5D9]">{selectedCustomer.customer.omerta_user_number}</p>
              </div>
              <div>
                <span className="text-[10px] text-[#71819A] uppercase">Internal AML Rating</span>
                <div>
                  <RiskBadge level={selectedCustomer.customer.risk_level} />
                </div>
              </div>
            </div>
          </div>
        </Modal>
      )}
    </div>
  );
};
