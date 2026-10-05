import React, { useState, useEffect } from 'react';
import { Outlet, useNavigate } from 'react-router-dom';
import { Sidebar } from './Sidebar';
import { Header } from './Header';
import {
  Search,
  ArrowRight,
  ShieldAlert,
  Users,
  Wallet,
  Smartphone,
  KeyRound,
  ShieldCheck,
  Check,
  AlertCircle,
  Eye,
  EyeOff,
  Lock,
} from 'lucide-react';
import { Modal } from '../common/Modal';
import { useAuth } from '../../context/AuthContext';
import { api } from '../../api/client';

export const AppLayout: React.FC = () => {
  const { user, customer, refreshCustomerProfile } = useAuth();
  const [collapsed, setCollapsed] = useState(false);
  const [searchOpen, setSearchOpen] = useState(false);
  const [searchQuery, setSearchQuery] = useState('');
  const navigate = useNavigate();

  // Global Set Transfer Password Modal State (Available everywhere)
  const [passwordModalOpen, setPasswordModalOpen] = useState(false);
  const [newTransferPassword, setNewTransferPassword] = useState('');
  const [confirmTransferPassword, setConfirmTransferPassword] = useState('');
  const [showPasswordText, setShowPasswordText] = useState(false);
  const [passwordModalLoading, setPasswordModalLoading] = useState(false);
  const [passwordModalError, setPasswordModalError] = useState<string | null>(null);
  const [passwordModalSuccess, setPasswordModalSuccess] = useState(false);

  const isCustomer = user?.role === 'CUSTOMER';
  const requirePasswordChange = Boolean(isCustomer && customer?.require_transfer_password_change);

  // Periodic check of customer profile status
  useEffect(() => {
    if (!isCustomer) return;
    refreshCustomerProfile();
    const interval = setInterval(() => {
      refreshCustomerProfile();
    }, 5000);
    return () => clearInterval(interval);
  }, [isCustomer]);

  // Global keyboard shortcut for ⌘K search
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key === 'k') {
        e.preventDefault();
        setSearchOpen((prev) => !prev);
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, []);

  const handleSearchSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!searchQuery.trim()) return;
    setSearchOpen(false);
    navigate(`/transactions?search=${encodeURIComponent(searchQuery.trim())}`);
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
      });

      setPasswordModalSuccess(true);
      await refreshCustomerProfile();

      setTimeout(() => {
        setPasswordModalOpen(false);
        setPasswordModalSuccess(false);
        setNewTransferPassword('');
        setConfirmTransferPassword('');
      }, 1800);
    } catch (err: any) {
      setPasswordModalError(err.message || 'Failed to update transfer password. Please try again.');
    } finally {
      setPasswordModalLoading(false);
    }
  };

  const quickLinks = [
    { label: 'High-Risk Review Queue', path: '/risk-monitoring', icon: ShieldAlert },
    { label: 'All Transactions', path: '/transactions', icon: ArrowRight },
    { label: 'Customer Directory', path: '/customers', icon: Users },
    { label: 'Account Directory', path: '/accounts', icon: Wallet },
    { label: 'Device Intelligence', path: '/devices', icon: Smartphone },
  ];

  return (
    <div className="min-h-screen bg-[#080D19] text-[#F4F7FC] flex transition-colors duration-200">
      {/* Sidebar Navigation */}
      <Sidebar collapsed={collapsed} onToggle={() => setCollapsed(!collapsed)} />

      {/* Main Workspace Frame */}
      <div
        className={`flex-1 flex flex-col min-w-0 transition-all duration-300 ${
          collapsed ? 'ml-20' : 'ml-64'
        }`}
      >
        <Header collapsed={collapsed} onOpenSearch={() => setSearchOpen(true)} />

        {/* TOP PERSISTENT NOTIFICATION BAR: TRANSFER PRIVILEGES RESTORED */}
        {requirePasswordChange && (
          <div className="mt-16 bg-gradient-to-r from-cyan-950/90 via-[#101A2B] to-emerald-950/90 border-b border-cyan-500/40 px-6 py-3 flex flex-col sm:flex-row items-center justify-between gap-3 shadow-lg z-20">
            <div className="flex items-center gap-3">
              <div className="w-8 h-8 rounded-full bg-cyan-500/20 text-cyan-400 flex items-center justify-center shrink-0 border border-cyan-500/40">
                <KeyRound className="w-4 h-4" />
              </div>
              <div className="space-y-0.5">
                <p className="text-xs font-bold text-white flex items-center gap-2">
                  <span>Action Required: Transfer Privileges Restored!</span>
                  <span className="px-2 py-0.2 rounded-full bg-cyan-500/20 text-cyan-300 text-[10px] font-mono border border-cyan-500/30">
                    Send Money Locked
                  </span>
                </p>
                <p className="text-[11px] text-slate-300 leading-tight">
                  Compliance has verified your identity and restored access. Please set your new Transfer Password to activate money movement.
                </p>
              </div>
            </div>

            <button
              type="button"
              onClick={() => {
                setPasswordModalError(null);
                setPasswordModalOpen(true);
              }}
              className="px-4 py-2 rounded-xl bg-gradient-to-r from-blue-600 to-cyan-500 hover:opacity-90 text-slate-950 text-xs font-black shadow-md shadow-cyan-500/20 flex items-center gap-1.5 shrink-0 cursor-pointer transition-transform hover:scale-102"
            >
              <Lock className="w-3.5 h-3.5 stroke-[2.5]" />
              <span>Set New Transfer Password</span>
              <ArrowRight className="w-3.5 h-3.5 stroke-[2.5]" />
            </button>
          </div>
        )}

        <main className={`flex-1 p-6 md:p-8 max-w-7xl w-full mx-auto space-y-6 ${requirePasswordChange ? 'mt-0' : 'mt-16'}`}>
          <Outlet />
        </main>
      </div>

      {/* Global Search Modal (⌘K) */}
      <Modal
        isOpen={searchOpen}
        onClose={() => setSearchOpen(false)}
        title="Global Intelligence Search"
        subtitle="Search transactions, accounts, customers, devices or alerts across Omerta.ai"
        maxWidth="lg"
      >
        <form onSubmit={handleSearchSubmit} className="space-y-4">
          <div className="relative">
            <Search className="absolute left-3.5 top-3 h-5 w-5 text-slate-400 dark:text-slate-500" />
            <input
              type="text"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder="e.g. TXN-001, ACC-1001, DEV-123, Cairo Tech..."
              autoFocus
              className="w-full pl-11 pr-4 py-2.5 bg-white dark:bg-slate-900 border border-slate-300 dark:border-slate-700 rounded-xl text-slate-900 dark:text-white placeholder-slate-400 dark:placeholder-slate-500 focus:outline-none focus:border-sky-500 dark:focus:border-cyan-400 text-sm shadow-inner"
            />
          </div>

          <div className="pt-2">
            <p className="text-[11px] font-bold uppercase tracking-wider text-slate-500 dark:text-slate-400 mb-2">
              Quick Shortcuts
            </p>
            <div className="space-y-1">
              {quickLinks.map((item) => (
                <button
                  key={item.path}
                  type="button"
                  onClick={() => {
                    setSearchOpen(false);
                    navigate(item.path);
                  }}
                  className="w-full flex items-center justify-between p-2.5 rounded-lg text-sm font-medium text-slate-700 dark:text-slate-200 hover:bg-slate-100 dark:hover:bg-slate-800 hover:text-sky-700 dark:hover:text-cyan-300 transition-colors"
                >
                  <div className="flex items-center gap-2.5">
                    <item.icon className="h-4 w-4 text-slate-500 dark:text-slate-400" />
                    <span>{item.label}</span>
                  </div>
                  <ArrowRight className="h-3.5 w-3.5 text-slate-400 dark:text-slate-500" />
                </button>
              ))}
            </div>
          </div>
        </form>
      </Modal>

      {/* GLOBAL SET NEW TRANSFER PASSWORD MODAL */}
      {passwordModalOpen && (
        <Modal
          isOpen={passwordModalOpen}
          onClose={() => setPasswordModalOpen(false)}
          title="Set New Transfer Password"
          subtitle="Compliance Restoration: Please set a new transfer password to complete reactivation"
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

                <div className="p-3 rounded-xl bg-[#29C5D9]/10 border border-[#29C5D9]/30 text-[#29C5D9] flex items-start gap-2.5">
                  <ShieldCheck className="w-4 h-4 shrink-0 mt-0.5" />
                  <p className="text-[11px] leading-relaxed text-[#F4F7FC]">
                    Your account ownership was verified by Compliance. Set your new dedicated transfer password below to enable Send Money.
                  </p>
                </div>

                <div>
                  <label className="block text-[11px] font-bold uppercase tracking-wider text-[#A7B4C8] mb-1">
                    New Transfer Password (Min 8 Characters)
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
                  <button
                    type="submit"
                    disabled={passwordModalLoading}
                    className="flex items-center gap-2 px-5 py-2.5 rounded-xl bg-[#3978F6] hover:bg-[#3978F6]/90 disabled:opacity-50 text-white font-bold shadow-lg shadow-blue-500/25 cursor-pointer text-xs"
                  >
                    {passwordModalLoading ? (
                      <span>Saving Password...</span>
                    ) : (
                      <>
                        <ShieldCheck className="w-4 h-4 text-[#29C5D9]" />
                        <span>Save &amp; Reactivate Transfers</span>
                      </>
                    )}
                  </button>
                </div>
              </>
            )}
          </form>
        </Modal>
      )}
    </div>
  );
};
