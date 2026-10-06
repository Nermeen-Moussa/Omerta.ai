import React, { useState } from 'react';
import {
  Search,
  Bell,
  UserCheck,
  Activity,
  LogOut,
  ChevronDown,
  Sun,
  Moon,
  Monitor,
  Copy,
  Check,
  Send,
  Building,
} from 'lucide-react';
import { useAuth } from '../../context/AuthContext';
import { useTheme } from '../../context/ThemeContext';
import { useNavigate } from 'react-router-dom';

interface HeaderProps {
  collapsed: boolean;
  onOpenSearch: () => void;
}

export const Header: React.FC<HeaderProps> = ({ collapsed, onOpenSearch }) => {
  const { user, customer, logout } = useAuth();
  const { theme, resolvedTheme, setTheme } = useTheme();
  const [roleMenuOpen, setRoleMenuOpen] = useState(false);
  const [themeMenuOpen, setThemeMenuOpen] = useState(false);
  const [copied, setCopied] = useState(false);
  const navigate = useNavigate();

  const isCustomer = user?.role === 'CUSTOMER';

  const handleCopyUserNumber = () => {
    if (customer?.omerta_user_number) {
      navigator.clipboard.writeText(customer.omerta_user_number);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    }
  };

  return (
    <header
      className={`fixed top-0 right-0 z-30 flex items-center justify-between h-16 px-6 bg-[#0B1220]/95 backdrop-blur-md border-b border-[#25344A] transition-all duration-300 shadow-sm ${
        collapsed ? 'left-20' : 'left-64'
      }`}
    >
      {/* Left section */}
      <div className="flex items-center gap-4 flex-1 max-w-md">
        {isCustomer ? (
          <div className="flex items-center gap-3">
            {customer?.omerta_user_number && (
              <div className="flex items-center gap-2 px-3 py-1.5 rounded-lg bg-[#101A2B] border border-[#25344A]">
                <span className="text-[11px] font-medium text-[#71819A]">Omerta User #:</span>
                <span className="text-xs font-mono font-bold text-[#F4F7FC]">
                  {customer.omerta_user_number}
                </span>
                <button
                  onClick={handleCopyUserNumber}
                  className="p-1 text-[#A7B4C8] hover:text-[#F4F7FC] rounded hover:bg-[#1B2B43] transition-colors"
                  title="Copy Omerta User Number for transfers"
                >
                  {copied ? <Check className="h-3.5 w-3.5 text-[#27C58B]" /> : <Copy className="h-3.5 w-3.5" />}
                </button>
              </div>
            )}
            <button
              onClick={() => navigate('/customer/transfer')}
              className="hidden sm:flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-[#3978F6] hover:bg-[#3978F6]/90 text-[#F4F7FC] text-xs font-bold transition-colors shadow-sm"
            >
              <Send className="h-3.5 w-3.5" />
              <span>Send Money</span>
            </button>
          </div>
        ) : (
          <button
            onClick={onOpenSearch}
            className="flex items-center justify-between w-full px-3.5 py-2 rounded-lg bg-[#101A2B] border border-[#25344A] text-sm text-[#A7B4C8] hover:text-[#F4F7FC] hover:border-[#3978F6]/50 transition-colors shadow-inner"
          >
            <div className="flex items-center gap-2">
              <Search className="h-4 w-4 text-[#71819A]" />
              <span>Search transactions, users, accounts...</span>
            </div>
            <kbd className="hidden sm:inline-block px-2 py-0.5 text-[10px] font-mono text-[#A7B4C8] bg-[#152238] border border-[#25344A] rounded shadow-xs">
              ⌘K
            </kbd>
          </button>
        )}
      </div>

      {/* Header Actions */}
      <div className="flex items-center gap-3 sm:gap-4">
        {/* Environment / Threshold Indicator */}
        {!isCustomer ? (
          <div className="hidden lg:flex items-center gap-2 px-3 py-1.5 rounded-full bg-[#101A2B] border border-[#25344A] text-xs text-[#A7B4C8] font-medium">
            <Activity className="h-3.5 w-3.5 text-[#29C5D9] animate-pulse" />
            <span>Human Review Rule:</span>
            <span className="font-bold text-[#F4B942]">score &gt; 40.00</span>
          </div>
        ) : (
          <div className="hidden md:flex items-center gap-2 px-3 py-1.5 rounded-full bg-[#101A2B] border border-[#25344A] text-xs text-[#A7B4C8] font-medium">
            <div className="h-2 w-2 rounded-full bg-[#27C58B] animate-pulse" />
            <span>Simulated Banking Network:</span>
            <span className="font-bold text-[#27C58B]">ACTIVE</span>
          </div>
        )}

        {/* Theme Mode Switcher Toggle */}
        <div className="relative">
          <button
            onClick={() => setThemeMenuOpen(!themeMenuOpen)}
            className="p-2 text-[#A7B4C8] hover:text-[#F4F7FC] rounded-lg hover:bg-[#1B2B43] transition-colors flex items-center gap-1 border border-[#25344A] bg-[#101A2B]"
            title={`Active Theme: ${theme.toUpperCase()} (Click to change)`}
          >
            {resolvedTheme === 'dark' ? (
              <Moon className="h-4 w-4 text-[#3978F6]" />
            ) : (
              <Sun className="h-4 w-4 text-[#F4B942]" />
            )}
            <ChevronDown className="h-3 w-3 text-[#71819A]" />
          </button>

          {themeMenuOpen && (
            <div className="absolute right-0 mt-2 w-48 omerta-card border-[#25344A] p-2 shadow-2xl z-50 animate-in fade-in zoom-in-95 duration-100 bg-[#152238]">
              <div className="px-2.5 py-1.5 border-b border-[#25344A] text-[11px] font-bold text-[#71819A] uppercase tracking-wider">
                Select Workspace Theme
              </div>
              <div className="py-1 space-y-1">
                <button
                  onClick={() => {
                    setTheme('dark');
                    setThemeMenuOpen(false);
                  }}
                  className={`w-full flex items-center gap-2.5 px-2.5 py-2 rounded-lg text-xs transition-colors ${
                    theme === 'dark'
                      ? 'bg-[#3978F6]/20 text-[#29C5D9] font-bold border border-[#3978F6]/40'
                      : 'text-[#A7B4C8] hover:bg-[#1B2B43] hover:text-[#F4F7FC]'
                  }`}
                >
                  <Moon className="h-4 w-4 text-[#3978F6]" />
                  <span>Dark Mode</span>
                </button>

                <button
                  onClick={() => {
                    setTheme('light');
                    setThemeMenuOpen(false);
                  }}
                  className={`w-full flex items-center gap-2.5 px-2.5 py-2 rounded-lg text-xs transition-colors ${
                    theme === 'light'
                      ? 'bg-[#3978F6]/20 text-[#29C5D9] font-bold border border-[#3978F6]/40'
                      : 'text-[#A7B4C8] hover:bg-[#1B2B43] hover:text-[#F4F7FC]'
                  }`}
                >
                  <Sun className="h-4 w-4 text-[#F4B942]" />
                  <span>Light Mode</span>
                </button>

                <button
                  onClick={() => {
                    setTheme('system');
                    setThemeMenuOpen(false);
                  }}
                  className={`w-full flex items-center gap-2.5 px-2.5 py-2 rounded-lg text-xs transition-colors ${
                    theme === 'system'
                      ? 'bg-[#3978F6]/20 text-[#29C5D9] font-bold border border-[#3978F6]/40'
                      : 'text-[#A7B4C8] hover:bg-[#1B2B43] hover:text-[#F4F7FC]'
                  }`}
                >
                  <Monitor className="h-4 w-4 text-[#71819A]" />
                  <span>System Automatic</span>
                </button>
              </div>
            </div>
          )}
        </div>

        {/* Notifications / Queue Icon */}
        {!isCustomer && (
          <button
            onClick={() => navigate('/admin/risk-monitoring')}
            className="relative p-2 text-[#A7B4C8] hover:text-[#F4F7FC] rounded-lg hover:bg-[#1B2B43] transition-colors border border-[#25344A] bg-[#101A2B]"
            title="Review Queue Alerts"
          >
            <Bell className="h-5 w-5" />
            <span className="absolute top-1.5 right-1.5 h-2 w-2 rounded-full bg-[#F4B942] animate-ping" />
            <span className="absolute top-1.5 right-1.5 h-2 w-2 rounded-full bg-[#F4B942]" />
          </button>
        )}

        {/* User Profile Menu */}
        <div className="relative">
          <button
            onClick={() => setRoleMenuOpen(!roleMenuOpen)}
            className="flex items-center gap-3 p-1.5 pl-2.5 rounded-xl bg-[#101A2B] border border-[#25344A] hover:border-[#3978F6]/40 transition-all text-left cursor-pointer"
          >
            <div className="hidden sm:flex flex-col text-right">
              <span className="text-xs font-bold text-[#F4F7FC] tracking-tight">
                {user?.full_name || 'Banking User'}
              </span>
              <span className="text-[10px] font-bold text-[#29C5D9] uppercase tracking-wider">
                {user?.role?.replace('_', ' ') || 'CUSTOMER'}
              </span>
            </div>
            <div className="h-8 w-8 rounded-lg bg-gradient-to-tr from-[#3978F6] to-[#29C5D9] text-slate-950 font-bold flex items-center justify-center text-xs shadow-md shadow-cyan-500/10">
              {isCustomer ? <Building className="h-4 w-4 text-slate-950 stroke-[2.5]" /> : <UserCheck className="h-4 w-4 text-slate-950 stroke-[2.5]" />}
            </div>
            <ChevronDown className="h-3.5 w-3.5 text-[#71819A] hidden sm:block" />
          </button>

          {/* User Account Dropdown */}
          {roleMenuOpen && (
            <div className="absolute right-0 mt-2 w-64 omerta-card border-[#25344A] p-2 shadow-2xl z-50 animate-in fade-in zoom-in-95 duration-100 bg-[#152238] rounded-xl">
              <div className="px-3 py-2.5 border-b border-[#25344A]">
                <p className="text-xs font-bold text-[#F4F7FC] truncate">{user?.full_name}</p>
                <p className="text-[11px] text-[#A7B4C8] truncate font-mono mt-0.5">
                  {isCustomer && customer?.omerta_user_number ? customer.omerta_user_number : user?.email}
                </p>
                <div className="mt-1.5 inline-flex items-center px-2 py-0.5 rounded-full text-[10px] font-bold bg-[#3978F6]/20 text-[#29C5D9] border border-[#3978F6]/40">
                  {user?.role?.replace('_', ' ')}
                </div>
              </div>

              <div className="py-1 space-y-0.5">
                {isCustomer ? (
                  <>
                    <button
                      onClick={() => {
                        navigate('/customer/dashboard');
                        setRoleMenuOpen(false);
                      }}
                      className="w-full text-left px-3 py-2 rounded-lg text-xs text-[#A7B4C8] hover:bg-[#1B2B43] hover:text-[#F4F7FC] transition-colors flex items-center gap-2 cursor-pointer"
                    >
                      <Activity className="h-3.5 w-3.5 text-[#3978F6]" />
                      <span>Banking Dashboard</span>
                    </button>
                    <button
                      onClick={() => {
                        navigate('/customer/transfer');
                        setRoleMenuOpen(false);
                      }}
                      className="w-full text-left px-3 py-2 rounded-lg text-xs text-[#A7B4C8] hover:bg-[#1B2B43] hover:text-[#F4F7FC] transition-colors flex items-center gap-2 cursor-pointer"
                    >
                      <Send className="h-3.5 w-3.5 text-[#27C58B]" />
                      <span>Send Money</span>
                    </button>
                    <button
                      onClick={() => {
                        navigate('/customer/security');
                        setRoleMenuOpen(false);
                      }}
                      className="w-full text-left px-3 py-2 rounded-lg text-xs text-[#A7B4C8] hover:bg-[#1B2B43] hover:text-[#F4F7FC] transition-colors flex items-center gap-2 cursor-pointer"
                    >
                      <Monitor className="h-3.5 w-3.5 text-[#29C5D9]" />
                      <span>Security &amp; Sessions</span>
                    </button>
                    <button
                      onClick={() => {
                        navigate('/customer/profile');
                        setRoleMenuOpen(false);
                      }}
                      className="w-full text-left px-3 py-2 rounded-lg text-xs text-[#A7B4C8] hover:bg-[#1B2B43] hover:text-[#F4F7FC] transition-colors flex items-center gap-2 cursor-pointer"
                    >
                      <UserCheck className="h-3.5 w-3.5 text-[#F4B942]" />
                      <span>Account Profile</span>
                    </button>
                  </>
                ) : (
                  <>
                    <button
                      onClick={() => {
                        navigate('/admin/dashboard');
                        setRoleMenuOpen(false);
                      }}
                      className="w-full text-left px-3 py-2 rounded-lg text-xs text-[#A7B4C8] hover:bg-[#1B2B43] hover:text-[#F4F7FC] transition-colors flex items-center gap-2 cursor-pointer"
                    >
                      <Activity className="h-3.5 w-3.5 text-[#3978F6]" />
                      <span>Control Center</span>
                    </button>
                    <button
                      onClick={() => {
                        navigate('/admin/users');
                        setRoleMenuOpen(false);
                      }}
                      className="w-full text-left px-3 py-2 rounded-lg text-xs text-[#A7B4C8] hover:bg-[#1B2B43] hover:text-[#F4F7FC] transition-colors flex items-center gap-2 cursor-pointer"
                    >
                      <UserCheck className="h-3.5 w-3.5 text-[#29C5D9]" />
                      <span>User Management</span>
                    </button>
                    <button
                      onClick={() => {
                        navigate('/admin/audit-logs');
                        setRoleMenuOpen(false);
                      }}
                      className="w-full text-left px-3 py-2 rounded-lg text-xs text-[#A7B4C8] hover:bg-[#1B2B43] hover:text-[#F4F7FC] transition-colors flex items-center gap-2 cursor-pointer"
                    >
                      <Monitor className="h-3.5 w-3.5 text-[#F4B942]" />
                      <span>Audit &amp; Telemetry</span>
                    </button>
                  </>
                )}
              </div>

              <div className="pt-2 mt-1 border-t border-[#25344A]">
                <button
                  onClick={() => {
                    logout();
                    navigate('/login');
                  }}
                  className="w-full flex items-center gap-2 px-3 py-2 rounded-lg text-xs font-semibold text-[#F06470] hover:bg-[#F06470]/10 transition-colors cursor-pointer"
                >
                  <LogOut className="h-3.5 w-3.5" />
                  <span>Log out session</span>
                </button>
              </div>
            </div>
          )}
        </div>
      </div>
    </header>
  );
};
