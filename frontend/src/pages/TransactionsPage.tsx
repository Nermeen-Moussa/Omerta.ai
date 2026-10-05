import React, { useEffect, useState } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import {
  Search,
  Download,
  RefreshCw,
  ChevronLeft,
  ChevronRight,
  Smartphone,
  Globe,
} from 'lucide-react';
import { api } from '../api/client';
import type { TransactionItem } from '../types';
import { RiskBadge } from '../components/common/RiskBadge';
import { StatusBadge } from '../components/common/StatusBadge';

export const TransactionsPage: React.FC = () => {
  const [transactions, setTransactions] = useState<TransactionItem[]>([]);
  const [total, setTotal] = useState(0);
  const [totalPages, setTotalPages] = useState(1);
  const [loading, setLoading] = useState(true);

  const [searchParams] = useSearchParams();
  const navigate = useNavigate();

  // Filters state
  const [search, setSearch] = useState(searchParams.get('search') || '');
  const [currency, setCurrency] = useState('');
  const [transactionType, setTransactionType] = useState('');
  const [riskLevel, setRiskLevel] = useState('');
  const [reviewStatus, setReviewStatus] = useState('');
  const [page, setPage] = useState(1);

  const fetchTransactions = async () => {
    setLoading(true);
    try {
      const res = await api.getTransactions({
        search,
        currency,
        transaction_type: transactionType,
        risk_level: riskLevel,
        review_status: reviewStatus,
        page,
        page_size: 20,
      });
      setTransactions(res.items || []);
      setTotal(res.total || 0);
      setTotalPages(res.total_pages || 1);
    } catch (err) {
      console.error('Failed to fetch transactions', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchTransactions();
  }, [page, currency, transactionType, riskLevel, reviewStatus]);

  const handleSearchSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    setPage(1);
    fetchTransactions();
  };

  const handleExportCSV = () => {
    const q = new URLSearchParams();
    if (search) q.append('search', search);
    if (currency) q.append('currency', currency);
    if (riskLevel) q.append('risk_level', riskLevel);
    if (reviewStatus) q.append('review_status', reviewStatus);
    window.open(`/api/v1/transactions/export?${q.toString()}`, '_blank');
  };

  return (
    <div className="space-y-6 animate-in fade-in duration-200">
      {/* Page Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-slate-900 dark:text-white flex items-center gap-2">
            Transaction Ledger & Monitoring
          </h1>
          <p className="text-xs text-slate-500 dark:text-slate-400 mt-1">
            Search, filter, and inspect banking transactions across accounts with multi-signal risk scoring.
          </p>
        </div>

        <div className="flex items-center gap-2.5">
          <button
            onClick={handleExportCSV}
            className="flex items-center gap-2 px-3.5 py-2 rounded-lg bg-white dark:bg-slate-900 border border-slate-300 dark:border-slate-700 text-xs font-semibold text-slate-700 dark:text-slate-200 hover:bg-slate-50 dark:hover:bg-slate-800 transition-colors shadow-sm"
          >
            <Download className="h-3.5 w-3.5" />
            <span>Export CSV</span>
          </button>
          <button
            onClick={fetchTransactions}
            className="flex items-center gap-2 px-3.5 py-2 rounded-lg bg-white dark:bg-slate-900 border border-slate-300 dark:border-slate-700 text-xs font-semibold text-slate-700 dark:text-slate-200 hover:bg-slate-50 dark:hover:bg-slate-800 transition-colors shadow-sm"
          >
            <RefreshCw className={`h-3.5 w-3.5 ${loading ? 'animate-spin text-sky-500 dark:text-cyan-400' : ''}`} />
            <span>Refresh</span>
          </button>
        </div>
      </div>

      {/* Search & Filter Toolbar */}
      <div className="omerta-card p-4 space-y-3">
        <div className="flex flex-col sm:flex-row items-center gap-3">
          <form onSubmit={handleSearchSubmit} className="relative flex-1 w-full">
            <Search className="absolute left-3.5 top-2.5 h-4 w-4 text-slate-400 dark:text-slate-500" />
            <input
              type="text"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Search by Transaction ID, Account ID, or Customer name..."
              className="w-full pl-10 pr-4 py-2 bg-slate-50 dark:bg-slate-900/90 border border-slate-300 dark:border-slate-700 rounded-lg text-sm text-slate-900 dark:text-white placeholder-slate-400 dark:placeholder-slate-500 focus:outline-none focus:border-sky-500 dark:focus:border-cyan-400"
            />
          </form>

          <div className="flex flex-wrap items-center gap-2 w-full sm:w-auto">
            <select
              value={riskLevel}
              onChange={(e) => {
                setRiskLevel(e.target.value);
                setPage(1);
              }}
              className="px-3 py-2 bg-slate-50 dark:bg-slate-900 border border-slate-300 dark:border-slate-700 rounded-lg text-xs font-medium text-slate-700 dark:text-slate-200 focus:outline-none focus:border-sky-500 dark:focus:border-cyan-400"
            >
              <option value="">All Risk Levels</option>
              <option value="LOW">Low Risk</option>
              <option value="MODERATE">Moderate</option>
              <option value="REQUIRES_REVIEW">Requires Review</option>
              <option value="HIGH">High Risk</option>
              <option value="CRITICAL">Critical</option>
            </select>

            <select
              value={reviewStatus}
              onChange={(e) => {
                setReviewStatus(e.target.value);
                setPage(1);
              }}
              className="px-3 py-2 bg-slate-50 dark:bg-slate-900 border border-slate-300 dark:border-slate-700 rounded-lg text-xs font-medium text-slate-700 dark:text-slate-200 focus:outline-none focus:border-sky-500 dark:focus:border-cyan-400"
            >
              <option value="">All Review Statuses</option>
              <option value="REQUIRES_REVIEW">Requires Review (&gt;40%)</option>
              <option value="NOT_REQUIRED">Routine Monitoring</option>
              <option value="COMPLETED">Completed</option>
            </select>

            <select
              value={currency}
              onChange={(e) => {
                setCurrency(e.target.value);
                setPage(1);
              }}
              className="px-3 py-2 bg-slate-50 dark:bg-slate-900 border border-slate-300 dark:border-slate-700 rounded-lg text-xs font-medium text-slate-700 dark:text-slate-200 focus:outline-none focus:border-sky-500 dark:focus:border-cyan-400"
            >
              <option value="">All Currencies</option>
              <option value="EGP">EGP</option>
              <option value="USD">USD</option>
              <option value="EUR">EUR</option>
              <option value="GBP">GBP</option>
            </select>

            <select
              value={transactionType}
              onChange={(e) => {
                setTransactionType(e.target.value);
                setPage(1);
              }}
              className="px-3 py-2 bg-slate-50 dark:bg-slate-900 border border-slate-300 dark:border-slate-700 rounded-lg text-xs font-medium text-slate-700 dark:text-slate-200 focus:outline-none focus:border-sky-500 dark:focus:border-cyan-400"
            >
              <option value="">All Types</option>
              <option value="TRANSFER">TRANSFER</option>
              <option value="DEPOSIT">DEPOSIT</option>
              <option value="WITHDRAWAL">WITHDRAWAL</option>
              <option value="PAYMENT">PAYMENT</option>
              <option value="FX_CONVERSION">FX CONVERSION</option>
            </select>
          </div>
        </div>
      </div>

      {/* Transactions Data Table */}
      <div className="omerta-card overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs">
            <thead className="bg-slate-100 dark:bg-slate-900/90 text-slate-700 dark:text-slate-400 border-b border-slate-200 dark:border-slate-800 uppercase text-[10px] tracking-wider font-bold">
              <tr>
                <th className="py-3.5 px-4">Transaction ID</th>
                <th className="py-3.5 px-4">Timestamp</th>
                <th className="py-3.5 px-4">Source Account</th>
                <th className="py-3.5 px-4">Customer</th>
                <th className="py-3.5 px-4">Recipient</th>
                <th className="py-3.5 px-4">Amount</th>
                <th className="py-3.5 px-4">Type</th>
                <th className="py-3.5 px-4">Hardware / IP</th>
                <th className="py-3.5 px-4">Risk Score</th>
                <th className="py-3.5 px-4">Review Status</th>
                <th className="py-3.5 px-4 text-right">Action</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-200 dark:divide-slate-800/60 text-slate-800 dark:text-slate-300">
              {loading ? (
                <tr>
                  <td colSpan={11} className="py-12 text-center text-slate-500 dark:text-slate-400">
                    <RefreshCw className="h-6 w-6 animate-spin mx-auto mb-2 text-sky-500 dark:text-cyan-400" />
                    <span>Loading transactions ledger...</span>
                  </td>
                </tr>
              ) : transactions.length === 0 ? (
                <tr>
                  <td colSpan={11} className="py-12 text-center text-slate-500 dark:text-slate-400">
                    No transactions match the selected filter criteria.
                  </td>
                </tr>
              ) : (
                transactions.map((t) => (
                  <tr
                    key={t.id}
                    onClick={() => navigate(`/transactions/${t.external_id}`)}
                    className="hover:bg-slate-50 dark:hover:bg-slate-800/50 cursor-pointer transition-colors group"
                  >
                    <td className="py-3 px-4 font-mono font-bold text-sky-700 dark:text-cyan-300 group-hover:underline">
                      {t.external_id}
                    </td>
                    <td className="py-3 px-4 text-slate-600 dark:text-slate-400 whitespace-nowrap">
                      {new Date(t.timestamp).toLocaleDateString()}{' '}
                      <span className="text-[10px] text-slate-500">
                        {new Date(t.timestamp).toLocaleTimeString([], {
                          hour: '2-digit',
                          minute: '2-digit',
                        })}
                      </span>
                    </td>
                    <td className="py-3 px-4 font-mono font-medium text-slate-800 dark:text-slate-300">
                      {t.source_account}
                    </td>
                    <td className="py-3 px-4 font-semibold text-slate-900 dark:text-white truncate max-w-[140px]">
                      {t.customer_name}
                    </td>
                    <td className="py-3 px-4 font-mono text-slate-600 dark:text-slate-400">
                      {t.recipient_account}
                    </td>
                    <td className="py-3 px-4 font-mono font-bold text-slate-900 dark:text-white whitespace-nowrap">
                      {t.amount.toLocaleString(undefined, {
                        minimumFractionDigits: 2,
                        maximumFractionDigits: 2,
                      })}{' '}
                      <span className="text-[10px] font-semibold text-slate-500 dark:text-slate-400">
                        {t.currency}
                      </span>
                    </td>
                    <td className="py-3 px-4">
                      <span className="px-2 py-0.5 rounded bg-slate-100 dark:bg-slate-800 text-[10px] font-bold text-slate-800 dark:text-slate-300 border border-slate-300 dark:border-slate-700">
                        {t.transaction_type}
                      </span>
                    </td>
                    <td className="py-3 px-4 text-[11px] text-slate-600 dark:text-slate-400">
                      <div className="flex items-center gap-1.5">
                        <Smartphone className="h-3 w-3 text-slate-400" />
                        <span className="font-mono truncate max-w-[70px]">{t.device}</span>
                        <Globe className="h-3 w-3 text-slate-400 ml-1" />
                        <span>{t.ip_country}</span>
                      </div>
                    </td>
                    <td className="py-3 px-4">
                      <RiskBadge
                        level={t.risk_level}
                        score={t.risk_score}
                        size="sm"
                      />
                    </td>
                    <td className="py-3 px-4">
                      <StatusBadge status={t.review_status} />
                    </td>
                    <td className="py-3 px-4 text-right">
                      <button
                        onClick={(e) => {
                          e.stopPropagation();
                          navigate(`/transactions/${t.external_id}`);
                        }}
                        className="px-2.5 py-1 text-xs font-bold rounded bg-sky-50 dark:bg-sky-500/10 text-sky-700 dark:text-cyan-400 hover:bg-sky-100 dark:hover:bg-sky-500/20 border border-sky-300 dark:border-sky-500/30 transition-colors shadow-xs"
                      >
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
        <div className="flex items-center justify-between px-4 py-3 bg-slate-100 dark:bg-slate-900/90 border-t border-slate-200 dark:border-slate-800 text-xs text-slate-600 dark:text-slate-400">
          <div>
            Showing <span className="text-slate-900 dark:text-white font-bold">{transactions.length}</span> of{' '}
            <span className="text-slate-900 dark:text-white font-bold">{total.toLocaleString()}</span> records
          </div>

          <div className="flex items-center gap-2">
            <button
              disabled={page <= 1 || loading}
              onClick={() => setPage((p) => Math.max(1, p - 1))}
              className="p-1.5 rounded-lg border border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-800 text-slate-700 dark:text-slate-300 disabled:opacity-40 hover:bg-slate-50 dark:hover:bg-slate-700 shadow-xs"
            >
              <ChevronLeft className="h-4 w-4" />
            </button>
            <span>
              Page <strong className="text-slate-900 dark:text-white">{page}</strong> of{' '}
              <strong className="text-slate-900 dark:text-white">{totalPages}</strong>
            </span>
            <button
              disabled={page >= totalPages || loading}
              onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
              className="p-1.5 rounded-lg border border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-800 text-slate-700 dark:text-slate-300 disabled:opacity-40 hover:bg-slate-50 dark:hover:bg-slate-700 shadow-xs"
            >
              <ChevronRight className="h-4 w-4" />
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};
