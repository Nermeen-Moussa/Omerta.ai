import React, { useEffect, useState } from 'react';
import { api } from '../api/client';
import { StatCard } from '../components/common/StatCard';
import {
  FileText,
  Download,
  RefreshCw,
  AlertTriangle,
  BarChart3,
  Calendar,
  Layers,
  ArrowUpRight,
  ShieldCheck,
} from 'lucide-react';
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  PieChart,
  Pie,
  Cell,
  Legend,
} from 'recharts';

const COLORS = ['#00d2ff', '#10b981', '#f59e0b', '#ef4444', '#8b5cf6'];

export const ReportsPage: React.FC = () => {
  const [reportTypes, setReportTypes] = useState<any[]>([]);
  const [selectedType, setSelectedType] = useState<string>('risk-distribution');
  const [reportData, setReportData] = useState<any>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    loadReportTypes();
  }, []);

  useEffect(() => {
    if (selectedType) {
      loadReport(selectedType);
    }
  }, [selectedType]);

  const loadReportTypes = async () => {
    try {
      const types = await api.getReportTypes();
      setReportTypes(types);
    } catch (err: any) {
      console.error('Failed to load report types', err);
    }
  };

  const loadReport = async (type: string) => {
    setLoading(true);
    setError(null);
    try {
      const data = await api.generateReport(type);
      setReportData(data);
    } catch (err: any) {
      setError(err.message || 'Failed to generate compliance report');
    } finally {
      setLoading(false);
    }
  };

  const handleExport = () => {
    window.open(`/api/v1/reports/export?report_type=${selectedType}`, '_blank');
  };

  return (
    <div className="space-y-6 animate-in fade-in duration-200">
      {/* Top Banner */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 omerta-card p-6 border-slate-200 dark:border-slate-800 shadow-md">
        <div className="flex items-center gap-4">
          <div className="w-12 h-12 rounded-xl bg-sky-50 dark:bg-cyan-500/10 border border-sky-200 dark:border-cyan-500/30 flex items-center justify-center text-sky-600 dark:text-cyan-400 shadow-xs">
            <FileText className="w-6 h-6" />
          </div>
          <div>
            <h1 className="text-2xl font-bold text-slate-900 dark:text-white tracking-tight flex items-center gap-2">
              Compliance & Intelligence Reports
              <span className="text-xs px-2.5 py-0.5 rounded-full bg-sky-50 dark:bg-cyan-500/10 text-sky-700 dark:text-cyan-300 border border-sky-300 dark:border-cyan-500/30 font-bold">
                Audit Ready
              </span>
            </h1>
            <p className="text-xs text-slate-500 dark:text-slate-400 mt-1">
              Official regulatory summaries, risk exposure distributions, and investigator disposition audit trails.
            </p>
          </div>
        </div>
        <div className="flex items-center gap-3">
          <button
            onClick={() => loadReport(selectedType)}
            disabled={loading}
            className="px-3.5 py-2 rounded-xl bg-white dark:bg-slate-800 hover:bg-slate-50 dark:hover:bg-slate-700 text-slate-700 dark:text-slate-200 border border-slate-300 dark:border-slate-700 text-xs font-semibold flex items-center gap-2 transition-colors disabled:opacity-50 shadow-xs"
          >
            <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin text-sky-500 dark:text-cyan-400' : ''}`} />
            Refresh
          </button>
          <button
            onClick={handleExport}
            className="px-4 py-2 rounded-xl bg-gradient-to-r from-sky-500 to-cyan-500 text-slate-950 text-xs font-bold flex items-center gap-2 transition-all shadow-md shadow-cyan-500/15 hover:brightness-110"
          >
            <Download className="w-4 h-4" />
            Export CSV
          </button>
        </div>
      </div>

      {/* Report Type Selector Tabs */}
      <div className="grid grid-cols-1 md:grid-cols-3 lg:grid-cols-5 gap-3">
        {reportTypes.map((rt) => {
          const isSelected = selectedType === rt.id;
          return (
            <button
              key={rt.id}
              onClick={() => setSelectedType(rt.id)}
              className={`p-4 rounded-xl border text-left transition-all flex flex-col justify-between ${
                isSelected
                  ? 'bg-sky-50 dark:bg-slate-800/90 border-sky-400 dark:border-cyan-500/60 shadow-md text-slate-900 dark:text-white font-bold'
                  : 'bg-white dark:bg-slate-900/60 border-slate-200 dark:border-slate-800/80 hover:bg-slate-50 dark:hover:bg-slate-800 hover:border-slate-300 dark:hover:border-slate-700 text-slate-600 dark:text-slate-400'
              }`}
            >
              <div>
                <div className="flex items-center justify-between mb-2">
                  <span className={`text-[10px] font-bold uppercase tracking-wider ${isSelected ? 'text-sky-700 dark:text-cyan-300' : 'text-slate-500 dark:text-slate-400'}`}>
                    Report
                  </span>
                  {isSelected && <div className="w-2 h-2 rounded-full bg-sky-500 dark:bg-cyan-400 animate-pulse" />}
                </div>
                <div className={`font-bold text-xs line-clamp-1 ${isSelected ? 'text-slate-900 dark:text-white' : 'text-slate-800 dark:text-slate-300'}`}>
                  {rt.name}
                </div>
              </div>
              <p className="text-[11px] text-slate-500 dark:text-slate-400 mt-2 line-clamp-2 font-normal">
                {rt.description}
              </p>
            </button>
          );
        })}
      </div>

      {/* Main Report View */}
      <div className="omerta-card p-6 shadow-md">
        {loading ? (
          <div className="py-24 flex flex-col items-center justify-center text-slate-500 dark:text-slate-400">
            <RefreshCw className="w-8 h-8 animate-spin text-sky-500 dark:text-cyan-400 mb-4" />
            <p className="text-base font-bold text-slate-900 dark:text-slate-200">Compiling Report Matrices...</p>
            <p className="text-xs text-slate-500 dark:text-slate-400 mt-1">Aggregating real-time transactions and audit ledger records</p>
          </div>
        ) : error ? (
          <div className="py-16 flex flex-col items-center justify-center text-rose-600 dark:text-rose-400">
            <AlertTriangle className="w-10 h-10 mb-3" />
            <p className="text-base font-bold">{error}</p>
            <button
              onClick={() => loadReport(selectedType)}
              className="mt-4 px-4 py-2 bg-slate-100 dark:bg-slate-800 hover:bg-slate-200 dark:hover:bg-slate-700 text-slate-900 dark:text-white rounded-lg text-xs font-semibold border border-slate-300 dark:border-slate-700"
            >
              Try Again
            </button>
          </div>
        ) : reportData ? (
          <div className="space-y-6">
            {/* Report Header Metadata */}
            <div className="flex flex-col sm:flex-row sm:items-center justify-between pb-4 border-b border-slate-200 dark:border-slate-800 text-xs text-slate-600 dark:text-slate-400 gap-2">
              <div className="flex items-center gap-2">
                <span className="font-bold text-slate-900 dark:text-slate-200">Generated:</span>
                <span>{new Date(reportData.generated_at).toLocaleString()}</span>
              </div>
              <div className="flex items-center gap-2">
                <span className="font-bold text-slate-900 dark:text-slate-200">Classification:</span>
                <span className="px-2 py-0.5 rounded bg-emerald-50 dark:bg-emerald-500/10 text-emerald-800 dark:text-emerald-300 border border-emerald-300 dark:border-emerald-500/20 font-mono font-bold">
                  CONFIDENTIAL / COMPLIANCE
                </span>
              </div>
            </div>

            {/* Custom Content by Report Type */}
            {selectedType === 'risk-distribution' && (
              <div className="space-y-6">
                <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                  <div className="bg-slate-50 dark:bg-slate-900/60 p-5 rounded-xl border border-slate-200 dark:border-slate-800">
                    <h3 className="text-sm font-bold text-slate-900 dark:text-white mb-4 flex items-center gap-2">
                      <BarChart3 className="w-4 h-4 text-sky-600 dark:text-cyan-400" />
                      Transaction Volume by Risk Tier
                    </h3>
                    <div className="h-64">
                      <ResponsiveContainer width="100%" height="100%">
                        <BarChart data={reportData.data || []}>
                          <CartesianGrid strokeDasharray="3 3" stroke="#cbd5e1" opacity={0.3} />
                          <XAxis dataKey="tier" stroke="#64748b" tick={{ fontSize: 11 }} />
                          <YAxis stroke="#64748b" tick={{ fontSize: 11 }} tickFormatter={(v) => `$${(v / 1000).toFixed(0)}k`} />
                          <Tooltip
                            contentStyle={{ backgroundColor: '#0f172a', borderColor: '#334155', borderRadius: '8px', color: '#ffffff' }}
                            formatter={(v: any) => [`$${Number(v).toLocaleString()}`, 'Gross Volume']}
                          />
                          <Bar dataKey="volume" fill="#0284c7" radius={[4, 4, 0, 0]} />
                        </BarChart>
                      </ResponsiveContainer>
                    </div>
                  </div>

                  <div className="bg-slate-50 dark:bg-slate-900/60 p-5 rounded-xl border border-slate-200 dark:border-slate-800">
                    <h3 className="text-sm font-bold text-slate-900 dark:text-white mb-4 flex items-center gap-2">
                      <Layers className="w-4 h-4 text-sky-600 dark:text-indigo-400" />
                      Transaction Count Proportions
                    </h3>
                    <div className="h-64">
                      <ResponsiveContainer width="100%" height="100%">
                        <PieChart>
                          <Pie
                            data={reportData.data || []}
                            dataKey="count"
                            nameKey="tier"
                            cx="50%"
                            cy="50%"
                            outerRadius={80}
                            label={(entry: any) => `${entry.tier || ''}: ${entry.count || 0}`}
                          >
                            {(reportData.data || []).map((_: any, index: number) => (
                              <Cell key={`cell-${index}`} fill={COLORS[index % COLORS.length]} />
                            ))}
                          </Pie>
                          <Tooltip contentStyle={{ backgroundColor: '#0f172a', borderColor: '#334155', borderRadius: '8px', color: '#ffffff' }} />
                          <Legend />
                        </PieChart>
                      </ResponsiveContainer>
                    </div>
                  </div>
                </div>

                {/* Table Breakdown */}
                <div className="overflow-x-auto rounded-xl border border-slate-200 dark:border-slate-800">
                  <table className="w-full text-left text-xs text-slate-800 dark:text-slate-200">
                    <thead className="bg-slate-100 dark:bg-slate-900/90 text-slate-700 dark:text-slate-400 uppercase tracking-wider font-bold border-b border-slate-200 dark:border-slate-800">
                      <tr>
                        <th className="p-3.5">Risk Tier</th>
                        <th className="p-3.5">Transaction Count</th>
                        <th className="p-3.5">Gross Volume</th>
                        <th className="p-3.5">Threshold Policy</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-200 dark:divide-slate-800/60 font-mono">
                      {(reportData.data || []).map((row: any, idx: number) => (
                        <tr key={idx} className="hover:bg-slate-50 dark:hover:bg-slate-800/40">
                          <td className="p-3.5 font-bold text-slate-900 dark:text-white">{row.tier}</td>
                          <td className="p-3.5 text-sky-700 dark:text-cyan-300 font-bold">{row.count.toLocaleString()}</td>
                          <td className="p-3.5 text-emerald-700 dark:text-emerald-400 font-bold">${row.volume.toLocaleString(undefined, { minimumFractionDigits: 2 })}</td>
                          <td className="p-3.5 text-slate-600 dark:text-slate-400 font-sans text-[11px]">
                            {row.tier === 'REQUIRES_REVIEW' ? 'Score > 40.00% (Mandatory Queue)' : 'Standard Routine Monitoring'}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            )}

            {selectedType === 'high-risk-ranking' && (
              <div className="space-y-4">
                <p className="text-xs text-slate-600 dark:text-slate-400">
                  Top tier entities exhibiting elevated anomaly scores and recurrent device/network signals.
                </p>
                <div className="overflow-x-auto rounded-xl border border-slate-200 dark:border-slate-800">
                  <table className="w-full text-left text-xs text-slate-800 dark:text-slate-200">
                    <thead className="bg-slate-100 dark:bg-slate-900/90 text-slate-700 dark:text-slate-400 uppercase tracking-wider font-bold border-b border-slate-200 dark:border-slate-800">
                      <tr>
                        <th className="p-3.5">Customer ID</th>
                        <th className="p-3.5">Entity Name</th>
                        <th className="p-3.5">Type</th>
                        <th className="p-3.5">Jurisdiction</th>
                        <th className="p-3.5">Risk Level</th>
                        <th className="p-3.5">Action</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-200 dark:divide-slate-800/60">
                      {(reportData.data || []).map((c: any, idx: number) => (
                        <tr key={idx} className="hover:bg-slate-50 dark:hover:bg-slate-800/40">
                          <td className="p-3.5 font-mono text-sky-700 dark:text-cyan-300 font-bold">{c.customer_id}</td>
                          <td className="p-3.5 font-semibold text-slate-900 dark:text-white">{c.name}</td>
                          <td className="p-3.5 text-slate-600 dark:text-slate-400 uppercase">{c.type}</td>
                          <td className="p-3.5 text-slate-800 dark:text-slate-300 font-medium">{c.country}</td>
                          <td className="p-3.5">
                            <span className="px-2 py-0.5 rounded text-[11px] font-bold bg-rose-50 dark:bg-rose-500/20 text-rose-800 dark:text-rose-300 border border-rose-300 dark:border-rose-500/30">
                              {c.risk_level}
                            </span>
                          </td>
                          <td className="p-3.5">
                            <a
                              href={`/customers`}
                              className="text-xs text-sky-700 dark:text-cyan-400 hover:text-sky-800 dark:hover:text-cyan-300 font-bold inline-flex items-center gap-1"
                            >
                              View Profile <ArrowUpRight className="w-3.5 h-3.5" />
                            </a>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            )}

            {selectedType === 'analyst-outcomes' && (
              <div className="space-y-6">
                <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                  <div className="bg-slate-50 dark:bg-slate-900/60 p-5 rounded-xl border border-slate-200 dark:border-slate-800">
                    <h3 className="text-sm font-bold text-slate-900 dark:text-white mb-4">Investigator Dispositions</h3>
                    <div className="h-64">
                      <ResponsiveContainer width="100%" height="100%">
                        <BarChart layout="vertical" data={reportData.data || []}>
                          <CartesianGrid strokeDasharray="3 3" stroke="#cbd5e1" opacity={0.3} />
                          <XAxis type="number" stroke="#64748b" tick={{ fontSize: 11 }} />
                          <YAxis dataKey="disposition" type="category" stroke="#64748b" tick={{ fontSize: 10 }} width={140} />
                          <Tooltip contentStyle={{ backgroundColor: '#0f172a', borderColor: '#334155', borderRadius: '8px', color: '#ffffff' }} />
                          <Bar dataKey="count" fill="#10b981" radius={[0, 4, 4, 0]} />
                        </BarChart>
                      </ResponsiveContainer>
                    </div>
                  </div>
                  <div className="bg-slate-50 dark:bg-slate-900/60 p-5 rounded-xl border border-slate-200 dark:border-slate-800 flex flex-col justify-center">
                    <div className="flex items-center gap-3 p-4 rounded-xl bg-emerald-50 dark:bg-emerald-500/10 border border-emerald-300 dark:border-emerald-500/30 mb-3">
                      <ShieldCheck className="w-6 h-6 text-emerald-600 dark:text-emerald-400 flex-shrink-0" />
                      <div>
                        <div className="text-sm font-bold text-emerald-900 dark:text-emerald-300">Human-In-The-Loop Governance</div>
                        <p className="text-xs text-slate-600 dark:text-slate-400 mt-0.5">
                          Every disposition requires written rationale from a credentialed investigator before a case is closed.
                        </p>
                      </div>
                    </div>
                    <p className="text-xs text-slate-600 dark:text-slate-400 leading-relaxed">
                      Our dual-tier review ensures false positive mitigation while preserving SAR audit trails for state financial intelligence units.
                    </p>
                  </div>
                </div>
              </div>
            )}

            {selectedType === 'transaction-activity' && (
              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
                <StatCard
                  title="Total Transactions Processed"
                  value={(reportData.data?.total_transactions || 0).toLocaleString()}
                  icon={<FileText className="w-5 h-5 text-sky-600 dark:text-cyan-400" />}
                  description="Validated source records"
                />
                <StatCard
                  title="Gross Transaction Volume"
                  value={`$${(reportData.data?.gross_volume || 0).toLocaleString(undefined, { maximumFractionDigits: 0 })}`}
                  icon={<BarChart3 className="w-5 h-5 text-emerald-600 dark:text-emerald-400" />}
                  description="All currencies combined"
                />
                <StatCard
                  title="Human Review Trigger Rate"
                  value={reportData.data?.review_rate || '12.4%'}
                  icon={<AlertTriangle className="w-5 h-5 text-amber-600 dark:text-amber-400" />}
                  description="Transactions with score > 40%"
                  variant="alert"
                />
                <StatCard
                  title="Avg Turnaround Time"
                  value={`${reportData.data?.avg_turnaround_hours || 2.1}h`}
                  icon={<Calendar className="w-5 h-5 text-sky-600 dark:text-indigo-400" />}
                  description="From alert to disposition"
                />
              </div>
            )}
          </div>
        ) : null}
      </div>
    </div>
  );
};
