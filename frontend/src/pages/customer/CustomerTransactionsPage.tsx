import React, { useState, useEffect } from 'react';
import {
  ArrowLeftRight,
  ArrowUpRight,
  ArrowDownLeft,
  Search,
  FileText,
  X,
} from 'lucide-react';
import { api } from '../../api/client';
import type { CustomerTransaction } from '../../types';
import { StatusBadge } from '../../components/common/StatusBadge';

export const CustomerTransactionsPage: React.FC = () => {
  const [transactions, setTransactions] = useState<CustomerTransaction[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [pageSize] = useState(15);
  const [search, setSearch] = useState('');
  const [direction, setDirection] = useState('ALL');
  const [status, setStatus] = useState('ALL');
  const [isLoading, setIsLoading] = useState(true);

  // Receipt Modal
  const [selectedTxn, setSelectedTxn] = useState<CustomerTransaction | null>(null);

  const fetchTransactions = async () => {
    setIsLoading(true);
    try {
      const res = await api.getCustomerTransactions({
        search: search.trim() || undefined,
        direction: direction !== 'ALL' ? direction : undefined,
        status: status !== 'ALL' ? status : undefined,
        page,
        page_size: pageSize,
      });
      setTransactions(res.items || []);
      setTotal(res.total || 0);
    } catch {
      setTransactions([]);
      setTotal(0);
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    fetchTransactions();
  }, [page, direction, status]);

  const handleSearchSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    setPage(1);
    fetchTransactions();
  };

  return (
    <div className="space-y-6 animate-in fade-in duration-200">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold tracking-tight text-[#F4F7FC] flex items-center gap-2">
          <ArrowLeftRight className="h-6 w-6 text-[#3978F6]" />
          <span>My Transactions</span>
        </h1>
        <p className="text-xs text-[#A7B4C8] mt-1">
          Historical record of all incoming and outgoing transfers scoped to your accounts
        </p>
      </div>

      {/* Filter Bar */}
      <div className="p-4 omerta-card space-y-3">
        <form onSubmit={handleSearchSubmit} className="flex flex-col sm:flex-row gap-3">
          <div className="relative flex-1">
            <input
              type="text"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Search reference, counterparty..."
              className="w-full pl-9 pr-4 py-2 bg-[#101A2B] border border-[#25344A] rounded-lg text-xs text-[#F4F7FC] placeholder-[#71819A] focus:outline-none focus:border-[#3978F6]"
            />
            <Search className="absolute left-3 top-2.5 h-4 w-4 text-[#71819A]" />
          </div>

          <div className="flex items-center gap-2">
            <select
              value={direction}
              onChange={(e) => {
                setDirection(e.target.value);
                setPage(1);
              }}
              className="px-3 py-2 bg-[#101A2B] border border-[#25344A] rounded-lg text-xs text-[#F4F7FC] focus:outline-none focus:border-[#3978F6]"
            >
              <option value="ALL">All Directions</option>
              <option value="INCOMING">Incoming Transfers</option>
              <option value="OUTGOING">Outgoing Transfers</option>
            </select>

            <select
              value={status}
              onChange={(e) => {
                setStatus(e.target.value);
                setPage(1);
              }}
              className="px-3 py-2 bg-[#101A2B] border border-[#25344A] rounded-lg text-xs text-[#F4F7FC] focus:outline-none focus:border-[#3978F6]"
            >
              <option value="ALL">All Statuses</option>
              <option value="COMPLETED">Completed</option>
              <option value="PENDING">Pending</option>
              <option value="REJECTED">Rejected</option>
            </select>

            <button
              type="submit"
              className="px-4 py-2 rounded-lg bg-[#3978F6] hover:bg-[#3978F6]/90 text-xs font-bold text-[#F4F7FC]"
            >
              Filter
            </button>
          </div>
        </form>
      </div>

      {/* Table */}
      <div className="omerta-card overflow-hidden">
        <div className="overflow-x-auto">
          <table className="text-left text-xs">
            <thead className="bg-[#101A2B] text-[#A7B4C8] uppercase tracking-wider font-bold">
              <tr>
                <th className="p-3.5">Direction</th>
                <th className="p-3.5">Reference</th>
                <th className="p-3.5">Counterparty</th>
                <th className="p-3.5">Amount</th>
                <th className="p-3.5">Status</th>
                <th className="p-3.5">Timestamp</th>
                <th className="p-3.5 text-right">Receipt</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-[#25344A]">
              {transactions.length > 0 ? (
                transactions.map((t) => (
                  <tr key={t.transaction_id} className="hover:bg-[#1B2B43]/50 transition-colors">
                    <td className="p-3.5">
                      {t.direction === 'INCOMING' ? (
                        <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full bg-[#27C58B]/15 text-[#27C58B] font-bold text-[10px] border border-[#27C58B]/30">
                          <ArrowDownLeft className="h-3 w-3" /> Incoming
                        </span>
                      ) : (
                        <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full bg-[#3978F6]/15 text-[#29C5D9] font-bold text-[10px] border border-[#3978F6]/30">
                          <ArrowUpRight className="h-3 w-3" /> Outgoing
                        </span>
                      )}
                    </td>
                    <td className="p-3.5 font-mono text-[#A7B4C8] font-bold">{t.transaction_id}</td>
                    <td className="p-3.5 font-semibold text-[#F4F7FC]">{t.counterparty}</td>
                    <td className="p-3.5 font-mono font-bold font-tabular text-[#F4F7FC]">
                      {t.direction === 'INCOMING' ? '+' : '-'}
                      {t.amount.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })} {t.currency}
                    </td>
                    <td className="p-3.5">
                      <StatusBadge status={t.status} />
                    </td>
                    <td className="p-3.5 text-[#71819A] whitespace-nowrap">
                      {new Date(t.timestamp).toLocaleDateString()} {new Date(t.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                    </td>
                    <td className="p-3.5 text-right">
                      <button
                        onClick={() => setSelectedTxn(t)}
                        className="p-1.5 text-[#3978F6] hover:text-[#29C5D9] hover:bg-[#101A2B] rounded transition-colors"
                        title="View Customer Receipt"
                      >
                        <FileText className="h-4 w-4" />
                      </button>
                    </td>
                  </tr>
                ))
              ) : (
                <tr>
                  <td colSpan={7} className="p-8 text-center text-[#71819A]">
                    {isLoading ? 'Loading transaction history...' : 'No transactions matching your criteria.'}
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>

        {/* Pagination */}
        {total > pageSize && (
          <div className="p-3 border-t border-[#25344A] flex items-center justify-between text-xs text-[#71819A]">
            <span>Showing {transactions.length} of {total} entries</span>
            <div className="flex gap-2">
              <button
                disabled={page <= 1}
                onClick={() => setPage(page - 1)}
                className="px-3 py-1 rounded bg-[#101A2B] border border-[#25344A] text-[#F4F7FC] disabled:opacity-50"
              >
                Previous
              </button>
              <button
                disabled={page * pageSize >= total}
                onClick={() => setPage(page + 1)}
                className="px-3 py-1 rounded bg-[#101A2B] border border-[#25344A] text-[#F4F7FC] disabled:opacity-50"
              >
                Next
              </button>
            </div>
          </div>
        )}
      </div>

      {/* Customer Receipt Modal */}
      {selectedTxn && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-950/70 backdrop-blur-sm animate-in fade-in">
          <div className="w-full max-w-md p-6 omerta-card bg-[#152238] border-[#25344A] space-y-4">
            <div className="flex items-center justify-between border-b border-[#25344A] pb-3">
              <h3 className="text-base font-bold text-[#F4F7FC] flex items-center gap-2">
                <FileText className="h-5 w-5 text-[#3978F6]" />
                <span>Transfer Receipt</span>
              </h3>
              <button
                onClick={() => setSelectedTxn(null)}
                className="p-1 text-[#A7B4C8] hover:text-[#F4F7FC] rounded"
              >
                <X className="h-4 w-4" />
              </button>
            </div>

            <div className="p-4 rounded-lg bg-[#101A2B] border border-[#25344A] space-y-3 text-xs">
              <div className="flex justify-between">
                <span className="text-[#71819A]">Transaction Ref</span>
                <span className="font-mono font-bold text-[#F4F7FC]">{selectedTxn.transaction_id}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-[#71819A]">Direction</span>
                <span className="font-bold text-[#F4F7FC]">{selectedTxn.direction}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-[#71819A]">Counterparty</span>
                <span className="font-semibold text-[#F4F7FC]">{selectedTxn.counterparty}</span>
              </div>
              <div className="flex justify-between border-t border-[#25344A] pt-2">
                <span className="text-[#71819A]">Amount</span>
                <span className="font-mono font-bold text-sm text-[#27C58B]">
                  {selectedTxn.amount.toLocaleString()} {selectedTxn.currency}
                </span>
              </div>
              <div className="flex justify-between">
                <span className="text-[#71819A]">Status</span>
                <StatusBadge status={selectedTxn.status} />
              </div>
              <div className="flex justify-between">
                <span className="text-[#71819A]">Date &amp; Time</span>
                <span className="text-[#A7B4C8]">{new Date(selectedTxn.timestamp).toLocaleString()}</span>
              </div>
            </div>

            <p className="text-[10px] text-[#71819A] text-center">
              Simulated demo transfer for testing and compliance demonstration.
            </p>

            <button
              onClick={() => setSelectedTxn(null)}
              className="w-full py-2.5 rounded-lg bg-[#3978F6] hover:bg-[#3978F6]/90 text-xs font-bold text-[#F4F7FC]"
            >
              Close Receipt
            </button>
          </div>
        </div>
      )}
    </div>
  );
};
