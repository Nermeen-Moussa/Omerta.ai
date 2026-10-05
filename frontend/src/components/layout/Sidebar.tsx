import React from 'react';
import { NavLink } from 'react-router-dom';
import {
  LayoutDashboard,
  ArrowLeftRight,
  ShieldAlert,
  FolderSearch,
  Users,
  Wallet,
  Smartphone,
  Share2,
  FileBarChart,
  BarChart3,
  ScrollText,
  Settings,
  ChevronLeft,
  ChevronRight,
  ShieldCheck,
  Send,
  UserCheck,
  Building,
  Bot,
} from 'lucide-react';
import { useAuth } from '../../context/AuthContext';

interface SidebarProps {
  collapsed: boolean;
  onToggle: () => void;
}

interface NavItem {
  to: string;
  label: string;
  icon: React.ComponentType<{ className?: string }>;
  badge?: string;
}

export const Sidebar: React.FC<SidebarProps> = ({ collapsed, onToggle }) => {
  const { user } = useAuth();
  const role = user?.role || 'CUSTOMER';
  const isCustomer = role === 'CUSTOMER';

  const customerNavItems: NavItem[] = [
    { to: '/customer/dashboard', label: 'Dashboard', icon: LayoutDashboard },
    { to: '/customer/accounts', label: 'My Accounts', icon: Wallet },
    { to: '/customer/transfer', label: 'Send Money', icon: Send },
    { to: '/customer/transactions', label: 'Transactions', icon: ArrowLeftRight },
    { to: '/customer/security', label: 'Security & Devices', icon: ShieldCheck },
    { to: '/customer/profile', label: 'Profile', icon: UserCheck },
  ];

  const investigatorNavItems: NavItem[] = [
    { to: '/admin/investigations', label: 'Investigations', icon: FolderSearch },
    { to: '/admin/network-analysis', label: 'Network Graph Analysis', icon: Share2 },
    { to: '/admin/ai-assistant', label: 'AI Copilot & RAG', icon: Bot, badge: 'Coming Soon' },
    { to: '/admin/audit-logs', label: 'Audit Trail', icon: ScrollText },
  ];

  const analystNavItems: NavItem[] = [
    { to: '/admin/dashboard', label: 'Analyst Overview', icon: LayoutDashboard },
    { to: '/admin/transactions', label: 'Transactions', icon: ArrowLeftRight },
    { to: '/admin/risk-monitoring', label: 'Risk Queue', icon: ShieldAlert, badge: '>40 Queue' },
    { to: '/admin/investigations', label: 'Investigations', icon: FolderSearch },
    { to: '/admin/reports', label: 'Reports', icon: FileBarChart },
    { to: '/admin/ai-assistant', label: 'AI Copilot & RAG', icon: Bot, badge: 'Coming Soon' },
  ];

  const auditorNavItems: NavItem[] = [
    { to: '/admin/audit-logs', label: 'Audit Logs', icon: ScrollText },
    { to: '/admin/reports', label: 'Compliance Reports', icon: FileBarChart },
    { to: '/admin/transactions', label: 'Transactions (Read-Only)', icon: ArrowLeftRight },
    { to: '/admin/investigations', label: 'Investigations (Read-Only)', icon: FolderSearch },
  ];

  const adminNavItems: NavItem[] = [
    { to: '/admin/dashboard', label: 'Overview', icon: LayoutDashboard },
    { to: '/admin/transactions', label: 'Transactions', icon: ArrowLeftRight },
    { to: '/admin/risk-monitoring', label: 'Risk Monitoring', icon: ShieldAlert, badge: '>40 Queue' },
    { to: '/admin/investigations', label: 'Investigations', icon: FolderSearch },
    { to: '/admin/users', label: 'User Management', icon: Users },
    { to: '/admin/accounts', label: 'Accounts', icon: Wallet },
    { to: '/admin/devices', label: 'Devices', icon: Smartphone },
    { to: '/admin/network-analysis', label: 'Network Analysis', icon: Share2 },
    { to: '/admin/reports', label: 'Reports', icon: FileBarChart },
    { to: '/admin/analytics', label: 'Analytics', icon: BarChart3 },
    { to: '/admin/audit-logs', label: 'Audit Logs', icon: ScrollText },
    { to: '/admin/ai-assistant', label: 'AI Copilot & RAG', icon: Bot, badge: 'Coming Soon' },
    { to: '/admin/settings', label: 'Settings', icon: Settings },
  ];

  let navItems: NavItem[] = customerNavItems;
  if (role === 'ADMINISTRATOR' || role === 'SUB_ADMINISTRATOR') {
    navItems = adminNavItems;
  } else if (role === 'SENIOR_INVESTIGATOR' || role === 'INVESTIGATOR') {
    navItems = investigatorNavItems;
  } else if (role === 'FRAUD_ANALYST') {
    navItems = analystNavItems;
  } else if (role === 'AUDITOR' || role === 'COMPLIANCE_AUDITOR') {
    navItems = auditorNavItems;
  }

  return (
    <aside
      className={`fixed left-0 top-0 bottom-0 z-40 flex flex-col bg-[#0B1220] border-r border-[#25344A] transition-all duration-300 ${
        collapsed ? 'w-20' : 'w-64'
      }`}
    >
      {/* Brand Header */}
      <div className="flex items-center justify-between h-16 px-4 border-b border-[#25344A]">
        <NavLink to={isCustomer ? '/customer/dashboard' : '/admin/dashboard'} className="flex items-center gap-3 overflow-hidden">
          <div className="flex items-center justify-center h-10 w-10 min-w-[2.5rem] rounded-xl bg-gradient-to-tr from-[#3978F6] to-[#29C5D9] text-slate-950 font-black shadow-lg shadow-cyan-500/20">
            {isCustomer ? <Building className="h-5 w-5 text-slate-950 stroke-[2.5]" /> : <ShieldCheck className="h-6 w-6 text-slate-950 stroke-[2.5]" />}
          </div>
          {!collapsed && (
            <div className="flex flex-col">
              <span className="text-lg font-bold tracking-tight text-[#F4F7FC] flex items-center gap-1">
                OMERTA<span className="text-[#29C5D9]">.AI</span>
              </span>
              <span className="text-[10px] font-semibold tracking-wider text-[#A7B4C8] uppercase">
                {isCustomer ? 'Customer Banking' : 'Admin Intelligence'}
              </span>
            </div>
          )}
        </NavLink>
        <button
          onClick={onToggle}
          className="hidden md:flex p-1.5 text-[#A7B4C8] hover:text-[#F4F7FC] rounded-lg hover:bg-[#1B2B43] transition-colors"
          title={collapsed ? 'Expand Sidebar' : 'Collapse Sidebar'}
        >
          {collapsed ? <ChevronRight className="h-4 w-4" /> : <ChevronLeft className="h-4 w-4" />}
        </button>
      </div>

      {/* Navigation Links */}
      <nav className="flex-1 px-3 py-4 space-y-1.5 overflow-y-auto">
        {navItems.map((item) => (
          <NavLink
            key={item.to}
            to={item.to}
            className={({ isActive }) =>
              `flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-all duration-150 group relative ${
                isActive
                  ? 'bg-[#3978F6]/20 text-[#29C5D9] border border-[#3978F6]/40 font-bold shadow-sm'
                  : 'text-[#A7B4C8] hover:text-[#F4F7FC] hover:bg-[#1B2B43]'
              } ${collapsed ? 'justify-center' : ''}`
            }
          >
            <item.icon className="h-5 w-5 min-w-[1.25rem] transition-transform group-hover:scale-110 text-[#A7B4C8] group-hover:text-[#29C5D9]" />
            {!collapsed && (
              <span className="flex-1 truncate tracking-tight">{item.label}</span>
            )}
            {!collapsed && item.badge && (
              <span className="px-1.5 py-0.5 text-[10px] font-bold uppercase rounded bg-[#3978F6]/20 text-[#29C5D9] border border-[#3978F6]/30">
                {item.badge}
              </span>
            )}
          </NavLink>
        ))}
      </nav>

      {/* Sidebar Footer */}
      <div className="p-3 border-t border-[#25344A]">
        {!collapsed ? (
          <div className="p-3 rounded-lg bg-[#101A2B] border border-[#25344A]">
            <div className="flex items-center justify-between text-xs mb-1">
              <span className="text-[#71819A]">Environment</span>
              <span className="font-bold text-[#27C58B]">SIMULATED DEMO</span>
            </div>
            <p className="text-[10px] text-[#71819A] leading-tight">
              {isCustomer ? 'Demo balances and transfers are simulated for testing.' : 'Compliance & Anti-Financial Crime Platform'}
            </p>
          </div>
        ) : (
          <div className="flex justify-center" title="Simulated Demo Platform">
            <div className="h-2 w-2 rounded-full bg-[#27C58B] animate-pulse" />
          </div>
        )}
      </div>
    </aside>
  );
};
