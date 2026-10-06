import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Wallet,
  Send,
  ArrowUpRight,
  ArrowDownLeft,
  Eye,
  EyeOff,
  Copy,
  Check,
  ShieldCheck,
  TrendingUp,
  CreditCard,
  Clock,
  ChevronRight,
  AlertCircle,
  AlertTriangle,
  Loader2,
  LifeBuoy,
  KeyRound,
  Lock,
  ArrowRight,
} from 'lucide-react';
import { useAuth } from '../../context/AuthContext';
import { api } from '../../api/client';
import { StatusBadge } from '../../components/common/StatusBadge';
import { Modal } from '../../components/common/Modal';

export const CustomerDashboardPage: React.FC = () => {
  const { user, customer } = useAuth();
  const navigate = useNavigate();

  const [data, setData] = useState<any>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [showBalance, setShowBalance] = useState(true);
  const [copied, setCopied] = useState(false);

  // Transfer Blocked Intercept Modal State
  const [showTransferBlockedModal, setShowTransferBlockedModal] = useState(false);

  // Recovery & Change Transfer Password Modal State
  const [showPasswordModal, setShowPasswordModal] = useState(false);
  const [newTransferPassword, setNewTransferPassword] = useState('');
  const [confirmTransferPassword, setConfirmTransferPassword] = useState('');
  const [currentTransferPassword, setCurrentTransferPassword] = useState('');
  const [showPasswordText, setShowPasswordText] = useState(false);
  const [passwordModalLoading, setPasswordModalLoading] = useState(false);
  const [passwordModalError, setPasswordModalError] = useState<string | null>(null);
  const [passwordModalSuccess, setPasswordModalSuccess] = useState(false);

  const fetchDashboard = async () => {
    setIsLoading(true);
    try {
      const res = await api.getCustomerDashboard();
      setData(res);
      // Auto open modal immediately on login / dashboard load if transfer password change is strictly required after compliance restore
      if (res?.customer?.require_transfer_password_change) {
        setShowPasswordModal(true);
      }
    } catch {
      // Fallback state if server is offline
      setData({
        customer: {
          name: customer?.name || user?.full_name || 'Customer',
          omerta_user_number: customer?.omerta_user_number || 'OMR-1092-4821',
          preferred_currency: 'EGP',
          status: 'ACTIVE',
          transfer_status: customer?.transfer_status || 'ACTIVE',
          identity_status: customer?.identity_status || 'VERIFIED',
          require_transfer_password_change: customer?.require_transfer_password_change || false,
        },
        accounts: [
          { account_id: 'ACC-1001', account_type: 'CHECKING', currency: 'EGP', balance: 50000.0, status: 'ACTIVE' },
        ],
        balances: { EGP: 50000.0 },
        activity: { incoming_volume: 12500.0, outgoing_volume: 1500.0, incoming_count: 3, outgoing_count: 1, total_transactions: 4 },
        recent_transactions: [],
      });
      if (customer?.require_transfer_password_change) {
        setShowPasswordModal(true);
      }
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    fetchDashboard();
  }, []);

  const handleCopyUserNumber = () => {
    const num = data?.customer?.omerta_user_number || customer?.omerta_user_number;
    if (num) {
      navigator.clipboard.writeText(num);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    }
  };

  const handleChangeTransferPassword = async (e: React.FormEvent) => {
    e.preventDefault();
    setPasswordModalError(null);

    if (!newTransferPassword) {
      setPasswordModalError('Please enter a new transfer password.');
      return;
    }
    if (newTransferPassword.length < 8) {
      setPasswordModalError('Transfer password must be at least 8 characters long.');
      return;
    }
    if (newTransferPassword !== confirmTransferPassword) {
      setPasswordModalError('New transfer password and confirmation do not match.');
      return;
    }

    setPasswordModalLoading(true);
    try {
      await api.changeTransferPassword({
        new_transfer_password: newTransferPassword,
        confirm_transfer_password: confirmTransferPassword,
        current_transfer_password: currentTransferPassword.trim() || undefined,
      });

      setPasswordModalSuccess(true);
      setTimeout(() => {
        setShowPasswordModal(false);
        setPasswordModalSuccess(false);
        setNewTransferPassword('');
        setConfirmTransferPassword('');
        setCurrentTransferPassword('');
        fetchDashboard();
      }, 1800);
    } catch (err: any) {
      setPasswordModalError(err.message || 'Failed to update transfer password. Please try again.');
    } finally {
      setPasswordModalLoading(false);
    }
  };

  const primaryAccount = data?.accounts?.[0] || { balance: 0, currency: 'EGP', account_id: 'ACC-DEMO' };

  const isTransferBlocked = data?.customer?.transfer_status === 'BLOCKED';
  const isPasswordChangeRequired = Boolean(data?.customer?.require_transfer_password_change);

  const handleTransferButtonClick = () => {
    if (isTransferBlocked) {
      setShowTransferBlockedModal(true);
      return;
    }
    if (isPasswordChangeRequired) {
      setShowPasswordModal(true);
      return;
    }
    navigate('/customer/transfer');
  };

  if (isLoading && !data) {
    return (
      <div className="py-20 flex flex-col items-center justify-center text-[#A7B4C8]">
        <Loader2 className="h-8 w-8 animate-spin text-[#29C5D9] mb-3" />
        <p className="text-xs font-semibold">Loading verified customer portfolio...</p>
      </div>
    );
  }


  return (
    <div className="space-y-6 animate-in fade-in duration-200">
      {/* Welcome & Status Banner */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 p-6 rounded-xl bg-gradient-to-r from-[#101A2B] via-[#152238] to-[#101A2B] border border-[#25344A]">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <h1 className="text-2xl font-bold tracking-tight text-[#F4F7FC]">
              Welcome back, {data?.customer?.name || user?.full_name || 'Customer'}
            </h1>
            <span className="px-2 py-0.5 rounded-full bg-[#27C58B]/15 text-[#27C58B] border border-[#27C58B]/30 text-[10px] font-bold uppercase">
              Verified Demo
            </span>
            {isTransferBlocked ? (
              <span className="px-2.5 py-0.5 rounded-full bg-[#F06470]/15 text-[#F06470] border border-[#F06470]/40 text-[10px] font-bold uppercase flex items-center gap-1">
                <AlertCircle className="w-3 h-3" />
                Transfer Blocked
              </span>
            ) : (
              <span className="px-2.5 py-0.5 rounded-full bg-[#27C58B]/15 text-[#27C58B] border border-[#27C58B]/30 text-[10px] font-bold uppercase flex items-center gap-1">
                <ShieldCheck className="w-3 h-3" />
                Transfer Active
              </span>
            )}
          </div>
          <p className="text-xs text-[#A7B4C8]">
            Simulated digital banking overview, support desk &amp; peer-to-peer transfers
          </p>
        </div>

        {/* Shareable Omerta User Number */}
        <div className="flex items-center gap-3 p-3 rounded-lg bg-[#080D19]/80 border border-[#25344A]">
          <div className="flex flex-col">
            <span className="text-[10px] uppercase font-bold text-[#71819A]">Your Omerta User #</span>
            <span className="font-mono text-sm font-bold text-[#29C5D9]">
              {data?.customer?.omerta_user_number || customer?.omerta_user_number || 'OMR-1092-4821'}
            </span>
          </div>
          <button
            onClick={handleCopyUserNumber}
            className="flex items-center gap-1 px-2.5 py-1.5 rounded-md bg-[#152238] hover:bg-[#1B2B43] border border-[#25344A] text-xs text-[#F4F7FC] font-medium transition-colors"
            title="Share this unique number with other registered users to receive funds"
          >
            {copied ? (
              <>
                <Check className="h-3.5 w-3.5 text-[#27C58B]" />
                <span className="text-[#27C58B]">Copied</span>
              </>
            ) : (
              <>
                <Copy className="h-3.5 w-3.5 text-[#3978F6]" />
                <span>Copy</span>
              </>
            )}
          </button>
        </div>
      </div>

      {/* SECURITY HOLD BANNER (If Transfer Blocked) */}
      {isTransferBlocked && (
        <div className="p-5 rounded-2xl bg-[#F06470]/10 border border-[#F06470]/40 flex flex-col sm:flex-row sm:items-center justify-between gap-4 shadow-lg shadow-rose-950/20">
          <div className="flex items-start gap-3">
            <AlertTriangle className="h-6 w-6 text-[#F06470] shrink-0 mt-0.5" />
            <div className="space-y-1">
              <h3 className="text-sm font-bold text-[#F4F7FC]">
                Security Hold: Money Transfers Restricted
              </h3>
              <p className="text-xs text-[#F4F7FC]/80 leading-relaxed max-w-2xl">
                Your transfer password was entered incorrectly 3 consecutive times. Your session and dashboard access remain active, but money movement is locked. Please open a support ticket to verify your National ID and restore transfer privileges.
              </p>
            </div>
          </div>
          <button
            type="button"
            onClick={() => navigate('/customer/support?reason=TRANSFER_BLOCKED')}
            className="shrink-0 px-4 py-2.5 rounded-xl bg-[#F06470] hover:bg-[#F06470]/90 text-[#F4F7FC] text-xs font-bold transition-all shadow-md flex items-center gap-2 cursor-pointer"
          >
            <LifeBuoy className="h-4 w-4" />
            <span>Open Support Ticket</span>
            <ArrowRight className="h-3.5 w-3.5" />
          </button>
        </div>
      )}

      {/* ACTION REQUIRED: RESTORE PASSWORD CHANGE BANNER */}
      {isPasswordChangeRequired && (
        <div className="p-5 rounded-2xl bg-[#29C5D9]/10 border border-[#29C5D9]/40 flex flex-col sm:flex-row sm:items-center justify-between gap-4 shadow-lg shadow-cyan-950/20">
          <div className="flex items-start gap-3">
            <KeyRound className="h-6 w-6 text-[#29C5D9] shrink-0 mt-0.5" />
            <div className="space-y-1">
              <h3 className="text-sm font-bold text-[#F4F7FC]">
                Action Required: Set New Transfer Password
              </h3>
              <p className="text-xs text-[#F4F7FC]/80 leading-relaxed max-w-2xl">
                Compliance staff has verified your identity and restored your transfer access! To complete account reactivation, please set a new transfer password now (without needing your old forgotten password).
              </p>
            </div>
          </div>
          <button
            type="button"
            onClick={() => {
              setPasswordModalError(null);
              setShowPasswordModal(true);
            }}
            className="shrink-0 px-4 py-2.5 rounded-xl bg-gradient-to-r from-[#3978F6] to-[#29C5D9] hover:opacity-90 text-slate-950 text-xs font-black transition-all shadow-md flex items-center gap-2 cursor-pointer"
          >
            <Lock className="h-4 w-4" />
            <span>Set New Transfer Password</span>
            <ArrowRight className="h-3.5 w-3.5" />
          </button>
        </div>
      )}

      {/* Primary Balance Card & Quick Action Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Main Available Balance Card */}
        <div className="lg:col-span-2 p-6 omerta-card-glow relative overflow-hidden flex flex-col justify-between min-h-[220px]">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <div className="p-2 rounded-lg bg-[#3978F6]/20 text-[#29C5D9] border border-[#3978F6]/30">
                <Wallet className="h-5 w-5" />
              </div>
              <div>
                <span className="text-xs font-semibold text-[#A7B4C8]">Primary Checking Account</span>
                <p className="text-[11px] font-mono text-[#71819A]">{primaryAccount.account_id}</p>
              </div>
            </div>

            <button
              onClick={() => setShowBalance(!showBalance)}
              className="p-1.5 text-[#A7B4C8] hover:text-[#F4F7FC] rounded hover:bg-[#1B2B43] transition-colors"
              title={showBalance ? 'Hide Balance' : 'Show Balance'}
            >
              {showBalance ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
            </button>
          </div>

          {/* Amount Display */}
          <div className="my-4">
            <span className="text-xs font-medium text-[#71819A] block mb-1">Available Demo Balance</span>
            <div className="flex items-baseline gap-2">
              {showBalance ? (
                <>
                  <span className="text-3xl sm:text-4xl font-black tracking-tight text-[#F4F7FC] font-tabular">
                    {primaryAccount.balance.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                  </span>
                  <span className="text-lg font-bold text-[#29C5D9]">{primaryAccount.currency}</span>
                </>
              ) : (
                <span className="text-3xl font-black text-[#71819A] tracking-widest">••••••••••</span>
              )}
            </div>
            <p className="text-[11px] text-[#71819A] mt-1 flex items-center gap-1">
              <ShieldCheck className="h-3.5 w-3.5 text-[#27C58B]" />
              <span>Protected with ledger double-entry audit trail</span>
            </p>
          </div>

          {/* Action Row */}
          <div className="flex flex-wrap items-center gap-3 pt-4 border-t border-[#25344A]">
            <button
              onClick={handleTransferButtonClick}
              className={`flex items-center gap-2 px-4 py-2 rounded-lg text-xs font-bold transition-all shadow-md cursor-pointer ${
                isTransferBlocked
                  ? 'bg-[#F06470]/20 text-[#F06470] border border-[#F06470]/40 hover:bg-[#F06470]/30'
                  : 'bg-[#3978F6] hover:bg-[#3978F6]/90 text-[#F4F7FC] shadow-blue-500/20'
              }`}
            >
              <Send className="h-3.5 w-3.5" />
              <span>{isTransferBlocked ? 'Transfers Blocked (Click for Info)' : 'Send Money'}</span>
            </button>

            <button
              onClick={() => navigate('/customer/accounts')}
              className="flex items-center gap-2 px-4 py-2 rounded-lg bg-[#152238] hover:bg-[#1B2B43] border border-[#25344A] text-[#F4F7FC] text-xs font-semibold transition-colors"
            >
              <CreditCard className="h-3.5 w-3.5 text-[#29C5D9]" />
              <span>View All Accounts</span>
            </button>

            <button
              onClick={() => navigate('/customer/support')}
              className="flex items-center gap-2 px-4 py-2 rounded-lg bg-[#152238] hover:bg-[#1B2B43] border border-[#25344A] text-[#29C5D9] text-xs font-semibold transition-colors"
            >
              <LifeBuoy className="h-3.5 w-3.5" />
              <span>Support &amp; Chat</span>
            </button>

            <button
              onClick={() => navigate('/customer/transactions')}
              className="flex items-center gap-2 px-4 py-2 rounded-lg bg-[#152238] hover:bg-[#1B2B43] border border-[#25344A] text-[#F4F7FC] text-xs font-semibold transition-colors ml-auto"
            >
              <Clock className="h-3.5 w-3.5 text-[#A7B4C8]" />
              <span>History</span>
            </button>
          </div>
        </div>

        {/* Activity Summary Card */}
        <div className="p-6 omerta-card flex flex-col justify-between">
          <div>
            <h3 className="text-sm font-bold text-[#F4F7FC] mb-4 flex items-center gap-2">
              <TrendingUp className="h-4 w-4 text-[#3978F6]" />
              <span>Demo Activity Overview</span>
            </h3>

            <div className="space-y-4">
              <div className="flex items-center justify-between p-3 rounded-lg bg-[#101A2B] border border-[#25344A]">
                <div className="flex items-center gap-2.5">
                  <div className="p-1.5 rounded bg-[#27C58B]/20 text-[#27C58B]">
                    <ArrowDownLeft className="h-4 w-4" />
                  </div>
                  <div>
                    <span className="text-xs font-semibold text-[#F4F7FC] block">Total Incoming</span>
                    <span className="text-[10px] text-[#71819A]">{data?.activity?.incoming_count || 0} transfer(s)</span>
                  </div>
                </div>
                <span className="text-sm font-bold text-[#27C58B] font-tabular">
                  +{(data?.activity?.incoming_volume || 0).toLocaleString()} {primaryAccount.currency}
                </span>
              </div>

              <div className="flex items-center justify-between p-3 rounded-lg bg-[#101A2B] border border-[#25344A]">
                <div className="flex items-center gap-2.5">
                  <div className="p-1.5 rounded bg-[#3978F6]/20 text-[#29C5D9]">
                    <ArrowUpRight className="h-4 w-4" />
                  </div>
                  <div>
                    <span className="text-xs font-semibold text-[#F4F7FC] block">Total Outgoing</span>
                    <span className="text-[10px] text-[#71819A]">{data?.activity?.outgoing_count || 0} transfer(s)</span>
                  </div>
                </div>
                <span className="text-sm font-bold text-[#F4F7FC] font-tabular">
                  -{(data?.activity?.outgoing_volume || 0).toLocaleString()} {primaryAccount.currency}
                </span>
              </div>
            </div>
          </div>

          <div className="mt-4 pt-3 border-t border-[#25344A] flex items-center justify-between text-xs text-[#71819A]">
            <span>Total Transfers</span>
            <span className="font-bold text-[#F4F7FC]">{data?.activity?.total_transactions || 0}</span>
          </div>
        </div>
      </div>

      {/* Recent Customer Transactions */}
      <div className="omerta-card overflow-hidden">
        <div className="p-4 border-b border-[#25344A] flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Clock className="h-4 w-4 text-[#29C5D9]" />
            <h2 className="text-sm font-bold text-[#F4F7FC]">Recent Transactions</h2>
          </div>

          <button
            onClick={() => navigate('/customer/transactions')}
            className="text-xs text-[#3978F6] hover:text-[#29C5D9] font-semibold flex items-center gap-1 transition-colors"
          >
            <span>View Full Ledger</span>
            <ChevronRight className="h-3.5 w-3.5" />
          </button>
        </div>

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
              </tr>
            </thead>
            <tbody className="divide-y divide-[#25344A]">
              {data?.recent_transactions?.length > 0 ? (
                data.recent_transactions.map((t: any) => (
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
                      {t.amount?.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })} {t.currency}
                    </td>
                    <td className="p-3.5">
                      <StatusBadge status={t.status} />
                    </td>
                    <td className="p-3.5 text-[#71819A] whitespace-nowrap">
                      {new Date(t.timestamp).toLocaleDateString()} {new Date(t.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                    </td>
                  </tr>
                ))
              ) : (
                <tr>
                  <td colSpan={6} className="p-8 text-center text-[#71819A]">
                    No transactions yet. Click &quot;Send Money&quot; to test your first simulated transfer!
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>

      {/* CHANGE / SET NEW TRANSFER PASSWORD MODAL */}
      {showPasswordModal && (
        <Modal
          isOpen={showPasswordModal}
          onClose={() => {
            if (!isPasswordChangeRequired) setShowPasswordModal(false);
          }}
          title={isPasswordChangeRequired ? 'Set New Transfer Password' : 'Change Transfer Password'}
          subtitle={
            isPasswordChangeRequired
              ? 'Compliance Restoration: Please set a new transfer password to complete reactivation'
              : 'Update your dedicated money movement authorization password'
          }
          maxWidth="md"
        >
          <form onSubmit={handleChangeTransferPassword} className="space-y-4 text-xs">
            {passwordModalSuccess ? (
              <div className="p-4 rounded-xl bg-[#27C58B]/10 border border-[#27C58B]/30 text-[#27C58B] flex items-center gap-3">
                <Check className="w-5 h-5 shrink-0 stroke-[3]" />
                <div className="space-y-0.5">
                  <p className="font-bold text-white text-sm">Transfer Password Updated Successfully!</p>
                  <p className="text-xs text-[#27C58B]/90">
                    Your transfer access is now ACTIVE. You can make money transfers freely.
                  </p>
                </div>
              </div>
            ) : (
              <>
                {passwordModalError && (
                  <div className="p-3 rounded-xl bg-[#F06470]/10 border border-[#F06470]/30 text-xs text-[#F06470] flex items-center gap-2">
                    <AlertCircle className="w-4 h-4 shrink-0" />
                    <span>{passwordModalError}</span>
                  </div>
                )}

                {/* Only ask for current password if not strictly recovering through compliance bypass */}
                {!isPasswordChangeRequired && (
                  <div>
                    <label className="block text-[11px] font-bold uppercase tracking-wider text-[#A7B4C8] mb-1">
                      Current Transfer Password
                    </label>
                    <input
                      type={showPasswordText ? 'text' : 'password'}
                      value={currentTransferPassword}
                      onChange={(e) => setCurrentTransferPassword(e.target.value)}
                      placeholder="Enter current transfer password"
                      className="w-full px-3 py-2 bg-[#080D19] border border-[#25344A] rounded-xl text-xs text-[#F4F7FC] placeholder-[#71819A] focus:outline-none focus:border-[#3978F6]"
                    />
                  </div>
                )}

                <div>
                  <label className="block text-[11px] font-bold uppercase tracking-wider text-[#A7B4C8] mb-1">
                    New Transfer Password (Min 6 Characters)
                  </label>
                  <div className="relative">
                    <input
                      type={showPasswordText ? 'text' : 'password'}
                      required
                      value={newTransferPassword}
                      onChange={(e) => setNewTransferPassword(e.target.value)}
                      placeholder="Enter new transfer password"
                      className="w-full pl-3 pr-9 py-2 bg-[#080D19] border border-[#25344A] rounded-xl text-xs text-[#F4F7FC] placeholder-[#71819A] focus:outline-none focus:border-[#29C5D9]"
                    />
                    <button
                      type="button"
                      onClick={() => setShowPasswordText(!showPasswordText)}
                      className="absolute right-2.5 top-2.5 text-[#71819A] hover:text-[#F4F7FC]"
                    >
                      {showPasswordText ? <EyeOff className="h-3.5 w-3.5" /> : <Eye className="h-3.5 w-3.5 text-[#A7B4C8]" />}
                    </button>
                  </div>
                </div>

                <div>
                  <label className="block text-[11px] font-bold uppercase tracking-wider text-[#A7B4C8] mb-1">
                    Confirm New Transfer Password
                  </label>
                  <input
                    type={showPasswordText ? 'text' : 'password'}
                    required
                    value={confirmTransferPassword}
                    onChange={(e) => setConfirmTransferPassword(e.target.value)}
                    placeholder="Repeat new transfer password"
                    className="w-full px-3 py-2 bg-[#080D19] border border-[#25344A] rounded-xl text-xs text-[#F4F7FC] placeholder-[#71819A] focus:outline-none focus:border-[#29C5D9]"
                  />
                </div>

                <div className="flex items-center justify-end gap-3 pt-3">
                  {!isPasswordChangeRequired && (
                    <button
                      type="button"
                      onClick={() => setShowPasswordModal(false)}
                      className="px-4 py-2 rounded-xl bg-slate-800 hover:bg-slate-700 text-slate-300 font-semibold cursor-pointer"
                    >
                      Cancel
                    </button>
                  )}
                  <button
                    type="submit"
                    disabled={passwordModalLoading}
                    className="flex items-center gap-2 px-5 py-2.5 rounded-xl bg-[#3978F6] hover:bg-[#3978F6]/90 disabled:opacity-50 text-white font-bold shadow-lg shadow-blue-500/25 cursor-pointer"
                  >
                    {passwordModalLoading ? (
                      <span>Updating Password...</span>
                    ) : (
                      <>
                        <ShieldCheck className="w-4 h-4 text-[#29C5D9]" />
                        <span>Save Transfer Password</span>
                      </>
                    )}
                  </button>
                </div>
              </>
            )}
          </form>
        </Modal>
      )}

      {/* TRANSFER BLOCKED INTERCEPT MODAL */}
      {showTransferBlockedModal && (
        <Modal
          isOpen={showTransferBlockedModal}
          onClose={() => setShowTransferBlockedModal(false)}
          title="Transfer Access Restricted"
          subtitle="Security Hold Enforced (3 Failed Password Attempts)"
          maxWidth="md"
        >
          <div className="space-y-4 text-xs">
            <div className="p-4 rounded-xl bg-[#F06470]/10 border border-[#F06470]/30 text-[#F06470] flex items-start gap-3">
              <AlertTriangle className="w-5 h-5 shrink-0 text-[#F06470] mt-0.5" />
              <div className="space-y-1">
                <p className="font-bold text-white text-sm">Transfers Locked Due to 3 Incorrect Attempts</p>
                <p className="text-[#F06470]/90 leading-relaxed text-xs">
                  You entered your transfer password incorrectly 3 times. For your financial security, money movement is temporarily locked. Your account login remains active.
                </p>
              </div>
            </div>

            <div className="p-4 rounded-xl bg-[#080D19] border border-[#25344A] space-y-2 text-[#F4F7FC]">
              <span className="text-[10px] font-bold text-[#A7B4C8] uppercase tracking-wider">How to Restore Transfer Privileges</span>
              <ul className="list-disc pl-4 space-y-1.5 text-xs text-[#A7B4C8]">
                <li>Open a support ticket with the Helpdesk.</li>
                <li>Upload a clear photo of your National ID or Passport (Front &amp; Back).</li>
                <li>Compliance officers will verify your account ownership and restore your transfer access.</li>
              </ul>
            </div>

            <div className="flex items-center justify-end gap-3 pt-2">
              <button
                type="button"
                onClick={() => setShowTransferBlockedModal(false)}
                className="px-4 py-2.5 rounded-xl bg-slate-800 hover:bg-slate-700 text-slate-300 font-semibold cursor-pointer text-xs"
              >
                Close
              </button>
              <button
                type="button"
                onClick={() => {
                  setShowTransferBlockedModal(false);
                  navigate('/customer/support?reason=TRANSFER_BLOCKED');
                }}
                className="flex items-center gap-2 px-5 py-2.5 rounded-xl bg-[#F06470] hover:bg-[#F06470]/90 text-white font-bold shadow-lg shadow-rose-500/25 cursor-pointer text-xs"
              >
                <LifeBuoy className="w-4 h-4" />
                <span>Go to Support &amp; Verify ID</span>
                <ArrowRight className="w-4 h-4" />
              </button>
            </div>
          </div>
        </Modal>
      )}

      {/* Demo Disclaimer Footer */}
      <div className="p-4 rounded-lg bg-[#101A2B] border border-[#25344A] flex items-center gap-3 text-xs text-[#71819A]">
        <AlertCircle className="h-4 w-4 text-[#F4B942] shrink-0" />
        <span>
          <strong>Demo Banking Environment:</strong> Omerta.ai is a simulation environment for financial crime intelligence and compliance testing. Balances and transfers do not represent real funds.
        </span>
      </div>
    </div>
  );
};

