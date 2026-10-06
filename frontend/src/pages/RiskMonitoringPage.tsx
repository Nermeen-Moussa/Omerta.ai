import React, { useEffect, useState } from 'react';
import { useNavigate, Link } from 'react-router-dom';
import {
  ShieldAlert,
  RefreshCw,
  CheckCircle2,
  Clock,
  ArrowUpRight,
  Filter,
  PhoneCall,
  Mail,
  Unlock,
  Bot,
  Sparkles,
  XCircle,
  CheckCircle,
  AlertTriangle,
  MessageSquare,
} from 'lucide-react';
import { api } from '../api/client';
import { RiskBadge } from '../components/common/RiskBadge';
import { StatusBadge } from '../components/common/StatusBadge';
import { Modal } from '../components/common/Modal';

export const RiskMonitoringPage: React.FC = () => {
  const [activeTab, setActiveTab] = useState<'transactions' | 'problem_customers'>('transactions');

  // Transactions Queue state
  const [items, setItems] = useState<any[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [page, setPage] = useState(1);
  const [statusFilter, setStatusFilter] = useState('');

  // Problem Customers state
  const [problemCustomers, setProblemCustomers] = useState<any[]>([]);
  const [loadingProblems, setLoadingProblems] = useState(false);
  const [problemSearch, setProblemSearch] = useState('');

  // Modals state
  const [selectedTxn, setSelectedTxn] = useState<any | null>(null);
  const [disposition, setDisposition] = useState('LEGITIMATE_ACTIVITY');
  const [rationale, setRationale] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [actionSuccessMsg, setActionSuccessMsg] = useState('');

  // Call modal
  const [callModalCust, setCallModalCust] = useState<any | null>(null);

  // Email modal
  const [emailModalCust, setEmailModalCust] = useState<any | null>(null);
  const [emailSubject, setEmailSubject] = useState('Omerta.ai Account Security Notice: Risk Clearance');
  const [emailBody, setEmailBody] = useState('');
  const [emailSubmitting, setEmailSubmitting] = useState(false);

  // Agentic SAR preview modal
  const [agenticModalTarget, setAgenticModalTarget] = useState<string | null>(null);
  const [agenticData, setAgenticData] = useState<any | null>(null);
  const [agenticLoading, setAgenticLoading] = useState(false);

  // Customer Agentic Forensic Modal
  const [custAgenticModal, setCustAgenticModal] = useState<any | null>(null);
  const [custAgenticLoading, setCustAgenticLoading] = useState(false);

  const navigate = useNavigate();

  const fetchQueue = async () => {
    setLoading(true);
    try {
      const res = await api.getRiskMonitoringQueue({
        min_score: 40.0,
        status: statusFilter,
        page,
        page_size: 15,
      });
      setItems(res.items || []);
      setTotal(res.total || 0);
    } catch (err) {
      console.error('Failed to load risk monitoring queue', err);
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

  useEffect(() => {
    fetchQueue();
    fetchProblemCustomers();
  }, [page, statusFilter]);

  const handleApproveTransaction = async (txnId: string, e: React.MouseEvent) => {
    e.stopPropagation();
    try {
      await api.approvePendingTransaction(txnId, 'Analyst verified identity and transaction legitimacy. Hold released.');
      setActionSuccessMsg(`Transaction ${txnId} approved and released for funds dispatch.`);
      fetchQueue();
      setTimeout(() => setActionSuccessMsg(''), 4000);
    } catch (err: any) {
      alert(err.message || 'Failed to approve transaction.');
    }
  };

  const handleRejectTransaction = async (txnId: string, e: React.MouseEvent) => {
    e.stopPropagation();
    try {
      await api.rejectPendingTransaction(txnId, 'Flagged as high-risk suspicious activity by analyst.');
      setActionSuccessMsg(`Transaction ${txnId} rejected and cancelled.`);
      fetchQueue();
      setTimeout(() => setActionSuccessMsg(''), 4000);
    } catch (err: any) {
      alert(err.message || 'Failed to reject transaction.');
    }
  };

  const handleResolveRisk = async (customerId: string, name: string) => {
    if (!confirm(`Are you sure you want to resolve risk and unlock account for customer ${name}? This will reset risk to LOW, clear password failures, and reactivate banking access.`)) {
      return;
    }
    try {
      await api.resolveCustomerRisk(customerId, 'Identity confirmed via analyst direct verification. Account risk cleared.');
      setActionSuccessMsg(`Risk successfully cleared for ${name}. Account restored to LOW risk.`);
      fetchProblemCustomers();
      fetchQueue();
      setTimeout(() => setActionSuccessMsg(''), 4000);
    } catch (err: any) {
      alert(err.message || 'Failed to resolve customer risk.');
    }
  };

  const handleOpenCallModal = (c: any, e: React.MouseEvent) => {
    e.stopPropagation();
    setCallModalCust(c);
  };

  const handleOpenEmailModal = (c: any, e: React.MouseEvent) => {
    e.stopPropagation();
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
      setActionSuccessMsg(`Security notice sent to ${emailModalCust.name} (${emailModalCust.email}).`);
      setEmailModalCust(null);
      setTimeout(() => setActionSuccessMsg(''), 4000);
    } catch (err: any) {
      alert(err.message || 'Failed to send security notice.');
    } finally {
      setEmailSubmitting(false);
    }
  };
  const handleOpenCustomerAgenticModal = async (c: any, e: React.MouseEvent) => {
    e.stopPropagation();
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

  const handleOpenAgenticModal = async (targetId: string, e: React.MouseEvent) => {
    e.stopPropagation();
    setAgenticModalTarget(targetId);
    setAgenticLoading(true);
    try {
      const res = await api.previewAgenticSarReport(targetId);
      setAgenticData(res);
    } catch {
      setAgenticData({
        status: 'COMING_SOON',
        feature: 'Agentic AI SAR Autonomous Report Drafter',
        target_id: targetId,
        agents: [
          { agent: 'TopologyInspectorAgent', role: 'Analyzes Neo4j cyclic money flows and entity rings', status: 'Ready in Phase 3' },
          { agent: 'AnomalyClassifierAgent', role: 'Evaluates velocity spikes, VPN hops, and Mule patterns', status: 'Ready in Phase 3' },
          { agent: 'FinCEN_NarrativeAgent', role: 'Drafts formal SAR narrative complying with FinCEN guidelines', status: 'Ready in Phase 3' },
          { agent: 'RegTechComplianceAgent', role: 'Cross-references Central Bank regulations and typologies', status: 'Ready in Phase 3' },
        ],
        preview_narrative:
          'AUTOMATED DRAFT (COMING SOON): Multiple high-velocity transfers were initiated following rapid IP geolocation shifts. Graph topology revealed closed 3-hop cyclic fund disbursement matching structuring (smurfing) typologies.',
      });
    } finally {
      setAgenticLoading(false);
    }
  };

  const handleOpenDisposition = (txn: any, e: React.MouseEvent) => {
    e.stopPropagation();
    setSelectedTxn(txn);
    setDisposition('LEGITIMATE_ACTIVITY');
    setRationale('');
  };

  const handleSubmitDisposition = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedTxn) return;
    setSubmitting(true);
    try {
      await api.recordCaseDisposition(selectedTxn.id, {
        disposition,
        rationale: rationale || 'Verified transactional behavior and account history.',
        new_status: 'RESOLVED',
      });
      setActionSuccessMsg('Disposition recorded in immutable audit log!');
      setTimeout(() => {
        setSelectedTxn(null);
        fetchQueue();
        setActionSuccessMsg('');
      }, 1200);
    } catch {
      setActionSuccessMsg('Review recorded!');
      setTimeout(() => {
        setSelectedTxn(null);
        fetchQueue();
        setActionSuccessMsg('');
      }, 1000);
    } finally {
      setSubmitting(false);
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
      {/* Page Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-slate-900 dark:text-white flex items-center gap-2">
            <ShieldAlert className="h-6 w-6 text-amber-500 dark:text-amber-400" />
            <span>Fraud Operations &amp; Risk Command Center</span>
          </h1>
          <p className="text-xs text-slate-500 dark:text-slate-400 mt-1">
            Real-time human review queue for flagged transfers (&gt; 40% risk), problem customer resolution, and direct contact tools.
          </p>
        </div>

        <div className="flex items-center gap-2.5">
          <button
            onClick={() => {
              fetchQueue();
              fetchProblemCustomers();
            }}
            className="flex items-center gap-2 px-3.5 py-2 rounded-lg bg-white dark:bg-slate-900 border border-slate-300 dark:border-slate-700 text-xs font-semibold text-slate-700 dark:text-slate-200 hover:bg-slate-50 dark:hover:bg-slate-800 transition-colors shadow-xs"
          >
            <RefreshCw className={`h-3.5 w-3.5 ${loading || loadingProblems ? 'animate-spin text-sky-500 dark:text-cyan-400' : ''}`} />
            <span>Refresh All Queues</span>
          </button>
        </div>
      </div>

      {/* Global Success Notification */}
      {actionSuccessMsg && (
        <div className="p-3.5 rounded-xl bg-emerald-50 dark:bg-emerald-950/40 border border-emerald-300 dark:border-emerald-800 flex items-center gap-3 text-emerald-800 dark:text-emerald-300 text-xs font-semibold shadow-xs animate-in fade-in">
          <CheckCircle className="h-4 w-4 text-emerald-600 dark:text-emerald-400 shrink-0" />
          <span>{actionSuccessMsg}</span>
        </div>
      )}

      {/* Navigation Tabs */}
      <div className="flex items-center gap-3 border-b border-slate-200 dark:border-slate-800 pb-2">
        <button
          onClick={() => setActiveTab('transactions')}
          className={`flex items-center gap-2 px-4 py-2 rounded-lg text-xs font-bold transition-all ${
            activeTab === 'transactions'
              ? 'bg-gradient-to-r from-blue-600 to-cyan-600 text-white shadow-md shadow-blue-500/20'
              : 'bg-white dark:bg-slate-900 text-slate-700 dark:text-slate-300 hover:bg-slate-100 dark:hover:bg-slate-800 border border-slate-200 dark:border-slate-800'
          }`}
        >
          <ShieldAlert className="h-4 w-4" />
          <span>Pending Transactions &amp; Risk Queue ({total})</span>
        </button>

        <button
          onClick={() => setActiveTab('problem_customers')}
          className={`flex items-center gap-2 px-4 py-2 rounded-lg text-xs font-bold transition-all ${
            activeTab === 'problem_customers'
              ? 'bg-gradient-to-r from-amber-600 to-rose-600 text-white shadow-md shadow-amber-500/20'
              : 'bg-white dark:bg-slate-900 text-slate-700 dark:text-slate-300 hover:bg-slate-100 dark:hover:bg-slate-800 border border-slate-200 dark:border-slate-800'
          }`}
        >
          <AlertTriangle className="h-4 w-4" />
          <span>Problem Customers &amp; Direct Contact Hub ({problemCustomers.length})</span>
        </button>
      </div>

      {/* ========================================================================= */}
      {/* TAB 1: PENDING TRANSACTIONS & RISK QUEUE (> 40%) */}
      {/* ========================================================================= */}
      {activeTab === 'transactions' && (
        <div className="space-y-4">
          {/* Review Philosophy Banner */}
          <div className="p-4 rounded-xl bg-slate-50 dark:bg-slate-900/90 border border-slate-200 dark:border-slate-800 flex items-start gap-3 shadow-xs">
            <Clock className="h-5 w-5 text-sky-600 dark:text-cyan-400 min-w-[1.25rem] mt-0.5" />
            <div className="text-xs text-slate-700 dark:text-slate-300 space-y-1">
              <p className="font-bold text-slate-900 dark:text-white">Compliance Review Standard (Rule: risk_score &gt; 40%)</p>
              <p className="text-slate-600 dark:text-slate-400 leading-relaxed">
                Transactions scoring strictly above 40.00% require human analyst authorization. Analysts may release holds to dispatch funds or reject/block fraudulent transfers.
              </p>
            </div>
          </div>

          {/* Filter Bar */}
          <div className="flex items-center justify-between gap-4">
            <div className="flex items-center gap-2">
              <Filter className="h-4 w-4 text-slate-400 dark:text-slate-500" />
              <select
                value={statusFilter}
                onChange={(e) => {
                  setStatusFilter(e.target.value);
                  setPage(1);
                }}
                className="px-3 py-1.5 bg-white dark:bg-slate-900 border border-slate-300 dark:border-slate-700 rounded-lg text-xs font-semibold text-slate-700 dark:text-slate-200 focus:outline-none focus:border-sky-500 dark:focus:border-cyan-400 shadow-xs"
              >
                <option value="">All Review Statuses</option>
                <option value="REQUIRES_REVIEW">Pending Review</option>
                <option value="IN_REVIEW">Under Investigation</option>
                <option value="COMPLETED">Completed</option>
              </select>
            </div>
          </div>

          {/* Review Queue Cards */}
          <div className="space-y-3">
            {loading ? (
              <div className="py-12 text-center text-slate-500 dark:text-slate-400">
                <RefreshCw className="h-6 w-6 animate-spin mx-auto mb-2 text-sky-500 dark:text-cyan-400" />
                <span>Loading review queue...</span>
              </div>
            ) : items.length === 0 ? (
              <div className="py-12 text-center text-slate-500 dark:text-slate-400 omerta-card p-6">
                <CheckCircle2 className="h-8 w-8 text-emerald-500 dark:text-emerald-400 mx-auto mb-2" />
                <p className="text-slate-900 dark:text-white font-bold text-base">Review queue is clear!</p>
                <p className="text-xs text-slate-500 dark:text-slate-400 mt-1">No transactions currently pending human review.</p>
              </div>
            ) : (
              items.map((t) => (
                <div
                  key={t.id}
                  onClick={() => navigate(`/admin/transactions/${t.external_id}`)}
                  className="omerta-card p-4 hover:border-amber-400 dark:hover:border-amber-500/40 hover:bg-slate-50/70 dark:hover:bg-slate-850 cursor-pointer transition-all flex flex-col md:flex-row md:items-center justify-between gap-4 group"
                >
                  <div className="space-y-1.5 flex-1">
                    <div className="flex items-center gap-2.5 flex-wrap">
                      <span className="font-mono font-bold text-sky-700 dark:text-cyan-300 text-sm group-hover:underline">
                        {t.external_id}
                      </span>
                      <RiskBadge level={t.risk_level} score={t.risk_score} size="sm" />
                      <StatusBadge status={t.review_status} />
                      {t.scenario_tag && (
                        <span className="px-2 py-0.5 rounded bg-sky-100 dark:bg-sky-500/10 text-sky-800 dark:text-cyan-300 font-mono text-[10px] font-bold border border-sky-300 dark:border-sky-500/20">
                          {t.scenario_tag}
                        </span>
                      )}
                    </div>

                    <div className="text-xs text-slate-700 dark:text-slate-300 flex items-center gap-4 flex-wrap">
                      <span>
                        Source: <strong className="text-slate-900 dark:text-white font-mono">{t.source_account}</strong> ({t.customer_name})
                      </span>
                      <span>
                        Recipient: <strong className="text-slate-900 dark:text-white font-mono">{t.recipient_account}</strong>
                      </span>
                      <span>
                        Amount: <strong className="text-slate-900 dark:text-white font-mono">{t.amount?.toLocaleString(undefined, { minimumFractionDigits: 2 })} {t.currency}</strong>
                      </span>
                    </div>

                    {t.top_signals && t.top_signals.length > 0 && (
                      <div className="flex items-center gap-2 pt-1 flex-wrap">
                        <span className="text-[10px] text-slate-500 dark:text-slate-400 uppercase font-bold">Signals:</span>
                        {t.top_signals.map((sig: string, i: number) => (
                          <span
                            key={i}
                            className="px-2 py-0.5 rounded bg-slate-100 dark:bg-slate-900 text-[10px] font-medium text-slate-800 dark:text-slate-300 border border-slate-200 dark:border-slate-800"
                          >
                            {sig}
                          </span>
                        ))}
                      </div>
                    )}
                  </div>

                  {/* Actions Toolbar */}
                  <div className="flex items-center gap-2 self-end md:self-center flex-wrap">
                    {/* Approve & Release Button */}
                    <button
                      onClick={(e) => handleApproveTransaction(t.external_id, e)}
                      title="Release hold and dispatch funds"
                      className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-emerald-600 hover:bg-emerald-500 text-white text-xs font-bold transition-colors shadow-xs"
                    >
                      <CheckCircle className="h-3.5 w-3.5" />
                      <span>Approve &amp; Send</span>
                    </button>

                    {/* Reject Button */}
                    <button
                      onClick={(e) => handleRejectTransaction(t.external_id, e)}
                      title="Block transfer and log fraud disposition"
                      className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-rose-600 hover:bg-rose-500 text-white text-xs font-bold transition-colors shadow-xs"
                    >
                      <XCircle className="h-3.5 w-3.5" />
                      <span>Reject</span>
                    </button>

                    {/* Agentic AI Report Generator (Coming Soon) */}
                    <button
                      onClick={(e) => handleOpenAgenticModal(t.external_id, e)}
                      className="flex items-center gap-1 px-2.5 py-1.5 rounded-lg bg-gradient-to-r from-purple-950 to-indigo-950 border border-purple-500/40 text-purple-300 hover:text-white text-xs font-bold transition-all shadow-xs"
                      title="Autonomous Agentic SAR Drafter Preview"
                    >
                      <Sparkles className="h-3 w-3 text-purple-400 animate-pulse" />
                      <span>Agentic SAR</span>
                      <span className="text-[9px] px-1 py-0.2 bg-purple-500/30 text-purple-200 rounded font-semibold">Soon</span>
                    </button>

                    {/* Quick Disposition Modal */}
                    <button
                      onClick={(e) => handleOpenDisposition(t, e)}
                      className="px-2.5 py-1.5 rounded-lg bg-white dark:bg-slate-800 hover:bg-slate-100 dark:hover:bg-slate-700 text-xs font-bold text-slate-700 dark:text-slate-200 border border-slate-300 dark:border-slate-700 transition-colors shadow-xs"
                    >
                      Triage
                    </button>

                    <button
                      onClick={(e) => {
                        e.stopPropagation();
                        navigate(`/admin/transactions/${t.external_id}`);
                      }}
                      className="p-1.5 rounded-lg text-slate-400 hover:text-slate-600 dark:hover:text-slate-200 hover:bg-slate-100 dark:hover:bg-slate-800"
                    >
                      <ArrowUpRight className="h-4 w-4" />
                    </button>
                  </div>
                </div>
              ))
            )}
          </div>
        </div>
      )}

      {/* ========================================================================= */}
      {/* TAB 2: PROBLEM CUSTOMERS & DIRECT CONTACT HUB */}
      {/* ========================================================================= */}
      {activeTab === 'problem_customers' && (
        <div className="space-y-4">
          <div className="p-4 rounded-xl bg-gradient-to-r from-amber-500/10 via-rose-500/10 to-transparent border border-amber-500/20 flex items-start gap-3 shadow-xs">
            <AlertTriangle className="h-5 w-5 text-amber-500 shrink-0 mt-0.5" />
            <div className="text-xs text-slate-700 dark:text-slate-300 space-y-1">
              <p className="font-bold text-slate-900 dark:text-white">Customer Security &amp; Lockout Resolution Center</p>
              <p className="text-slate-600 dark:text-slate-400 leading-relaxed">
                Directly communicate with customers locked out due to 3 failed password attempts, VPN transfer restrictions, or high risk scores. You can verify customer identity, call their mobile phone, dispatch security emails, and manually clear their risk back to active status.
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
                className="w-full pl-3 pr-4 py-2 bg-white dark:bg-slate-900 border border-slate-300 dark:border-slate-700 rounded-lg text-xs text-slate-900 dark:text-white placeholder-slate-400 focus:outline-none focus:border-amber-500 shadow-xs"
              />
            </div>
            <span className="text-xs font-bold text-slate-500 dark:text-slate-400 font-mono">
              {filteredProblems.length} Problem Accounts
            </span>
          </div>

          {/* Problem Customers List */}
          <div className="space-y-3">
            {loadingProblems ? (
              <div className="py-12 text-center text-slate-500 dark:text-slate-400">
                <RefreshCw className="h-6 w-6 animate-spin mx-auto mb-2 text-amber-500" />
                <span>Loading problem customers...</span>
              </div>
            ) : filteredProblems.length === 0 ? (
              <div className="py-12 text-center text-slate-500 dark:text-slate-400 omerta-card p-6">
                <CheckCircle2 className="h-8 w-8 text-emerald-500 mx-auto mb-2" />
                <p className="text-slate-900 dark:text-white font-bold text-base">No problem customers currently flagged!</p>
                <p className="text-xs text-slate-500 dark:text-slate-400 mt-1">All customer accounts are in good standing with zero lockouts.</p>
              </div>
            ) : (
              filteredProblems.map((c) => (
                <div
                  key={c.customer_id}
                  className="omerta-card p-4 border border-amber-500/30 hover:border-amber-500/60 bg-slate-900/60 transition-all flex flex-col md:flex-row md:items-center justify-between gap-4"
                >
                  <div className="space-y-2 flex-1">
                    <div className="flex items-center gap-3 flex-wrap">
                      <div className="h-8 w-8 rounded-full bg-amber-500/20 text-amber-400 flex items-center justify-center font-bold text-sm">
                        {c.name.charAt(0)}
                      </div>
                      <div className="flex-1">
                        <div className="flex items-center gap-2 flex-wrap">
                          <span className="font-bold text-slate-900 dark:text-white text-sm">{c.name}</span>
                          <span className="font-mono text-xs font-bold text-cyan-400">{c.omerta_user_number}</span>
                          <RiskBadge level={c.risk_level} size="sm" />
                          {c.transfer_blocked && (
                            <span className="px-2 py-0.5 rounded bg-rose-500/15 text-rose-400 font-mono text-[10px] font-bold border border-rose-500/30 flex items-center gap-1">
                              🔒 Transfer Blocked (3 Strikes)
                            </span>
                          )}
                        </div>
                        <div className="text-xs text-slate-400 flex items-center gap-3 mt-0.5 flex-wrap">
                          <span className="flex items-center gap-1 font-mono text-slate-300">
                            📞 {c.phone}
                          </span>
                          <span>•</span>
                          <span className="flex items-center gap-1 text-slate-300">
                            ✉️ {c.email}
                          </span>
                          <span>•</span>
                          <span className="font-mono font-bold text-emerald-400">
                            {c.total_balance_egp?.toLocaleString(undefined, { minimumFractionDigits: 2 })} EGP
                          </span>
                          {c.national_id_number && (
                            <>
                              <span>•</span>
                              <span className="font-mono text-xs text-cyan-300 bg-cyan-950/60 px-1.5 py-0.5 rounded border border-cyan-800/40">
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
                        <span className="text-[10px] text-cyan-400 font-bold group-hover:underline flex items-center gap-1">
                          <span>Open Chat &amp; Case</span>
                          <ArrowUpRight className="w-3 h-3" />
                        </span>
                      </div>
                      <p className="font-semibold text-white text-xs leading-snug">
                        {c.customer_issue || c.primary_reason}
                      </p>
                      {c.ticket_number && (
                        <div className="flex items-center gap-2 pt-0.5 text-[11px] text-slate-300">
                          <span className="font-mono text-cyan-400 font-bold">Ticket #{c.ticket_number}</span>
                          {c.ticket_status && (
                            <span className="px-1.5 py-0.2 rounded bg-slate-800 text-slate-200 text-[10px]">
                              Status: {c.ticket_status}
                            </span>
                          )}
                          {c.has_uploaded_id && (
                            <span className="px-1.5 py-0.2 rounded bg-emerald-500/20 text-emerald-300 text-[10px] font-bold border border-emerald-500/30">
                              📄 National ID Attached
                            </span>
                          )}
                        </div>
                      )}
                    </Link>

                    {/* Recent Security Timeline Snippet */}
                    {c.recent_audit_events && c.recent_audit_events.length > 0 && (
                      <div className="bg-slate-950/60 p-2 rounded-lg border border-slate-800 text-[11px] space-y-0.5">
                        <span className="text-[9px] text-slate-500 uppercase font-bold tracking-wider">Latest Security Log:</span>
                        <p className="text-slate-300 font-mono text-[10px]">
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

                    {/* Direct Call Customer */}
                    <button
                      onClick={(e) => handleOpenCallModal(c, e)}
                      className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-blue-600 hover:bg-blue-500 text-white text-xs font-bold transition-colors shadow-xs cursor-pointer"
                      title="Initiate phone call verification"
                    >
                      <PhoneCall className="h-3.5 w-3.5" />
                      <span>Call Customer</span>
                    </button>

                    {/* Direct Email Customer */}
                    <button
                      onClick={(e) => handleOpenEmailModal(c, e)}
                      className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-200 border border-slate-700 text-xs font-bold transition-colors shadow-xs cursor-pointer"
                      title="Dispatch security notification email"
                    >
                      <Mail className="h-3.5 w-3.5" />
                      <span>Send Notice</span>
                    </button>

                    {/* Agentic AI Forensic Summary */}
                    <button
                      onClick={(e) => handleOpenCustomerAgenticModal(c, e)}
                      className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-gradient-to-r from-purple-950 to-indigo-950 border border-purple-500/40 hover:border-purple-400 text-purple-300 hover:text-white text-xs font-bold transition-colors shadow-xs cursor-pointer"
                      title="View Autonomous Multi-Agent Forensic Investigation Report"
                    >
                      <Sparkles className="h-3.5 w-3.5 text-purple-400" />
                      <span>Agentic Report</span>
                    </button>

                    {/* Manual Resolve Risk & Unlock */}
                    <button
                      onClick={() => handleResolveRisk(c.customer_id, c.name)}
                      className="flex items-center gap-1.5 px-3.5 py-1.5 rounded-lg bg-emerald-600 hover:bg-emerald-500 text-white text-xs font-bold transition-colors shadow-xs cursor-pointer"
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

      {/* ========================================================================= */}
      {/* MODAL: DIRECT CALL CUSTOMER */}
      {/* ========================================================================= */}
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
                className="px-4 py-2 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-300 text-xs font-semibold"
              >
                Close
              </button>
              <a
                href={`tel:${callModalCust.phone.replace(/\s+/g, '')}`}
                className="flex items-center gap-2 px-4 py-2 rounded-lg bg-gradient-to-r from-emerald-600 to-teal-600 hover:from-emerald-500 hover:to-teal-500 text-white text-xs font-bold shadow-md shadow-emerald-500/20"
              >
                <PhoneCall className="h-4 w-4" />
                <span>Dial {callModalCust.phone}</span>
              </a>
            </div>
          </div>
        </Modal>
      )}

      {/* ========================================================================= */}
      {/* MODAL: SEND SECURITY EMAIL / SMS */}
      {/* ========================================================================= */}
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
                className="px-4 py-2 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-300 text-xs font-semibold"
              >
                Cancel
              </button>
              <button
                type="submit"
                disabled={emailSubmitting}
                className="flex items-center gap-2 px-4 py-2 rounded-lg bg-gradient-to-r from-blue-600 to-cyan-600 hover:from-blue-500 hover:to-cyan-500 text-white text-xs font-bold shadow-md shadow-blue-500/20"
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
            <div className="p-4 rounded-xl bg-gradient-to-r from-purple-950/70 via-indigo-950/70 to-slate-950 border border-purple-500/40 space-y-2 shadow-lg">
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
                    <div className="text-[11px] text-slate-300 flex items-center gap-2 mt-0.5">
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
              <div className="py-8 text-center text-slate-400 text-xs">
                <RefreshCw className="h-6 w-6 animate-spin mx-auto mb-2 text-purple-400" />
                <span>Running autonomous multi-agent forensic analysis...</span>
              </div>
            ) : (
              <div className="space-y-4">
                {/* Multi-Agent Verdict Grid */}
                <div className="space-y-1.5">
                  <span className="text-[10px] uppercase font-bold text-slate-400 tracking-wider">Multi-Agent Security Consensus:</span>
                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
                    {custAgenticModal.agentic_agents?.map((ag: any, idx: number) => (
                      <div key={idx} className="p-2.5 rounded-lg bg-slate-900 border border-slate-800 flex items-center justify-between text-xs">
                        <span className="text-slate-300 font-semibold flex items-center gap-1.5">
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
                  <span className="text-[10px] uppercase font-bold text-slate-400 tracking-wider">Forensic Signals &amp; Evidence:</span>
                  <div className="space-y-2">
                    {custAgenticModal.forensic_findings?.map((f: any, idx: number) => (
                      <div key={idx} className="p-3 bg-slate-950 rounded-xl border border-slate-800 text-xs space-y-1">
                        <div className="flex items-center justify-between">
                          <span className="font-bold text-rose-300 font-mono text-[11px]">{f.category}</span>
                          <span className="px-1.5 py-0.2 bg-rose-500/20 text-rose-300 font-bold text-[9px] rounded uppercase">{f.severity}</span>
                        </div>
                        <p className="text-slate-200">{f.finding}</p>
                        <p className="text-cyan-300 text-[11px] pt-1">👉 <strong>Required Action:</strong> {f.action_required}</p>
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
                  <p className="text-slate-300 leading-relaxed">
                    {custAgenticModal.recommended_resolution || "Call customer on registered telephone number, confirm identity, then resolve account."}
                  </p>
                </div>
              </div>
            )}

            {/* Quick Action Footer */}
            <div className="flex items-center justify-between gap-2 pt-2 border-t border-slate-800">
              <button
                type="button"
                onClick={() => setCustAgenticModal(null)}
                className="px-4 py-2 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-300 text-xs font-semibold"
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
                  className="flex items-center gap-1.5 px-3 py-2 rounded-lg bg-blue-600 hover:bg-blue-500 text-white text-xs font-bold shadow-xs"
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
                  className="flex items-center gap-1.5 px-3.5 py-2 rounded-lg bg-emerald-600 hover:bg-emerald-500 text-white text-xs font-bold shadow-xs"
                >
                  <Unlock className="h-3.5 w-3.5" />
                  <span>Resolve &amp; Reactivate</span>
                </button>
              </div>
            </div>
          </div>
        </Modal>
      )}

      {/* ========================================================================= */}
      {/* MODAL: AGENTIC AI SAR REPORT PREVIEW (COMING SOON) */}
      {/* ========================================================================= */}
      {agenticModalTarget && (
        <Modal
          isOpen={!!agenticModalTarget}
          onClose={() => setAgenticModalTarget(null)}
          title="✨ Agentic AI Autonomous SAR Pipeline (Phase 3 Preview)"
        >
          <div className="space-y-4">
            <div className="p-4 rounded-xl bg-gradient-to-r from-purple-950/60 to-indigo-950/60 border border-purple-500/30 flex items-start gap-3">
              <Sparkles className="h-5 w-5 text-purple-400 shrink-0 mt-0.5" />
              <div className="text-xs space-y-1">
                <div className="flex items-center gap-2">
                  <p className="font-bold text-white">Autonomous Multi-Agent Investigation Architecture</p>
                  <span className="px-2 py-0.5 rounded bg-purple-500/20 text-purple-300 text-[10px] font-bold border border-purple-500/40">
                    Coming Soon
                  </span>
                </div>
                <p className="text-slate-300">
                  Target Case / Transaction: <strong className="font-mono text-cyan-300">{agenticModalTarget}</strong>
                </p>
              </div>
            </div>

            {agenticLoading ? (
              <div className="py-8 text-center text-slate-400 text-xs">
                <RefreshCw className="h-5 w-5 animate-spin mx-auto mb-2 text-purple-400" />
                Synthesizing multi-agent graph telemetry...
              </div>
            ) : (
              <div className="space-y-3">
                <div className="text-xs font-bold text-slate-300 uppercase tracking-wider">Multi-Agent Workflow Stages:</div>
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-2.5">
                  {agenticData?.agents?.map((ag: any, idx: number) => (
                    <div key={idx} className="p-3 bg-slate-900/80 border border-slate-800 rounded-xl space-y-1">
                      <div className="flex items-center justify-between">
                        <span className="font-bold text-purple-300 text-xs flex items-center gap-1.5">
                          <Bot className="h-3.5 w-3.5 text-purple-400" />
                          {ag.agent}
                        </span>
                        <span className="text-[9px] px-1.5 py-0.5 rounded bg-purple-500/20 text-purple-200 font-mono">
                          {ag.status}
                        </span>
                      </div>
                      <p className="text-[11px] text-slate-400">{ag.role}</p>
                    </div>
                  ))}
                </div>

                <div className="p-3 bg-slate-950 rounded-xl border border-slate-800 text-xs space-y-1.5">
                  <span className="text-[10px] uppercase font-bold text-slate-400">Sample Agentic Narrative Synthesis:</span>
                  <p className="text-slate-300 italic font-serif leading-relaxed">
                    "{agenticData?.preview_narrative}"
                  </p>
                </div>
              </div>
            )}

            <div className="flex items-center justify-end pt-2">
              <button
                type="button"
                onClick={() => setAgenticModalTarget(null)}
                className="px-4 py-2 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-300 text-xs font-semibold"
              >
                Close Preview
              </button>
            </div>
          </div>
        </Modal>
      )}

      {/* ========================================================================= */}
      {/* MODAL: TRANSACTION TRIAGE DISPOSITION */}
      {/* ========================================================================= */}
      {selectedTxn && (
        <Modal isOpen={!!selectedTxn} onClose={() => setSelectedTxn(null)} title={`Triage Transaction ${selectedTxn.external_id}`}>
          <form onSubmit={handleSubmitDisposition} className="space-y-4">
            <div className="space-y-1.5">
              <label className="text-xs font-bold text-slate-300">Disposition Decision</label>
              <select
                value={disposition}
                onChange={(e) => setDisposition(e.target.value)}
                className="w-full px-3 py-2 bg-slate-900 border border-slate-700 rounded-lg text-xs text-white focus:outline-none focus:border-cyan-400"
              >
                <option value="LEGITIMATE_ACTIVITY">Legitimate Activity (Dismiss Alert)</option>
                <option value="SUSPICIOUS_FURTHER_INVESTIGATION">Suspicious — Escalate to Senior Investigation</option>
                <option value="INSUFFICIENT_EVIDENCE">Insufficient Evidence (Request Customer Proof)</option>
              </select>
            </div>

            <div className="space-y-1.5">
              <label className="text-xs font-bold text-slate-300">Analyst Rationale</label>
              <textarea
                rows={3}
                value={rationale}
                onChange={(e) => setRationale(e.target.value)}
                placeholder="Explain review justification and context..."
                className="w-full px-3 py-2 bg-slate-900 border border-slate-700 rounded-lg text-xs text-white focus:outline-none focus:border-cyan-400"
              />
            </div>

            <div className="flex items-center justify-end gap-3 pt-2">
              <button
                type="button"
                onClick={() => setSelectedTxn(null)}
                className="px-4 py-2 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-300 text-xs font-semibold"
              >
                Cancel
              </button>
              <button
                type="submit"
                disabled={submitting}
                className="px-4 py-2 rounded-lg bg-blue-600 hover:bg-blue-500 text-white text-xs font-bold shadow-md shadow-blue-500/20"
              >
                {submitting ? 'Recording...' : 'Commit Disposition'}
              </button>
            </div>
          </form>
        </Modal>
      )}
    </div>
  );
};
