import React, { useEffect, useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import {
  ArrowLeft,
  ShieldAlert,
  Wallet,
  Sparkles,
  AlertTriangle,
  CheckCircle2,
} from 'lucide-react';
import { api } from '../api/client';
import type { TransactionDetail } from '../types';
import { RiskBadge } from '../components/common/RiskBadge';
import { StatusBadge } from '../components/common/StatusBadge';
import { Modal } from '../components/common/Modal';

export const TransactionDetailPage: React.FC = () => {
  const { id } = useParams<{ id: string }>();
  const [detail, setDetail] = useState<TransactionDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [activeTab, setActiveTab] = useState<'overview' | 'risk' | 'signals' | 'timeline' | 'entities' | 'report'>('overview');
  
  // Quick Disposition Modal state
  const [dispositionModalOpen, setDispositionModalOpen] = useState(false);
  const [disposition, setDisposition] = useState('LEGITIMATE_ACTIVITY');
  const [rationale, setRationale] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [actionSuccess, setActionSuccess] = useState('');

  const navigate = useNavigate();

  const fetchDetail = async () => {
    if (!id) return;
    setLoading(true);
    try {
      const res = await api.getTransactionDetail(id);
      setDetail(res);
    } catch (err) {
      console.error('Failed to load transaction detail', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchDetail();
  }, [id]);

  const handleRecordDisposition = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!detail?.related_cases?.[0]?.id) return;
    setSubmitting(true);
    try {
      await api.recordCaseDisposition(detail.related_cases[0].id, {
        disposition,
        rationale: rationale.trim() || 'Reviewed against transactional evidence and account behavioral baseline.',
        new_status: 'RESOLVED',
      });
      setActionSuccess('Compliance review disposition recorded successfully!');
      setTimeout(() => {
        setDispositionModalOpen(false);
        setActionSuccess('');
        fetchDetail();
      }, 1500);
    } catch (err) {
      console.error('Failed to record disposition', err);
    } finally {
      setSubmitting(false);
    }
  };

  if (loading) {
    return (
      <div className="py-20 text-center text-slate-500 dark:text-slate-400">
        <ShieldAlert className="h-8 w-8 animate-pulse mx-auto mb-2 text-sky-500 dark:text-cyan-400" />
        <p className="font-medium">Loading deep transaction intelligence dossier...</p>
      </div>
    );
  }

  if (!detail) {
    return (
      <div className="py-20 text-center text-slate-500 dark:text-slate-400">
        <p className="text-lg font-semibold">Transaction {id} was not found.</p>
        <button
          onClick={() => navigate('/transactions')}
          className="mt-4 px-4 py-2 rounded-lg bg-slate-900 text-white dark:bg-slate-800 text-xs font-semibold"
        >
          Return to Transactions
        </button>
      </div>
    );
  }

  const assessment = detail.assessment || detail.risk_assessment || {
    risk_score: 0,
    risk_level: 'LOW',
    requires_human_review: false,
    version: 'v1.0',
    summary: 'Standard assessment',
  };
  const overview = detail.overview;
  const signals = detail.signals || [];
  const timeline = detail.timeline || [];
  const related_cases = detail.related_cases || [];
  const report = detail.report || {
    title: 'Investigation Dossier',
    executive_summary: detail.investigation_report?.summary || 'No dossier recorded for this standard transaction.',
    risk_factors: detail.investigation_report?.risk_factors || [],
    recommended_action: detail.investigation_report?.recommended_action || 'ROUTINE_MONITORING',
    version: 'v1.0-preview',
  };
  const requiresReview = Boolean(assessment.requires_human_review || (assessment.risk_score && assessment.risk_score > 40.0));

  return (
    <div className="space-y-6 animate-in fade-in duration-200">
      {/* Top Breadcrumb & Actions Bar */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-4 border-b border-slate-200 dark:border-slate-800">
        <div className="flex items-center gap-3">
          <button
            onClick={() => navigate(-1)}
            className="p-2 text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-white rounded-lg hover:bg-slate-100 dark:hover:bg-slate-800 transition-colors"
          >
            <ArrowLeft className="h-5 w-5" />
          </button>
          <div>
            <div className="flex items-center gap-3">
              <h1 className="text-2xl font-bold tracking-tight text-slate-900 dark:text-white font-mono">
                {overview.external_id}
              </h1>
              <RiskBadge level={assessment.risk_level} score={assessment.risk_score} size="lg" />
              <StatusBadge status={overview.status} />
            </div>
            <p className="text-xs text-slate-500 dark:text-slate-400 mt-0.5">
              Initiated on {new Date(overview.timestamp).toLocaleString()} • {overview.transaction_type}
            </p>
          </div>
        </div>

        <div className="flex items-center gap-3">
          {related_cases?.[0] && (
            <button
              onClick={() => setDispositionModalOpen(true)}
              className="flex items-center gap-2 px-4 py-2 rounded-lg bg-gradient-to-r from-cyan-500 to-sky-500 text-slate-950 font-bold text-xs hover:brightness-110 shadow-lg shadow-cyan-500/20"
            >
              <CheckCircle2 className="h-4 w-4" />
              <span>Record Review Decision</span>
            </button>
          )}
        </div>
      </div>

      {/* Human Review Threshold Alert Banner (strictly score > 40%) */}
      {requiresReview && (
        <div className="omerta-card p-4 border-amber-300 dark:border-amber-500/40 bg-amber-50/80 dark:bg-gradient-to-r dark:from-amber-500/10 dark:via-slate-900/80 dark:to-slate-900 flex items-start gap-3 shadow-xs">
          <AlertTriangle className="h-5 w-5 text-amber-600 dark:text-amber-400 min-w-[1.25rem] mt-0.5" />
          <div className="space-y-1">
            <h4 className="text-sm font-bold text-amber-900 dark:text-amber-300">
              Flagged for Human Compliance Review (Rule: risk_score &gt; 40%)
            </h4>
            <p className="text-xs text-slate-700 dark:text-slate-300 leading-relaxed">
              This transaction received an estimated risk score of{' '}
              <strong className="text-slate-900 dark:text-white">{assessment.risk_score.toFixed(1)}%</strong>, which exceeds the 40.00%
              threshold. This is a risk estimate requiring human evaluation, not automated proof of financial crime.
            </p>
          </div>
        </div>
      )}

      {/* 6 Tabs Navigation Header */}
      <div className="flex items-center gap-2 border-b border-slate-200 dark:border-slate-800 overflow-x-auto pb-1 text-xs font-semibold">
        {[
          { key: 'overview', label: 'Overview', count: undefined },
          { key: 'risk', label: 'Risk Assessment', count: `${assessment.risk_score.toFixed(1)}%` },
          { key: 'signals', label: 'Risk Signals', count: signals.length },
          { key: 'timeline', label: 'Timeline', count: timeline.length },
          { key: 'entities', label: 'Related Entities', count: undefined },
          { key: 'report', label: 'Investigation Report', count: 'AI Dossier' },
        ].map((tab) => (
          <button
            key={tab.key}
            onClick={() => setActiveTab(tab.key as any)}
            className={`px-4 py-2.5 rounded-t-lg transition-all flex items-center gap-2 whitespace-nowrap ${
              activeTab === tab.key
                ? 'bg-sky-50 dark:bg-slate-800 text-sky-700 dark:text-cyan-400 border-b-2 border-sky-600 dark:border-cyan-400 font-bold'
                : 'text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-slate-200 hover:bg-slate-100 dark:hover:bg-slate-900/50'
            }`}
          >
            <span>{tab.label}</span>
            {tab.count !== undefined && (
              <span className="px-1.5 py-0.5 rounded text-[10px] font-mono bg-slate-200 dark:bg-slate-800 text-slate-800 dark:text-slate-300 font-bold">
                {tab.count}
              </span>
            )}
          </button>
        ))}
      </div>

      {/* TAB 1: OVERVIEW */}
      {activeTab === 'overview' && (
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 animate-in fade-in duration-150">
          <div className="lg:col-span-2 omerta-card p-6 space-y-6">
            <div>
              <h3 className="text-base font-bold text-slate-900 dark:text-white mb-3">Transaction Summary</h3>
              <div className="grid grid-cols-2 sm:grid-cols-3 gap-4">
                <div className="p-3.5 rounded-lg bg-slate-50 dark:bg-slate-900/80 border border-slate-200 dark:border-slate-800 space-y-1">
                  <span className="text-[11px] text-slate-500 dark:text-slate-400 uppercase font-bold">Gross Amount</span>
                  <p className="text-lg font-bold text-slate-900 dark:text-white font-mono">
                    {overview.amount.toLocaleString(undefined, { minimumFractionDigits: 2 })} {overview.currency}
                  </p>
                </div>
                <div className="p-3.5 rounded-lg bg-slate-50 dark:bg-slate-900/80 border border-slate-200 dark:border-slate-800 space-y-1">
                  <span className="text-[11px] text-slate-500 dark:text-slate-400 uppercase font-bold">Transaction Type</span>
                  <p className="text-base font-bold text-sky-700 dark:text-cyan-300">{overview.transaction_type}</p>
                </div>
                <div className="p-3.5 rounded-lg bg-slate-50 dark:bg-slate-900/80 border border-slate-200 dark:border-slate-800 space-y-1">
                  <span className="text-[11px] text-slate-500 dark:text-slate-400 uppercase font-bold">Execution Status</span>
                  <p className="text-base font-bold text-emerald-700 dark:text-emerald-400">{overview.status}</p>
                </div>
              </div>
            </div>

            {/* Money Flow Visual */}
            <div>
              <h3 className="text-base font-bold text-slate-900 dark:text-white mb-3">Source & Recipient Counterparties</h3>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                <div className="p-4 rounded-xl bg-slate-50 dark:bg-slate-900 border border-slate-200 dark:border-slate-800 space-y-2">
                  <div className="flex items-center gap-2 text-xs font-bold text-sky-700 dark:text-cyan-400">
                    <Wallet className="h-4 w-4" />
                    <span>Originating Source Account</span>
                  </div>
                  <div className="space-y-1">
                    <p className="text-sm font-bold text-slate-900 dark:text-white font-mono">{overview.source_account.external_id}</p>
                    <p className="text-xs font-medium text-slate-700 dark:text-slate-300">{overview.source_account.customer_name}</p>
                    <p className="text-[11px] text-slate-500 dark:text-slate-400">
                      Type: {overview.source_account.account_type} • Balance: {overview.source_account.balance.toLocaleString()} {overview.currency}
                    </p>
                  </div>
                </div>

                <div className="p-4 rounded-xl bg-slate-50 dark:bg-slate-900 border border-slate-200 dark:border-slate-800 space-y-2">
                  <div className="flex items-center gap-2 text-xs font-bold text-amber-700 dark:text-amber-400">
                    <Wallet className="h-4 w-4" />
                    <span>Destination Recipient Account</span>
                  </div>
                  <div className="space-y-1">
                    <p className="text-sm font-bold text-slate-900 dark:text-white font-mono">{overview.recipient_account.external_id}</p>
                    <p className="text-xs font-medium text-slate-700 dark:text-slate-300">{overview.recipient_account.customer_name}</p>
                    <p className="text-[11px] text-slate-500 dark:text-slate-400">Type: {overview.recipient_account.account_type}</p>
                  </div>
                </div>
              </div>
            </div>
          </div>

          {/* Device & Location Sidebar */}
          <div className="omerta-card p-6 space-y-6">
            <div>
              <h3 className="text-base font-bold text-slate-900 dark:text-white mb-3">Client & Network Telemetry</h3>
              <div className="space-y-3 text-xs">
                <div className="flex items-center justify-between p-3 rounded-lg bg-slate-50 dark:bg-slate-900 border border-slate-200 dark:border-slate-800">
                  <span className="text-slate-600 dark:text-slate-400 font-medium">Device Hardware:</span>
                  <span className="font-mono font-bold text-slate-900 dark:text-white">{overview.device?.external_id || 'N/A'}</span>
                </div>
                <div className="flex items-center justify-between p-3 rounded-lg bg-slate-50 dark:bg-slate-900 border border-slate-200 dark:border-slate-800">
                  <span className="text-slate-600 dark:text-slate-400 font-medium">Device Platform:</span>
                  <span className="text-slate-800 dark:text-slate-200 font-semibold">{overview.device?.platform || 'Android'}</span>
                </div>
                <div className="flex items-center justify-between p-3 rounded-lg bg-slate-50 dark:bg-slate-900 border border-slate-200 dark:border-slate-800">
                  <span className="text-slate-600 dark:text-slate-400 font-medium">Unrecognized Device:</span>
                  <span className={overview.is_new_device ? 'text-rose-700 dark:text-rose-400 font-bold' : 'text-emerald-700 dark:text-emerald-400 font-bold'}>
                    {overview.is_new_device ? 'YES (New Device)' : 'NO (Known Device)'}
                  </span>
                </div>
                <div className="flex items-center justify-between p-3 rounded-lg bg-slate-50 dark:bg-slate-900 border border-slate-200 dark:border-slate-800">
                  <span className="text-slate-600 dark:text-slate-400 font-medium">IP Observation:</span>
                  <span className="font-mono font-semibold text-slate-800 dark:text-slate-200">{overview.ip_address?.address || '197.45.10.12'}</span>
                </div>
                <div className="flex items-center justify-between p-3 rounded-lg bg-slate-50 dark:bg-slate-900 border border-slate-200 dark:border-slate-800">
                  <span className="text-slate-600 dark:text-slate-400 font-medium">Geo Country:</span>
                  <span className="text-slate-900 dark:text-white font-bold">{overview.ip_address?.country || 'EG'}</span>
                </div>
                <div className="flex items-center justify-between p-3 rounded-lg bg-slate-50 dark:bg-slate-900 border border-slate-200 dark:border-slate-800">
                  <span className="text-slate-600 dark:text-slate-400 font-medium">VPN / Proxy Flag:</span>
                  <span className={overview.ip_address?.is_vpn ? 'text-amber-700 dark:text-amber-400 font-bold' : 'text-slate-500 dark:text-slate-400'}>
                    {overview.ip_address?.is_vpn ? 'YES (VPN Detected)' : 'NO'}
                  </span>
                </div>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* TAB 2: RISK ASSESSMENT */}
      {activeTab === 'risk' && (
        <div className="omerta-card p-6 space-y-6 animate-in fade-in duration-150">
          <div className="flex flex-col sm:flex-row items-center justify-between gap-6 p-6 rounded-xl bg-slate-50 dark:bg-slate-900/90 border border-slate-200 dark:border-slate-800">
            <div className="space-y-2">
              <span className="text-xs uppercase tracking-wider font-bold text-slate-500 dark:text-slate-400">
                Aggregated Multi-Signal Risk Score
              </span>
              <div className="flex items-baseline gap-3">
                <span className="text-5xl font-black text-slate-900 dark:text-white font-mono">
                  {assessment.risk_score.toFixed(1)}%
                </span>
                <RiskBadge level={assessment.risk_level} size="lg" />
              </div>
              <p className="text-xs text-slate-600 dark:text-slate-400 max-w-xl">
                {assessment.summary || 'Computed using deterministic multi-tier behavioral and structural risk signals.'}
              </p>
            </div>

            <div className="text-right space-y-1 font-mono text-xs text-slate-600 dark:text-slate-400">
              <p>Version: <span className="text-slate-900 dark:text-slate-200 font-bold">{assessment.version || 'v1.0'}</span></p>
              <p>Correlation ID: <span className="text-slate-900 dark:text-slate-200 font-bold">{(assessment as any).correlation_id || 'CORR-TXN'}</span></p>
              <p>Review Required: <strong className={requiresReview ? 'text-amber-600 dark:text-amber-400 font-bold' : 'text-emerald-600 dark:text-emerald-400 font-bold'}>{requiresReview ? 'YES (>40%)' : 'NO'}</strong></p>
            </div>
          </div>

          <div>
            <h3 className="text-base font-bold text-slate-900 dark:text-white mb-3">Risk Assessment Architecture Pipeline</h3>
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 text-xs">
              <div className="p-4 rounded-xl bg-slate-50 dark:bg-slate-900 border border-slate-200 dark:border-slate-800 space-y-2">
                <div className="text-sky-700 dark:text-cyan-400 font-bold">1. Parallel Analyzer Pass</div>
                <p className="text-slate-600 dark:text-slate-400">Transaction rules, Device integrity checks, and IP Geolocation telemetry.</p>
              </div>
              <div className="p-4 rounded-xl bg-slate-50 dark:bg-slate-900 border border-slate-200 dark:border-slate-800 space-y-2">
                <div className="text-amber-700 dark:text-amber-400 font-bold">2. Multi-Signal Aggregator</div>
                <p className="text-slate-600 dark:text-slate-400">Combines independent signal impacts onto calibrated 0-100 score scale.</p>
              </div>
              <div className="p-4 rounded-xl bg-slate-50 dark:bg-slate-900 border border-slate-200 dark:border-slate-800 space-y-2">
                <div className="text-emerald-700 dark:text-emerald-400 font-bold">3. Human Review Dispatch</div>
                <p className="text-slate-600 dark:text-slate-400">Strict rule: score &gt; 40.00% queues case for compliance officer evaluation.</p>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* TAB 3: RISK SIGNALS */}
      {activeTab === 'signals' && (
        <div className="omerta-card p-6 space-y-4 animate-in fade-in duration-150">
          <h3 className="text-base font-bold text-slate-900 dark:text-white">Granular Contributing Signals ({signals.length})</h3>
          <div className="space-y-3">
            {signals.map((sig) => (
              <div
                key={sig.id}
                className="p-4 rounded-xl bg-slate-50 dark:bg-slate-900 border border-slate-200 dark:border-slate-800 flex items-start justify-between gap-4"
              >
                <div className="space-y-1">
                  <div className="flex items-center gap-2">
                    <span className="text-sm font-bold text-slate-900 dark:text-white">{sig.signal_name}</span>
                    <span className={`px-2 py-0.5 rounded text-[10px] font-bold ${
                      sig.severity === 'CRITICAL' ? 'bg-red-100 dark:bg-red-500/20 text-red-800 dark:text-red-400' :
                      sig.severity === 'HIGH' ? 'bg-rose-100 dark:bg-rose-500/20 text-rose-800 dark:text-rose-400' :
                      sig.severity === 'MEDIUM' ? 'bg-amber-100 dark:bg-amber-500/20 text-amber-800 dark:text-amber-400' : 'bg-slate-200 dark:bg-slate-800 text-slate-800 dark:text-slate-300'
                    }`}>
                      {sig.severity}
                    </span>
                  </div>
                  <p className="text-xs text-slate-700 dark:text-slate-300">{sig.description}</p>
                  <p className="text-[11px] text-slate-500 font-mono">
                    Source: {sig.source} • Evidence Ref: {sig.evidence_reference || 'N/A'} • Confidence: {(sig.confidence * 100).toFixed(0)}%
                  </p>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* TAB 4: TIMELINE */}
      {activeTab === 'timeline' && (
        <div className="omerta-card p-6 space-y-4 animate-in fade-in duration-150">
          <h3 className="text-base font-bold text-slate-900 dark:text-white">Chronological Transaction Lifecycle</h3>
          <div className="relative pl-6 border-l-2 border-slate-300 dark:border-slate-800 space-y-6 mt-4">
            {timeline.map((item, idx) => (
              <div key={idx} className="relative">
                <div className="absolute -left-[31px] top-1 h-3.5 w-3.5 rounded-full bg-sky-500 dark:bg-cyan-400 ring-4 ring-white dark:ring-slate-950" />
                <div className="space-y-1">
                  <div className="flex items-center gap-2">
                    <span className="text-xs font-bold text-slate-900 dark:text-white font-mono">{item.event || item.title || 'EVENT'}</span>
                    <span className="text-[11px] text-slate-500">
                      {new Date(item.timestamp).toLocaleTimeString()}
                    </span>
                  </div>
                  <p className="text-xs text-slate-700 dark:text-slate-300">{item.description}</p>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* TAB 5: RELATED ENTITIES */}
      {activeTab === 'entities' && (
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 animate-in fade-in duration-150">
          <div className="omerta-card p-5 space-y-3">
            <h4 className="text-xs font-bold uppercase text-slate-500 dark:text-slate-400 tracking-wider">Primary Customer</h4>
            {overview.customer ? (
              <div className="space-y-1 text-xs">
                <p className="text-sm font-bold text-slate-900 dark:text-white">{overview.customer.name}</p>
                <p className="text-slate-600 dark:text-slate-400 font-mono font-medium">{overview.customer.external_id}</p>
                <p className="text-slate-600 dark:text-slate-400">Type: {overview.customer.customer_type} • Country: {overview.customer.country}</p>
              </div>
            ) : <p className="text-xs text-slate-500">No linked customer profile.</p>}
          </div>

          <div className="omerta-card p-5 space-y-3">
            <h4 className="text-xs font-bold uppercase text-slate-500 dark:text-slate-400 tracking-wider">Associated Cases</h4>
            {related_cases.length > 0 ? (
              <div className="space-y-2">
                {related_cases.map((c: any) => (
                  <div key={c.id} className="p-2.5 rounded bg-slate-50 dark:bg-slate-900 text-xs flex justify-between items-center border border-slate-200 dark:border-slate-800">
                    <span className="font-mono font-bold text-slate-900 dark:text-white">{c.external_id}</span>
                    <StatusBadge status={c.status} />
                  </div>
                ))}
              </div>
            ) : <p className="text-xs text-slate-500">No active cases opened.</p>}
          </div>
        </div>
      )}

      {/* TAB 6: INVESTIGATION REPORT */}
      {activeTab === 'report' && (
        <div className="omerta-card p-6 space-y-6 animate-in fade-in duration-150">
          <div className="flex items-center justify-between pb-4 border-b border-slate-200 dark:border-slate-800">
            <div>
              <h3 className="text-base font-bold text-slate-900 dark:text-white flex items-center gap-2">
                <Sparkles className="h-4 w-4 text-sky-600 dark:text-cyan-400" />
                {report.title}
              </h3>
              <p className="text-xs text-slate-500 dark:text-slate-400">AI-generated evidence-backed investigation dossier</p>
            </div>
            <span className="px-2.5 py-0.5 rounded bg-sky-100 dark:bg-sky-500/10 text-sky-800 dark:text-cyan-300 font-mono text-xs font-bold border border-sky-300 dark:border-sky-500/20">
              {(report as any).version || 'v1.0'}
            </span>
          </div>

          <div className="space-y-4 text-xs leading-relaxed text-slate-800 dark:text-slate-200">
            <div className="p-4 rounded-xl bg-slate-50 dark:bg-slate-900 border border-slate-200 dark:border-slate-800 space-y-2">
              <h4 className="font-bold text-slate-600 dark:text-slate-300 uppercase tracking-wider text-[11px]">Executive Summary</h4>
              <p>{report.executive_summary}</p>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <div className="p-4 rounded-xl bg-slate-50 dark:bg-slate-900 border border-slate-200 dark:border-slate-800 space-y-2">
                <h4 className="font-bold text-slate-600 dark:text-slate-300 uppercase tracking-wider text-[11px]">Identified Risk Factors</h4>
                <ul className="list-disc pl-4 space-y-1 text-slate-700 dark:text-slate-300">
                  {(report.risk_factors || []).map((rf: string, i: number) => (
                    <li key={i}>{rf}</li>
                  ))}
                </ul>
              </div>

              <div className="p-4 rounded-xl bg-slate-50 dark:bg-slate-900 border border-slate-200 dark:border-slate-800 space-y-2">
                <h4 className="font-bold text-slate-600 dark:text-slate-300 uppercase tracking-wider text-[11px]">Recommended Action</h4>
                <p className="text-sm font-bold text-sky-700 dark:text-cyan-300">{report.recommended_action}</p>
                <p className="text-slate-500 dark:text-slate-400 text-[11px]">
                  Requires human compliance sign-off prior to filing any regulatory documentation.
                </p>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Record Disposition Dialog Modal */}
      <Modal
        isOpen={dispositionModalOpen}
        onClose={() => setDispositionModalOpen(false)}
        title="Record Compliance Review Disposition"
        subtitle={`Case ${related_cases?.[0]?.external_id || 'CASE-001'} • Transaction ${overview.external_id}`}
      >
        <form onSubmit={handleRecordDisposition} className="space-y-4 text-xs">
          {actionSuccess && (
            <div className="p-3 rounded-lg bg-emerald-100 dark:bg-emerald-500/15 border border-emerald-300 dark:border-emerald-500/30 text-emerald-900 dark:text-emerald-300 font-bold">
              {actionSuccess}
            </div>
          )}

          <div className="space-y-1.5">
            <label className="text-slate-800 dark:text-slate-200 font-bold">Analyst Disposition</label>
            <select
              value={disposition}
              onChange={(e) => setDisposition(e.target.value)}
              className="w-full p-2.5 bg-slate-50 dark:bg-slate-900 border border-slate-300 dark:border-slate-700 rounded-lg text-slate-900 dark:text-white font-medium focus:outline-none focus:border-sky-500 dark:focus:border-cyan-400"
            >
              <option value="LEGITIMATE_ACTIVITY">Legitimate Activity (No Further Action)</option>
              <option value="NO_SUSPICIOUS_ACTIVITY">No Suspicious Activity Identified</option>
              <option value="SUSPICIOUS_FURTHER_INVESTIGATION">Suspicious — Further Investigation Required</option>
              <option value="INSUFFICIENT_EVIDENCE">Insufficient Evidence</option>
              <option value="ESCALATED_SPECIALIST">Escalated for Specialist AML Review</option>
            </select>
          </div>

          <div className="space-y-1.5">
            <label className="text-slate-800 dark:text-slate-200 font-bold">Investigative Rationale & Findings</label>
            <textarea
              rows={4}
              value={rationale}
              onChange={(e) => setRationale(e.target.value)}
              placeholder="State the reasons for this disposition based on reviewed transactional evidence..."
              className="w-full p-2.5 bg-slate-50 dark:bg-slate-900 border border-slate-300 dark:border-slate-700 rounded-lg text-slate-900 dark:text-white placeholder-slate-400 dark:placeholder-slate-500 font-medium focus:outline-none focus:border-sky-500 dark:focus:border-cyan-400"
            />
          </div>

          <div className="pt-2 flex items-center justify-end gap-2">
            <button
              type="button"
              onClick={() => setDispositionModalOpen(false)}
              className="px-3.5 py-2 rounded-lg bg-slate-100 dark:bg-slate-800 text-slate-700 dark:text-slate-300 hover:bg-slate-200 dark:hover:bg-slate-700 font-semibold border border-slate-300 dark:border-slate-700"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={submitting}
              className="px-4 py-2 rounded-lg bg-gradient-to-r from-sky-500 to-cyan-500 text-slate-950 font-bold hover:brightness-110 disabled:opacity-50 shadow-sm"
            >
              {submitting ? 'Recording...' : 'Confirm Disposition'}
            </button>
          </div>
        </form>
      </Modal>
    </div>
  );
};
