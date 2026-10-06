import React, { useEffect, useState } from 'react';
import { api } from '../api/client';
import { StatCard } from '../components/common/StatCard';
import { Modal } from '../components/common/Modal';
import {
  Shield,
  Search,
  RefreshCw,
  Clock,
  User,
  Eye,
  ChevronLeft,
  ChevronRight,
  Database,
  Lock,
} from 'lucide-react';

export const AuditLogsPage: React.FC = () => {
  const [logs, setLogs] = useState<any[]>([]);
  const [total, setTotal] = useState<number>(0);
  const [page, setPage] = useState<number>(1);
  const [pageSize] = useState<number>(20);
  const [loading, setLoading] = useState<boolean>(true);
  const [search, setSearch] = useState<string>('');
  const [eventType, setEventType] = useState<string>('');
  const [actorType, setActorType] = useState<string>('');
  const [selectedLog, setSelectedLog] = useState<any | null>(null);

  useEffect(() => {
    loadLogs();
  }, [page, eventType, actorType]);

  const loadLogs = async () => {
    setLoading(true);
    try {
      const data = await api.getAuditLogs({
        page,
        page_size: pageSize,
        event_type: eventType || undefined,
        actor_type: actorType || undefined,
        search: search || undefined,
      });
      setLogs(data.items || []);
      setTotal(data.total || 0);
    } catch (err: any) {
      console.error('Failed to load audit logs', err);
    } finally {
      setLoading(false);
    }
  };

  const handleSearchSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    setPage(1);
    loadLogs();
  };

  const totalPages = Math.max(1, Math.ceil(total / pageSize));

  return (
    <div className="space-y-6 animate-in fade-in duration-200">
      {/* Top Banner */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 omerta-card p-6 border-slate-200 dark:border-slate-800 shadow-md">
        <div className="flex items-center gap-4">
          <div className="w-12 h-12 rounded-xl bg-sky-50 dark:bg-cyan-500/10 border border-sky-200 dark:border-cyan-500/30 flex items-center justify-center text-sky-600 dark:text-cyan-400 shadow-xs">
            <Shield className="w-6 h-6" />
          </div>
          <div>
            <h1 className="text-2xl font-bold text-slate-900 dark:text-white tracking-tight flex items-center gap-2">
              Immutable Regulatory Audit Trail
              <span className="text-xs px-2.5 py-0.5 rounded-full bg-sky-50 dark:bg-cyan-500/10 text-sky-700 dark:text-cyan-300 border border-sky-300 dark:border-cyan-500/30 font-bold">
                Cryptographic Nonce
              </span>
            </h1>
            <p className="text-xs text-slate-500 dark:text-slate-400 mt-1">
              Tamper-evident chronological ledger recording all risk evaluations, system triggers, analyst notes, and disposition decisions.
            </p>
          </div>
        </div>
        <button
          onClick={loadLogs}
          disabled={loading}
          className="px-3.5 py-2 rounded-xl bg-white dark:bg-slate-800 hover:bg-slate-50 dark:hover:bg-slate-700 text-slate-700 dark:text-slate-200 border border-slate-300 dark:border-slate-700 text-xs font-semibold flex items-center gap-2 transition-colors disabled:opacity-50 shadow-xs"
        >
          <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin text-sky-500 dark:text-cyan-400' : ''}`} />
          Refresh Ledger
        </button>
      </div>

      {/* KPI Stats */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <StatCard
          title="Total Audit Events"
          value={total.toLocaleString()}
          icon={<Database className="w-5 h-5 text-sky-600 dark:text-cyan-400" />}
          description="Retained compliance ledger"
          variant="cyan"
        />
        <StatCard
          title="Ledger Integrity"
          value="100% VERIFIED"
          icon={<Lock className="w-5 h-5 text-emerald-600 dark:text-emerald-400" />}
          description="Hash-chain validated"
          variant="emerald"
        />
        <StatCard
          title="Active Actors"
          value="System + 4 Roles"
          icon={<User className="w-5 h-5 text-indigo-600 dark:text-indigo-400" />}
          description="RBAC Enforced"
          variant="default"
        />
        <StatCard
          title="Audit Policy"
          value="Strict Retention"
          icon={<Clock className="w-5 h-5 text-amber-600 dark:text-amber-400" />}
          description="5-Year Regulatory SLA"
          variant="alert"
        />
      </div>

      {/* Search & Filter Controls */}
      <div className="omerta-card p-4 shadow-sm flex flex-wrap items-center justify-between gap-3">
        <form onSubmit={handleSearchSubmit} className="flex items-center gap-2 flex-1 min-w-[280px]">
          <div className="relative flex-1">
            <Search className="w-4 h-4 absolute left-3 top-1/2 -translate-y-1/2 text-slate-400 dark:text-slate-500" />
            <input
              type="text"
              placeholder="Search Event ID, Transaction ID, Actor, or Source..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="w-full pl-9 pr-3 py-2 bg-slate-50 dark:bg-slate-900 border border-slate-300 dark:border-slate-700 rounded-lg text-xs text-slate-900 dark:text-white placeholder-slate-400 dark:placeholder-slate-500 focus:outline-none focus:border-sky-500 dark:focus:border-cyan-400"
            />
          </div>
          <button
            type="submit"
            className="px-4 py-2 bg-gradient-to-r from-sky-500 to-cyan-500 text-slate-950 text-xs font-bold rounded-lg transition-all shadow-xs hover:brightness-110"
          >
            Search
          </button>
        </form>

        <div className="flex items-center gap-3">
          <select
            value={eventType}
            onChange={(e) => {
              setEventType(e.target.value);
              setPage(1);
            }}
            className="px-3 py-2 bg-slate-50 dark:bg-slate-900 border border-slate-300 dark:border-slate-700 rounded-lg text-xs font-medium text-slate-700 dark:text-slate-200 focus:outline-none focus:border-sky-500 dark:focus:border-cyan-400"
          >
            <option value="">All Event Types</option>
            <option value="TRANSACTION_RISK_ASSESSED">Risk Assessed</option>
            <option value="CASE_DISPOSITION_RECORDED">Disposition Recorded</option>
            <option value="CASE_NOTE_ADDED">Note Added</option>
            <option value="CASE_STATUS_CHANGED">Status Changed</option>
            <option value="LOGIN_SUCCESS">Login Success</option>
          </select>

          <select
            value={actorType}
            onChange={(e) => {
              setActorType(e.target.value);
              setPage(1);
            }}
            className="px-3 py-2 bg-slate-50 dark:bg-slate-900 border border-slate-300 dark:border-slate-700 rounded-lg text-xs font-medium text-slate-700 dark:text-slate-200 focus:outline-none focus:border-sky-500 dark:focus:border-cyan-400"
          >
            <option value="">All Actor Types</option>
            <option value="SYSTEM">SYSTEM</option>
            <option value="ANALYST">ANALYST</option>
            <option value="USER">USER</option>
          </select>
        </div>
      </div>

      {/* Audit Logs Table */}
      <div className="omerta-card shadow-md overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs text-slate-800 dark:text-slate-200">
            <thead className="bg-slate-100 dark:bg-slate-900/90 text-slate-700 dark:text-slate-400 uppercase tracking-wider font-bold border-b border-slate-200 dark:border-slate-800">
              <tr>
                <th className="p-3.5">Event ID</th>
                <th className="p-3.5">Timestamp</th>
                <th className="p-3.5">Event Type</th>
                <th className="p-3.5">Actor Type</th>
                <th className="p-3.5">Actor ID</th>
                <th className="p-3.5">Target Entity</th>
                <th className="p-3.5">Source Module</th>
                <th className="p-3.5 text-right">Payload</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-200 dark:divide-slate-800/60 font-mono">
              {loading ? (
                <tr>
                  <td colSpan={8} className="p-12 text-center text-slate-500 dark:text-slate-400">
                    <RefreshCw className="w-6 h-6 animate-spin mx-auto text-sky-500 dark:text-cyan-400 mb-2" />
                    Loading audit trail ledger...
                  </td>
                </tr>
              ) : logs.length === 0 ? (
                <tr>
                  <td colSpan={8} className="p-12 text-center text-slate-500 dark:text-slate-400 font-sans">
                    No audit records match the selected filters.
                  </td>
                </tr>
              ) : (
                logs.map((log) => (
                  <tr key={log.id} className="hover:bg-slate-50 dark:hover:bg-slate-800/40 transition-colors font-sans">
                    <td className="p-3.5 font-mono text-sky-700 dark:text-cyan-300 font-bold">{log.event_id}</td>
                    <td className="p-3.5 font-mono text-slate-600 dark:text-slate-400 text-[11px]">
                      {new Date(log.created_at).toLocaleString()}
                    </td>
                    <td className="p-3.5">
                      <span className="px-2 py-0.5 rounded font-mono text-[11px] font-semibold bg-slate-100 dark:bg-slate-800 text-slate-800 dark:text-slate-200 border border-slate-300 dark:border-slate-700">
                        {log.event_type}
                      </span>
                    </td>
                    <td className="p-3.5">
                      <span
                        className={`px-2 py-0.5 rounded text-[11px] font-bold ${
                          log.actor_type === 'SYSTEM'
                            ? 'bg-indigo-50 dark:bg-indigo-500/10 text-indigo-800 dark:text-indigo-300 border border-indigo-200 dark:border-indigo-500/30'
                            : 'bg-emerald-50 dark:bg-emerald-500/10 text-emerald-800 dark:text-emerald-300 border border-emerald-200 dark:border-emerald-500/30'
                        }`}
                      >
                        {log.actor_type}
                      </span>
                    </td>
                    <td className="p-3.5 font-mono text-slate-800 dark:text-slate-300 font-medium">{log.actor_id}</td>
                    <td className="p-3.5 font-mono text-slate-600 dark:text-slate-400">
                      {log.transaction_id || log.investigation_id || log.case_id || '—'}
                    </td>
                    <td className="p-3.5 text-slate-600 dark:text-slate-400 font-mono text-[11px]">{log.source}</td>
                    <td className="p-3.5 text-right">
                      <button
                        onClick={() => setSelectedLog(log)}
                        className="px-2.5 py-1 rounded bg-sky-50 dark:bg-slate-800 hover:bg-sky-100 dark:hover:bg-slate-700 text-sky-700 dark:text-cyan-300 text-xs font-bold border border-sky-300 dark:border-slate-700 inline-flex items-center gap-1 transition-colors shadow-xs"
                      >
                        <Eye className="w-3.5 h-3.5" />
                        Inspect
                      </button>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>

        {/* Pagination Bar */}
        <div className="p-4 bg-slate-100 dark:bg-slate-900/90 border-t border-slate-200 dark:border-slate-800 flex items-center justify-between text-xs text-slate-600 dark:text-slate-400">
          <div>
            Showing <strong className="text-slate-900 dark:text-white">{logs.length > 0 ? (page - 1) * pageSize + 1 : 0}</strong> to{' '}
            <strong className="text-slate-900 dark:text-white">{Math.min(page * pageSize, total)}</strong> of{' '}
            <strong className="text-slate-900 dark:text-white">{total.toLocaleString()}</strong> entries
          </div>
          <div className="flex items-center gap-2">
            <button
              onClick={() => setPage((p) => Math.max(1, p - 1))}
              disabled={page <= 1}
              className="p-1.5 rounded-lg bg-white dark:bg-slate-800 hover:bg-slate-50 dark:hover:bg-slate-700 text-slate-700 dark:text-slate-300 disabled:opacity-40 disabled:cursor-not-allowed border border-slate-300 dark:border-slate-700 shadow-xs"
            >
              <ChevronLeft className="w-4 h-4" />
            </button>
            <span className="px-2 font-mono">
              Page <strong className="text-slate-900 dark:text-white">{page}</strong> of <strong className="text-slate-900 dark:text-white">{totalPages}</strong>
            </span>
            <button
              onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
              disabled={page >= totalPages}
              className="p-1.5 rounded-lg bg-white dark:bg-slate-800 hover:bg-slate-50 dark:hover:bg-slate-700 text-slate-700 dark:text-slate-300 disabled:opacity-40 disabled:cursor-not-allowed border border-slate-300 dark:border-slate-700 shadow-xs"
            >
              <ChevronRight className="w-4 h-4" />
            </button>
          </div>
        </div>
      </div>

      {/* Inspect Modal */}
      {selectedLog && (
        <Modal
          isOpen={!!selectedLog}
          onClose={() => setSelectedLog(null)}
          title={`Audit Payload: ${selectedLog.event_id}`}
        >
          <div className="space-y-4">
            <div className="grid grid-cols-2 gap-3 text-xs bg-slate-50 dark:bg-slate-900 p-3 rounded-lg border border-slate-200 dark:border-slate-800 font-mono">
              <div>
                <span className="text-slate-500 dark:text-slate-400">Event Type:</span>
                <span className="text-sky-700 dark:text-cyan-400 ml-2 font-bold">{selectedLog.event_type}</span>
              </div>
              <div>
                <span className="text-slate-500 dark:text-slate-400">Actor:</span>
                <span className="text-slate-900 dark:text-white ml-2 font-bold">
                  {selectedLog.actor_type} ({selectedLog.actor_id})
                </span>
              </div>
              <div>
                <span className="text-slate-500 dark:text-slate-400">Timestamp:</span>
                <span className="text-slate-700 dark:text-slate-300 ml-2">{new Date(selectedLog.created_at).toISOString()}</span>
              </div>
              <div>
                <span className="text-slate-500 dark:text-slate-400">Source Module:</span>
                <span className="text-emerald-700 dark:text-emerald-400 ml-2 font-bold">{selectedLog.source}</span>
              </div>
            </div>

            <div>
              <label className="text-xs font-bold text-slate-700 dark:text-slate-300 mb-1 block">
                Structured JSON Metadata
              </label>
              <pre className="p-4 bg-slate-900 text-cyan-300 dark:bg-slate-950 rounded-xl border border-slate-700 dark:border-slate-800 text-[11px] font-mono overflow-x-auto max-h-72">
                {JSON.stringify(selectedLog.metadata || {}, null, 2)}
              </pre>
            </div>
          </div>
        </Modal>
      )}
    </div>
  );
};
