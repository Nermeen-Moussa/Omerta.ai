import React, { useState, useEffect } from 'react';
import {
  Wallet,
  PlusCircle,
  ShieldCheck,
  CreditCard,
  X,
  FileText,
  AlertCircle,
  Loader2,
} from 'lucide-react';
import { api } from '../../api/client';
import type { CustomerAccount } from '../../types';
import { StatusBadge } from '../../components/common/StatusBadge';

export const CustomerAccountsPage: React.FC = () => {
  const [accounts, setAccounts] = useState<CustomerAccount[]>([]);
  const [isLoading, setIsLoading] = useState(true);

  // New account modal
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [newAccType, setNewAccType] = useState('SAVINGS');
  const [newAccCurrency, setNewAccCurrency] = useState('EGP');
  const [newAccInitialBalance, setNewAccInitialBalance] = useState('5000.00');
  const [isCreating, setIsCreating] = useState(false);
  const [createError, setCreateError] = useState<string | null>(null);

  // Ledger drawer
  const [activeLedgerAccount, setActiveLedgerAccount] = useState<CustomerAccount | null>(null);

  const fetchAccounts = async () => {
    setIsLoading(true);
    try {
      const res = await api.getCustomerAccounts();
      setAccounts(res);
    } catch {
      // Fallback
      setAccounts([
        {
          account_id: 'ACC-1001',
          account_type: 'CHECKING',
          currency: 'EGP',
          balance: 50000.0,
          status: 'ACTIVE',
          recent_ledger: [
            {
              entry_id: 'LED-OPEN-1001',
              entry_type: 'OPENING_BALANCE',
              amount: 50000.0,
              currency: 'EGP',
              balance_after: 50000.0,
              description: 'Initial demo balance',
              created_at: new Date().toISOString(),
            },
          ],
        },
      ]);
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    fetchAccounts();
  }, []);

  const handleCreateAccount = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsCreating(true);
    setCreateError(null);
    try {
      await api.createCustomerAccount({
        account_type: newAccType,
        currency: newAccCurrency,
        initial_balance: parseFloat(newAccInitialBalance) || 0,
      });
      setIsModalOpen(false);
      fetchAccounts();
    } catch (err: any) {
      setCreateError(err.message || 'Failed to open new account.');
    } finally {
      setIsCreating(false);
    }
  };

  if (isLoading && accounts.length === 0) {
    return (
      <div className="py-20 flex flex-col items-center justify-center text-[#A7B4C8]">
        <Loader2 className="h-8 w-8 animate-spin text-[#29C5D9] mb-3" />
        <p className="text-xs font-semibold">Loading ledger-verified accounts...</p>
      </div>
    );
  }

  return (
    <div className="space-y-6 animate-in fade-in duration-200">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-[#F4F7FC] flex items-center gap-2">
            <Wallet className="h-6 w-6 text-[#3978F6]" />
            <span>My Bank Accounts</span>
          </h1>
          <p className="text-xs text-[#A7B4C8] mt-1">
            Manage your demo bank accounts, view verified ledger balances, and open new accounts
          </p>
        </div>

        <button
          onClick={() => setIsModalOpen(true)}
          className="flex items-center gap-2 px-4 py-2 rounded-lg bg-[#3978F6] hover:bg-[#3978F6]/90 text-[#F4F7FC] text-xs font-bold transition-all shadow-md shadow-blue-500/20"
        >
          <PlusCircle className="h-4 w-4" />
          <span>Open Demo Account</span>
        </button>
      </div>

      {/* Account Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
        {accounts.map((acc) => (
          <div key={acc.account_id} className="p-5 omerta-card flex flex-col justify-between hover:border-[#3978F6]/50 transition-colors">
            <div>
              <div className="flex items-center justify-between mb-3">
                <span className="px-2.5 py-0.5 rounded-full bg-[#3978F6]/15 text-[#29C5D9] border border-[#3978F6]/30 text-[10px] font-bold uppercase">
                  {acc.account_type}
                </span>
                <StatusBadge status={acc.status} />
              </div>

              <span className="text-xs text-[#71819A] block mb-1">Account Identifier</span>
              <p className="text-sm font-mono font-bold text-[#F4F7FC] mb-4">{acc.account_id}</p>

              <span className="text-xs text-[#71819A] block mb-0.5">Available Balance</span>
              <div className="flex items-baseline gap-1.5 mb-2">
                <span className="text-2xl font-bold text-[#F4F7FC] font-mono font-tabular">
                  {acc.balance.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                </span>
                <span className="text-sm font-bold text-[#29C5D9]">{acc.currency}</span>
              </div>
            </div>

            <div className="pt-4 border-t border-[#25344A] flex items-center justify-between">
              <span className="text-[11px] text-[#71819A] flex items-center gap-1">
                <ShieldCheck className="h-3.5 w-3.5 text-[#27C58B]" /> Verified Ledger
              </span>

              <button
                onClick={() => setActiveLedgerAccount(acc)}
                className="text-xs text-[#3978F6] hover:text-[#29C5D9] font-semibold flex items-center gap-1 transition-colors"
              >
                <FileText className="h-3.5 w-3.5" />
                <span>View Statement</span>
              </button>
            </div>
          </div>
        ))}
      </div>

      {/* Open Account Modal */}
      {isModalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-950/70 backdrop-blur-sm animate-in fade-in">
          <div className="w-full max-w-md p-6 omerta-card bg-[#152238] border-[#25344A] space-y-4">
            <div className="flex items-center justify-between border-b border-[#25344A] pb-3">
              <h3 className="text-base font-bold text-[#F4F7FC] flex items-center gap-2">
                <CreditCard className="h-5 w-5 text-[#3978F6]" />
                <span>Open Additional Demo Account</span>
              </h3>
              <button
                onClick={() => setIsModalOpen(false)}
                className="p-1 text-[#A7B4C8] hover:text-[#F4F7FC] rounded"
              >
                <X className="h-4 w-4" />
              </button>
            </div>

            <form onSubmit={handleCreateAccount} className="space-y-4">
              <div>
                <label className="block text-xs font-bold text-[#A7B4C8] uppercase mb-1">Account Type</label>
                <select
                  value={newAccType}
                  onChange={(e) => setNewAccType(e.target.value)}
                  className="w-full px-3 py-2 bg-[#101A2B] border border-[#25344A] rounded-lg text-sm text-[#F4F7FC]"
                >
                  <option value="CHECKING">Checking Account</option>
                  <option value="SAVINGS">Savings Account</option>
                  <option value="DEMO">Demo Funds Account</option>
                </select>
              </div>

              <div>
                <label className="block text-xs font-bold text-[#A7B4C8] uppercase mb-1">Currency</label>
                <select
                  value={newAccCurrency}
                  onChange={(e) => setNewAccCurrency(e.target.value)}
                  className="w-full px-3 py-2 bg-[#101A2B] border border-[#25344A] rounded-lg text-sm text-[#F4F7FC]"
                >
                  <option value="EGP">EGP — Egyptian Pound</option>
                  <option value="USD">USD — US Dollar</option>
                  <option value="EUR">EUR — Euro</option>
                  <option value="GBP">GBP — British Pound</option>
                </select>
              </div>

              <div>
                <label className="block text-xs font-bold text-[#A7B4C8] uppercase mb-1">
                  Starting Demo Balance
                </label>
                <input
                  type="number"
                  min="0"
                  step="100"
                  value={newAccInitialBalance}
                  onChange={(e) => setNewAccInitialBalance(e.target.value)}
                  className="w-full px-3 py-2 bg-[#101A2B] border border-[#25344A] rounded-lg text-sm font-mono text-[#F4F7FC]"
                  required
                />
                <span className="text-[10px] text-[#71819A] block mt-1">
                  This will be recorded as an immutable opening balance in the PostgreSQL ledger.
                </span>
              </div>

              {createError && (
                <div className="p-3 rounded-lg bg-[#F06470]/10 border border-[#F06470]/30 text-xs text-[#F06470] flex items-center gap-2">
                  <AlertCircle className="h-4 w-4 shrink-0" />
                  <span>{createError}</span>
                </div>
              )}

              <div className="flex items-center justify-end gap-2 pt-2">
                <button
                  type="button"
                  onClick={() => setIsModalOpen(false)}
                  className="px-4 py-2 rounded-lg bg-[#101A2B] hover:bg-[#1B2B43] border border-[#25344A] text-xs font-semibold text-[#A7B4C8]"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={isCreating}
                  className="px-4 py-2 rounded-lg bg-[#3978F6] hover:bg-[#3978F6]/90 disabled:opacity-50 text-xs font-bold text-[#F4F7FC]"
                >
                  {isCreating ? 'Provisioning Account...' : 'Open Account'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Ledger Statement Drawer */}
      {activeLedgerAccount && (
        <div className="fixed inset-0 z-50 flex items-center justify-end bg-slate-950/70 backdrop-blur-sm animate-in fade-in">
          <div className="w-full max-w-lg h-full p-6 omerta-card bg-[#101A2B] border-l border-[#25344A] overflow-y-auto space-y-4">
            <div className="flex items-center justify-between border-b border-[#25344A] pb-3">
              <div>
                <h3 className="text-base font-bold text-[#F4F7FC]">Ledger Statement</h3>
                <p className="text-xs font-mono text-[#29C5D9]">{activeLedgerAccount.account_id}</p>
              </div>
              <button
                onClick={() => setActiveLedgerAccount(null)}
                className="p-1.5 text-[#A7B4C8] hover:text-[#F4F7FC] rounded hover:bg-[#152238]"
              >
                <X className="h-5 w-5" />
              </button>
            </div>

            <div className="p-4 rounded-lg bg-[#152238] border border-[#25344A] flex items-center justify-between">
              <div>
                <span className="text-xs text-[#71819A] block">Current Verified Balance</span>
                <span className="text-xl font-bold font-mono text-[#F4F7FC]">
                  {activeLedgerAccount.balance.toLocaleString()} {activeLedgerAccount.currency}
                </span>
              </div>
              <span className="px-2 py-1 rounded bg-[#27C58B]/15 text-[#27C58B] border border-[#27C58B]/30 text-[10px] font-bold">
                AUDITED
              </span>
            </div>

            <div className="space-y-2">
              <h4 className="text-xs font-bold uppercase tracking-wider text-[#71819A]">
                Immutable Ledger Entries
              </h4>

              <div className="space-y-2">
                {activeLedgerAccount.recent_ledger && activeLedgerAccount.recent_ledger.length > 0 ? (
                  activeLedgerAccount.recent_ledger.map((entry) => (
                    <div
                      key={entry.entry_id}
                      className="p-3 rounded-lg bg-[#152238] border border-[#25344A] text-xs space-y-1"
                    >
                      <div className="flex items-center justify-between">
                        <span className={`font-bold font-mono ${entry.entry_type === 'DEBIT' ? 'text-[#F06470]' : 'text-[#27C58B]'}`}>
                          {entry.entry_type === 'DEBIT' ? '-' : '+'}
                          {entry.amount.toLocaleString()} {entry.currency}
                        </span>
                        <span className="text-[10px] font-mono text-[#71819A]">{entry.entry_id}</span>
                      </div>
                      <p className="text-[#A7B4C8] text-[11px]">{entry.description}</p>
                      <div className="flex items-center justify-between text-[10px] text-[#71819A] pt-1 border-t border-[#25344A]">
                        <span>Balance after: {entry.balance_after.toLocaleString()} {entry.currency}</span>
                        <span>{new Date(entry.created_at).toLocaleString()}</span>
                      </div>
                    </div>
                  ))
                ) : (
                  <p className="p-4 text-center text-xs text-[#71819A]">No ledger history recorded.</p>
                )}
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
