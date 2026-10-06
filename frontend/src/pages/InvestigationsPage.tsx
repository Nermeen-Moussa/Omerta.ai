import React, { useEffect, useState } from 'react';
import {
  FolderSearch,
  RefreshCw,
  ChevronLeft,
  ChevronRight,
} from 'lucide-react';
import { api } from '../api/client';
import type { CaseItem } from '../types';
import { StatusBadge } from '../components/common/StatusBadge';
import { RiskBadge } from '../components/common/RiskBadge';
import { Modal } from '../components/common/Modal';

export const InvestigationsPage: React.FC = () => {
  const [cases, setCases] = useState<CaseItem[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [statusFilter, setStatusFilter] = useState('');
  const [severityFilter, setSeverityFilter] = useState('');
  const [page, setPage] = useState(1);

  // Case Dossier Modal state
  const [selectedCase, setSelectedCase] = useState<any | null>(null);
  const [dossierLoading, setDossierLoading] = useState(false);

  const fetchCases = async () => {
    setLoading(true);
    try {
      const res = await api.getCases({
        status: statusFilter,
        severity: severityFilter,
        page,
        page_size: 15,
      });
      setCases(res.items || []);
      setTotal(res.total || 0);
    } catch (err) {
      console.error('Failed to load investigation cases', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchCases();
  }, [page, statusFilter, severityFilter]);

  const handleOpenDossier = async (c: CaseItem) => {
    setDossierLoading(true);
    try {
      const res = await api.getCaseDetail(c.external_id);
      setSelectedCase(res);
    } catch (err) {
      console.error('Failed to load case detail', err);
    } finally {
      setDossierLoading(false);
    }
  };

  return (
    <div className="space-y-6 animate-in fade-in duration-200">
      {/* Page Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-slate-900 dark:text-white flex items-center gap-2">
            <FolderSearch className="h-6 w-6 text-sky-600 dark:text-cyan-400" />
            Compliance Investigation Cases
          </h1>
          <p className="text-xs text-slate-500 dark:text-slate-400 mt-1">
            Formal compliance dossiers opened for high-priority alerts and suspicious transaction patterns.
          </p>
        </div>

        <div className="flex items-center gap-2.5">
          <span className="px-3 py-1.5 rounded-lg bg-sky-50 dark:bg-slate-900 text-sky-800 dark:text-cyan-300 font-mono text-xs font-bold border border-sky-300 dark:border-slate-700 shadow-xs">
            {total} Active Cases
          </span>
          <button
            onClick={fetchCases}
            className="flex items-center gap-2 px-3.5 py-2 rounded-lg bg-white dark:bg-slate-900 border border-slate-300 dark:border-slate-700 text-xs font-semibold text-slate-700 dark:text-slate-200 hover:bg-slate-50 dark:hover:bg-slate-800 transition-colors shadow-sm"
          >
            <RefreshCw className={`h-3.5 w-3.5 ${loading ? 'animate-spin text-sky-500 dark:text-cyan-400' : ''}`} />
            <span>Refresh</span>
          </button>
        </div>
      </div>

      {/* Filter Bar */}
      <div className="omerta-card p-4 flex items-center justify-between gap-4 flex-wrap">
        <div className="flex items-center gap-3 flex-wrap">
          <select
            value={statusFilter}
            onChange={(e) => {
              setStatusFilter(e.target.value);
              setPage(1);
            }}
            className="px-3 py-2 bg-slate-50 dark:bg-slate-900 border border-slate-300 dark:border-slate-700 rounded-lg text-xs font-medium text-slate-700 dark:text-slate-200 focus:outline-none focus:border-sky-500 dark:focus:border-cyan-400"
          >
            <option value="">All Case Statuses</option>
            <option value="NEW">New</option>
            <option value="UNDER_INVESTIGATION">Under Investigation</option>
            <option value="ESCALATED">Escalated</option>
            <option value="RESOLVED">Resolved</option>
          </select>

          <select
            value={severityFilter}
            onChange={(e) => {
              setSeverityFilter(e.target.value);
              setPage(1);
            }}
            className="px-3 py-2 bg-slate-50 dark:bg-slate-900 border border-slate-300 dark:border-slate-700 rounded-lg text-xs font-medium text-slate-700 dark:text-slate-200 focus:outline-none focus:border-sky-500 dark:focus:border-cyan-400"
          >
            <option value="">All Severities</option>
            <option value="HIGH">High Severity</option>
            <option value="MEDIUM">Medium Severity</option>
            <option value="LOW">Low Severity</option>
          </select>
        </div>
      </div>

      {/* Cases Table */}
      <div className="omerta-card overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs">
            <thead className="bg-slate-100 dark:bg-slate-900/90 text-slate-700 dark:text-slate-400 border-b border-slate-200 dark:border-slate-800 uppercase text-[10px] tracking-wider font-bold">
              <tr>
                <th className="py-3.5 px-4">Case ID</th>
                <th className="py-3.5 px-4">Title / Scenario</th>
                <th className="py-3.5 px-4">Severity</th>
                <th className="py-3.5 px-4">Status</th>
                <th className="py-3.5 px-4">Assigned Analyst</th>
                <th className="py-3.5 px-4">Related Alert / Txn</th>
                <th className="py-3.5 px-4">Opened Date</th>
                <th className="py-3.5 px-4 text-right">Dossier</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-200 dark:divide-slate-800/60 text-slate-800 dark:text-slate-300">
              {loading ? (
                <tr>
                  <td colSpan={8} className="py-12 text-center text-slate-500 dark:text-slate-400">
                    <RefreshCw className="h-6 w-6 animate-spin mx-auto mb-2 text-sky-500 dark:text-cyan-400" />
                    <span>Loading investigation cases...</span>
                  </td>
                </tr>
              ) : cases.length === 0 ? (
                <tr>
                  <td colSpan={8} className="py-12 text-center text-slate-500 dark:text-slate-400">
                    No cases match the selected filter criteria.
                  </td>
                </tr>
              ) : (
                cases.map((c) => (
                  <tr
                    key={c.id}
                    onClick={() => handleOpenDossier(c)}
                    className="hover:bg-slate-50 dark:hover:bg-slate-800/50 cursor-pointer transition-colors group"
                  >
                    <td className="py-3.5 px-4 font-mono font-bold text-sky-700 dark:text-cyan-300 group-hover:underline">
                      {c.external_id}
                    </td>
                    <td className="py-3.5 px-4 font-semibold text-slate-900 dark:text-white max-w-xs truncate">
                      {c.title}
                    </td>
                    <td className="py-3.5 px-4">
                      <RiskBadge level={c.severity} size="sm" />
                    </td>
                    <td className="py-3.5 px-4">
                      <StatusBadge status={c.status} />
                    </td>
                    <td className="py-3.5 px-4 text-slate-800 dark:text-slate-300 font-medium">
                      {c.assigned_to || <span className="text-slate-500 italic">Unassigned</span>}
                    </td>
                    <td className="py-3.5 px-4 font-mono text-xs text-slate-600 dark:text-slate-400">
                      {c.alert_id || c.transaction_id || 'N/A'}
                    </td>
                    <td className="py-3.5 px-4 text-slate-600 dark:text-slate-400 whitespace-nowrap">
                      {new Date(c.created_at).toLocaleDateString()}
                    </td>
                    <td className="py-3.5 px-4 text-right">
                      <button
                        onClick={(e) => {
                          e.stopPropagation();
                          handleOpenDossier(c);
                        }}
                        disabled={dossierLoading}
                        className="px-2.5 py-1 text-xs font-bold rounded bg-sky-50 dark:bg-sky-500/10 text-sky-700 dark:text-cyan-400 hover:bg-sky-100 dark:hover:bg-sky-500/20 border border-sky-300 dark:border-sky-500/30 disabled:opacity-50 shadow-xs"
                      >
                        {dossierLoading ? 'Loading...' : 'Inspect'}
                      </button>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>

        {/* Pagination Bar */}
        <div className="flex items-center justify-between px-4 py-3 bg-slate-100 dark:bg-slate-900/90 border-t border-slate-200 dark:border-slate-800 text-xs text-slate-600 dark:text-slate-400">
          <span>Showing <strong className="text-slate-900 dark:text-white">{cases.length}</strong> of <strong className="text-slate-900 dark:text-white">{total}</strong> cases</span>
          <div className="flex items-center gap-2">
            <button
              disabled={page <= 1 || loading}
              onClick={() => setPage((p) => Math.max(1, p - 1))}
              className="p-1.5 rounded-lg border border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-800 text-slate-700 dark:text-slate-300 disabled:opacity-40 hover:bg-slate-50 dark:hover:bg-slate-700 shadow-xs"
            >
              <ChevronLeft className="h-4 w-4" />
            </button>
            <span>Page <strong className="text-slate-900 dark:text-white">{page}</strong></span>
            <button
              disabled={cases.length < 15 || loading}
              onClick={() => setPage((p) => p + 1)}
              className="p-1.5 rounded-lg border border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-800 text-slate-700 dark:text-slate-300 disabled:opacity-40 hover:bg-slate-50 dark:hover:bg-slate-700 shadow-xs"
            >
              <ChevronRight className="h-4 w-4" />
            </button>
          </div>
        </div>
      </div>

      {/* Case Dossier Inspection Modal */}
      <Modal
        isOpen={!!selectedCase}
        onClose={() => setSelectedCase(null)}
        title={selectedCase?.case?.title || 'Investigation Dossier'}
        subtitle={`Case ID: ${selectedCase?.case?.external_id}`}
        maxWidth="2xl"
      >
        {selectedCase && (
          <div className="space-y-5 text-xs">
            <div className="p-4 rounded-xl bg-slate-50 dark:bg-slate-900 border border-slate-200 dark:border-slate-800 space-y-2">
              <h4 className="font-bold text-slate-700 dark:text-slate-300 uppercase tracking-wider text-[11px]">Investigation Summary</h4>
              <p className="text-slate-800 dark:text-slate-200 leading-relaxed">
                {selectedCase.case?.report?.summary || 'Formal case file reviewing multi-signal risk anomalies.'}
              </p>
              <div className="pt-2 flex items-center gap-3">
                <span className="text-slate-600 dark:text-slate-400 font-medium">Recommended Action:</span>
                <span className="font-bold text-sky-700 dark:text-cyan-300">{selectedCase.case?.report?.recommended_action || 'HUMAN_REVIEW'}</span>
              </div>
            </div>

            {/* Notes Section */}
            <div>
              <h4 className="font-bold text-slate-700 dark:text-slate-300 uppercase tracking-wider text-[11px] mb-2">
                Analyst Notes ({selectedCase.notes?.length || 0})
              </h4>
              <div className="space-y-2">
                {(selectedCase.notes || []).map((n: any) => (
                  <div key={n.id} className="p-3 rounded-lg bg-slate-50 dark:bg-slate-900 border border-slate-200 dark:border-slate-800">
                    <div className="flex justify-between text-[11px] text-slate-500 dark:text-slate-400 mb-1">
                      <span className="font-bold text-slate-900 dark:text-white">{n.author}</span>
                      <span>{new Date(n.created_at).toLocaleString()}</span>
                    </div>
                    <p className="text-slate-700 dark:text-slate-300">{n.note_text}</p>
                  </div>
                ))}
              </div>
            </div>

            {/* Dispositions Recorded */}
            <div>
              <h4 className="font-bold text-slate-700 dark:text-slate-300 uppercase tracking-wider text-[11px] mb-2">
                Recorded Dispositions ({selectedCase.dispositions?.length || 0})
              </h4>
              <div className="space-y-2">
                {(selectedCase.dispositions || []).map((d: any) => (
                  <div key={d.id} className="p-3 rounded-lg bg-slate-50 dark:bg-slate-900 border border-slate-200 dark:border-slate-800">
                    <div className="flex justify-between text-[11px] text-slate-500 dark:text-slate-400 mb-1">
                      <span className="font-bold text-emerald-700 dark:text-emerald-400">{d.disposition.replace(/_/g, ' ')}</span>
                      <span>{new Date(d.recorded_at).toLocaleString()}</span>
                    </div>
                    <p className="text-slate-700 dark:text-slate-300">{d.rationale}</p>
                  </div>
                ))}
              </div>
            </div>
          </div>
        )}
      </Modal>
    </div>
  );
};
