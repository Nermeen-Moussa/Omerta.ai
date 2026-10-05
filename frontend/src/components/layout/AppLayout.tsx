import React, { useState, useEffect } from 'react';
import { Outlet, useNavigate } from 'react-router-dom';
import { Sidebar } from './Sidebar';
import { Header } from './Header';
import { Search, ArrowRight, ShieldAlert, Users, Wallet, Smartphone } from 'lucide-react';
import { Modal } from '../common/Modal';

export const AppLayout: React.FC = () => {
  const [collapsed, setCollapsed] = useState(false);
  const [searchOpen, setSearchOpen] = useState(false);
  const [searchQuery, setSearchQuery] = useState('');
  const navigate = useNavigate();

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

        <main className="flex-1 mt-16 p-6 md:p-8 max-w-7xl w-full mx-auto space-y-6">
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
    </div>
  );
};
