import React, { useEffect, useState } from 'react';
import {
  Wallet,
  Search,
  RefreshCw,
  ChevronLeft,
  ChevronRight,
  ArrowRightLeft,
} from 'lucide-react';
import { api } from '../api/client';
import type { AccountItem } from '../types';
import { RiskBadge } from '../components/common/RiskBadge';
import { StatusBadge } from '../components/common/StatusBadge';
import { Modal } from '../components/common/Modal';

export const AccountsPage: React.FC = () => {
  const [accounts, setAccounts] = useState<AccountItem[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState('');
  const [currencyFilter, setCurrencyFilter] = useState('');
  const [typeFilter, setTypeFilter] = useState('');
  const [page, setPage] = useState(1);

  // Account detail modal state
  const [selectedAccount, setSelectedAccount] = useState<any | null>(null);

  const fetchAccounts = async () => {
    setLoading(true);
    try {
      const res = await api.getAccounts({
        search,
        currency: currencyFilter,
        account_type: typeFilter,
        page,
        page_size: 20,
      });
      setAccounts(res.items || []);
      setTotal(res.total || 0);
    } catch (err) {
      console.error('Failed to load accounts', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchAccounts();
  }, [page, currencyFilter, typeFilter]);

  const handleSearchSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    setPage(1);
    fetchAccounts();
  };

  const handleOpenDetail = async (a: AccountItem) => {
    try {
      const res = await api.getAccountDetail(a.external_id);
      setSelectedAccount(res);
    } catch (err) {
      console.error('Failed to load account detail', err);
    }
  };

  return (
    <div className="space-y-6 animate-in fade-in duration-200">
      {/* Page Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-slate-900 dark:text-white flex items-center gap-2">
            <Wallet className="h-6 w-6 text-sky-600 dark:text-cyan-400" />
            Bank Accounts & Balance Ledgers
          </h1>
          <p className="text-xs text-slate-500 dark:text-slate-400 mt-1">
            Explore multi-currency customer accounts, active ledger balances, and counterparties.
          </p>
        </div>

        <div className="flex items-center gap-2.5">
          <span className="px-3 py-1.5 rounded-lg bg-sky-50 dark:bg-slate-900 text-sky-800 dark:text-cyan-300 font-mono text-xs font-bold border border-sky-300 dark:border-slate-700 shadow-xs">
            {total} Bank Accounts
          </span>
          <button
            onClick={fetchAccounts}
            className="flex items-center gap-2 px-3.5 py-2 rounded-lg bg-white dark:bg-slate-900 border border-slate-300 dark:border-slate-700 text-xs font-semibold text-slate-700 dark:text-slate-200 hover:bg-slate-50 dark:hover:bg-slate-800 transition-colors shadow-sm"
          >
            <RefreshCw className={`h-3.5 w-3.5 ${loading ? 'animate-spin text-sky-500 dark:text-cyan-400' : ''}`} />
            <span>Refresh</span>
          </button>
        </div>
      </div>

      {/* Search Toolbar */}
      <div className="omerta-card p-4 flex flex-col sm:flex-row items-center gap-3">
        <form onSubmit={handleSearchSubmit} className="relative flex-1 w-full">
          <Search className="absolute left-3.5 top-2.5 h-4 w-4 text-slate-400 dark:text-slate-500" />
          <input
            type="text"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search by Account ID or Customer Name..."
            className="w-full pl-10 pr-4 py-2 bg-slate-50 dark:bg-slate-900 border border-slate-300 dark:border-slate-700 rounded-lg text-sm text-slate-900 dark:text-white placeholder-slate-400 dark:placeholder-slate-500 focus:outline-none focus:border-sky-500 dark:focus:border-cyan-400"
          />
        </form>

        <div className="flex items-center gap-2 w-full sm:w-auto">
          <select
            value={currencyFilter}
            onChange={(e) => {
              setCurrencyFilter(e.target.value);
              setPage(1);
            }}
            className="px-3 py-2 bg-slate-50 dark:bg-slate-900 border border-slate-300 dark:border-slate-700 rounded-lg text-xs font-medium text-slate-700 dark:text-slate-200 focus:outline-none focus:border-sky-500 dark:focus:border-cyan-400"
          >
            <option value="">All Currencies</option>
            <option value="EGP">EGP</option>
            <option value="USD">USD</option>
            <option value="EUR">EUR</option>
            <option value="GBP">GBP</option>
            <option value="SAR">SAR</option>
            <option value="AED">AED</option>
          </select>

          <select
            value={typeFilter}
            onChange={(e) => {
              setTypeFilter(e.target.value);
              setPage(1);
            }}
            className="px-3 py-2 bg-slate-50 dark:bg-slate-900 border border-slate-300 dark:border-slate-700 rounded-lg text-xs font-medium text-slate-700 dark:text-slate-200 focus:outline-none focus:border-sky-500 dark:focus:border-cyan-400"
          >
            <option value="">All Account Types</option>
            <option value="CHECKING">Checking</option>
            <option value="SAVINGS">Savings</option>
            <option value="BUSINESS">Business</option>
          </select>
        </div>
      </div>

      {/* Account Table */}
      <div className="omerta-card overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs">
            <thead className="bg-slate-100 dark:bg-slate-900/90 text-slate-700 dark:text-slate-400 border-b border-slate-200 dark:border-slate-800 uppercase text-[10px] tracking-wider font-bold">
              <tr>
                <th className="py-3.5 px-4">Account ID</th>
                <th className="py-3.5 px-4">Customer Name</th>
                <th className="py-3.5 px-4">Account Type</th>
                <th className="py-3.5 px-4">Currency</th>
                <th className="py-3.5 px-4">Current Balance</th>
                <th className="py-3.5 px-4">Country</th>
                <th className="py-3.5 px-4">Status</th>
                <th className="py-3.5 px-4">Risk Tier</th>
                <th className="py-3.5 px-4 text-right">Action</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-200 dark:divide-slate-800/60 text-slate-800 dark:text-slate-300">
              {loading ? (
                <tr>
                  <td colSpan={9} className="py-12 text-center text-slate-500 dark:text-slate-400">
                    <RefreshCw className="h-6 w-6 animate-spin mx-auto mb-2 text-sky-500 dark:text-cyan-400" />
                    <span>Loading bank accounts...</span>
                  </td>
                </tr>
              ) : accounts.length === 0 ? (
                <tr>
                  <td colSpan={9} className="py-12 text-center text-slate-500 dark:text-slate-400">
                    No accounts match the selected filters.
                  </td>
                </tr>
              ) : (
                accounts.map((a) => (
                  <tr
                    key={a.id}
                    onClick={() => handleOpenDetail(a)}
                    className="hover:bg-slate-50 dark:hover:bg-slate-800/50 cursor-pointer transition-colors group"
                  >
                    <td className="py-3 px-4 font-mono font-bold text-sky-700 dark:text-cyan-300 group-hover:underline">
                      {a.external_id}
                    </td>
                    <td className="py-3 px-4 font-bold text-slate-900 dark:text-white">
                      {a.customer_name}
                    </td>
                    <td className="py-3 px-4">
                      <span className="px-2 py-0.5 rounded bg-slate-100 dark:bg-slate-800 text-[10px] font-semibold text-slate-800 dark:text-slate-300 border border-slate-300 dark:border-slate-700">
                        {a.account_type}
                      </span>
                    </td>
                    <td className="py-3 px-4 font-mono font-bold text-sky-700 dark:text-cyan-300">
                      {a.currency}
                    </td>
                    <td className="py-3 px-4 font-mono font-bold text-slate-900 dark:text-white whitespace-nowrap">
                      {a.balance.toLocaleString(undefined, { minimumFractionDigits: 2 })}
                    </td>
                    <td className="py-3 px-4 font-bold text-slate-800 dark:text-slate-300">{a.country}</td>
                    <td className="py-3 px-4">
                      <StatusBadge status={a.status} />
                    </td>
                    <td className="py-3 px-4">
                      <RiskBadge level={a.risk_level || 'LOW'} size="sm" />
                    </td>
                    <td className="py-3 px-4 text-right">
                      <button
                        onClick={(e) => {
                          e.stopPropagation();
                          handleOpenDetail(a);
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
          <span>Showing <strong className="text-slate-900 dark:text-white">{accounts.length}</strong> of <strong className="text-slate-900 dark:text-white">{total}</strong> accounts</span>
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
              disabled={accounts.length < 20 || loading}
              onClick={() => setPage((p) => p + 1)}
              className="p-1.5 rounded-lg border border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-800 text-slate-700 dark:text-slate-300 disabled:opacity-40 hover:bg-slate-50 dark:hover:bg-slate-700 shadow-xs"
            >
              <ChevronRight className="h-4 w-4" />
            </button>
          </div>
        </div>
      </div>

      {/* Account Detail Modal */}
      <Modal
        isOpen={!!selectedAccount}
        onClose={() => setSelectedAccount(null)}
        title={`Account: ${selectedAccount?.account?.external_id}`}
        subtitle={`${selectedAccount?.account?.customer_name} • Balance: ${selectedAccount?.account?.balance.toLocaleString()} ${selectedAccount?.account?.currency}`}
        maxWidth="2xl"
      >
        {selectedAccount && (
          <div className="space-y-5 text-xs">
            {/* Counterparties */}
            <div>
              <h4 className="font-bold text-slate-700 dark:text-slate-300 uppercase tracking-wider text-[11px] mb-2 flex items-center gap-1.5">
                <ArrowRightLeft className="h-3.5 w-3.5 text-sky-600 dark:text-cyan-400" />
                <span>Frequent Counterparties & Beneficiaries ({selectedAccount.counterparties?.length || 0})</span>
              </h4>
              <div className="space-y-2">
                {(selectedAccount.counterparties || []).map((cp: any) => (
                  <div key={cp.account_external_id} className="p-3 rounded-lg bg-slate-50 dark:bg-slate-900 border border-slate-200 dark:border-slate-800 flex justify-between items-center">
                    <div>
                      <span className="font-mono font-bold text-slate-900 dark:text-white">{cp.account_external_id}</span>
                      <p className="text-slate-600 dark:text-slate-400 font-medium">{cp.customer_name}</p>
                    </div>
                    <div className="text-right">
                      <p className="font-mono font-bold text-slate-900 dark:text-white">{cp.total_volume.toLocaleString()} EGP</p>
                      <span className="text-[10px] text-slate-500 dark:text-slate-400 font-medium">{cp.total_transfers} transfer(s)</span>
                    </div>
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
