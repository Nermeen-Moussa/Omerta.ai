import React, { useEffect, useState } from 'react';
import {
  Smartphone,
  Search,
  RefreshCw,
  ChevronLeft,
  ChevronRight,
  AlertTriangle,
  CheckCircle,
} from 'lucide-react';
import { api } from '../api/client';
import type { DeviceItem } from '../types';
import { RiskBadge } from '../components/common/RiskBadge';
import { Modal } from '../components/common/Modal';

export const DevicesPage: React.FC = () => {
  const [devices, setDevices] = useState<DeviceItem[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState('');
  const [typeFilter, setTypeFilter] = useState('');
  const [platformFilter, setPlatformFilter] = useState('');
  const [page, setPage] = useState(1);

  // Device detail modal state
  const [selectedDevice, setSelectedDevice] = useState<any | null>(null);

  const fetchDevices = async () => {
    setLoading(true);
    try {
      const res = await api.getDevices({
        search,
        device_type: typeFilter,
        platform: platformFilter,
        page,
        page_size: 20,
      });
      setDevices(res.items || []);
      setTotal(res.total || 0);
    } catch (err) {
      console.error('Failed to load devices', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchDevices();
  }, [page, typeFilter, platformFilter]);

  const handleSearchSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    setPage(1);
    fetchDevices();
  };

  const handleOpenDetail = async (d: DeviceItem) => {
    try {
      const res = await api.getDeviceDetail(d.external_id);
      setSelectedDevice(res);
    } catch (err) {
      console.error('Failed to load device detail', err);
    }
  };

  return (
    <div className="space-y-6 animate-in fade-in duration-200">
      {/* Page Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-slate-900 dark:text-white flex items-center gap-2">
            <Smartphone className="h-6 w-6 text-sky-600 dark:text-cyan-400" />
            Device Intelligence & Fingerprinting
          </h1>
          <p className="text-xs text-slate-500 dark:text-slate-400 mt-1">
            Detect virtualized emulator environments, rooted Android clients, and multi-account hardware sharing.
          </p>
        </div>

        <div className="flex items-center gap-2.5">
          <span className="px-3 py-1.5 rounded-lg bg-sky-50 dark:bg-slate-900 text-sky-800 dark:text-cyan-300 font-mono text-xs font-bold border border-sky-300 dark:border-slate-700 shadow-xs">
            {total} Devices
          </span>
          <button
            onClick={fetchDevices}
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
            placeholder="Search by Device ID, platform, or user agent..."
            className="w-full pl-10 pr-4 py-2 bg-slate-50 dark:bg-slate-900 border border-slate-300 dark:border-slate-700 rounded-lg text-sm text-slate-900 dark:text-white placeholder-slate-400 dark:placeholder-slate-500 focus:outline-none focus:border-sky-500 dark:focus:border-cyan-400"
          />
        </form>

        <div className="flex items-center gap-2 w-full sm:w-auto">
          <select
            value={typeFilter}
            onChange={(e) => {
              setTypeFilter(e.target.value);
              setPage(1);
            }}
            className="px-3 py-2 bg-slate-50 dark:bg-slate-900 border border-slate-300 dark:border-slate-700 rounded-lg text-xs font-medium text-slate-700 dark:text-slate-200 focus:outline-none focus:border-sky-500 dark:focus:border-cyan-400"
          >
            <option value="">All Device Types</option>
            <option value="MOBILE">Mobile</option>
            <option value="DESKTOP">Desktop</option>
            <option value="TABLET">Tablet</option>
          </select>

          <select
            value={platformFilter}
            onChange={(e) => {
              setPlatformFilter(e.target.value);
              setPage(1);
            }}
            className="px-3 py-2 bg-slate-50 dark:bg-slate-900 border border-slate-300 dark:border-slate-700 rounded-lg text-xs font-medium text-slate-700 dark:text-slate-200 focus:outline-none focus:border-sky-500 dark:focus:border-cyan-400"
          >
            <option value="">All Platforms</option>
            <option value="Android">Android</option>
            <option value="iOS">iOS</option>
            <option value="Windows">Windows</option>
            <option value="macOS">macOS</option>
          </select>
        </div>
      </div>

      {/* Devices Table */}
      <div className="omerta-card overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs">
            <thead className="bg-slate-100 dark:bg-slate-900/90 text-slate-700 dark:text-slate-400 border-b border-slate-200 dark:border-slate-800 uppercase text-[10px] tracking-wider font-bold">
              <tr>
                <th className="py-3.5 px-4">Device ID</th>
                <th className="py-3.5 px-4">Type</th>
                <th className="py-3.5 px-4">Platform</th>
                <th className="py-3.5 px-4">Emulator / Root Risk</th>
                <th className="py-3.5 px-4">Sessions</th>
                <th className="py-3.5 px-4">Risk Rating</th>
                <th className="py-3.5 px-4">First Observed</th>
                <th className="py-3.5 px-4 text-right">Action</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-200 dark:divide-slate-800/60 text-slate-800 dark:text-slate-300">
              {loading ? (
                <tr>
                  <td colSpan={8} className="py-12 text-center text-slate-500 dark:text-slate-400">
                    <RefreshCw className="h-6 w-6 animate-spin mx-auto mb-2 text-sky-500 dark:text-cyan-400" />
                    <span>Loading devices...</span>
                  </td>
                </tr>
              ) : devices.length === 0 ? (
                <tr>
                  <td colSpan={8} className="py-12 text-center text-slate-500 dark:text-slate-400">
                    No devices match the selected filters.
                  </td>
                </tr>
              ) : (
                devices.map((d) => (
                  <tr
                    key={d.id}
                    onClick={() => handleOpenDetail(d)}
                    className="hover:bg-slate-50 dark:hover:bg-slate-800/50 cursor-pointer transition-colors group"
                  >
                    <td className="py-3 px-4 font-mono font-bold text-sky-700 dark:text-cyan-300 group-hover:underline">
                      {d.external_id}
                    </td>
                    <td className="py-3 px-4">
                      <span className="px-2 py-0.5 rounded bg-slate-100 dark:bg-slate-800 text-[10px] font-semibold text-slate-800 dark:text-slate-300 border border-slate-300 dark:border-slate-700">
                        {d.device_type}
                      </span>
                    </td>
                    <td className="py-3 px-4 font-medium text-slate-900 dark:text-white">{d.platform}</td>
                    <td className="py-3 px-4">
                      <div className="flex flex-col gap-1">
                        {d.account_count && d.account_count > 1 ? (
                          <span className="inline-flex items-center gap-1 text-amber-600 dark:text-amber-400 font-bold text-[11px] bg-amber-50 dark:bg-amber-950/40 px-2 py-0.5 rounded border border-amber-200 dark:border-amber-800/60 w-fit">
                            <AlertTriangle className="h-3 w-3 shrink-0" />
                            MULTI-ACCOUNT ({d.account_count} ACCOUNTS)
                          </span>
                        ) : null}
                        {d.is_emulator || d.is_rooted ? (
                          <span className="inline-flex items-center gap-1 text-rose-700 dark:text-rose-400 font-bold text-[11px]">
                            <AlertTriangle className="h-3.5 w-3.5 shrink-0" />
                            {d.is_emulator ? 'EMULATOR DETECTED' : 'ROOTED CLIENT'}
                          </span>
                        ) : (!d.account_count || d.account_count <= 1) ? (
                          <span className="inline-flex items-center gap-1 text-emerald-700 dark:text-emerald-400 font-semibold text-[11px]">
                            <CheckCircle className="h-3.5 w-3.5 shrink-0" />
                            Standard Hardware
                          </span>
                        ) : null}
                      </div>
                    </td>
                    <td className="py-3 px-4 font-mono font-bold text-sky-700 dark:text-cyan-300">{d.session_count} sessions</td>
                    <td className="py-3 px-4">
                      <RiskBadge level={d.risk_level || 'LOW'} size="sm" />
                    </td>
                    <td className="py-3 px-4 text-slate-600 dark:text-slate-400 whitespace-nowrap">
                      {d.first_seen_at || d.first_seen ? new Date(d.first_seen_at || d.first_seen!).toLocaleDateString() : 'N/A'}
                    </td>
                    <td className="py-3 px-4 text-right">
                      <button
                        onClick={(e) => {
                          e.stopPropagation();
                          handleOpenDetail(d);
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
          <span>Showing <strong className="text-slate-900 dark:text-white">{devices.length}</strong> of <strong className="text-slate-900 dark:text-white">{total}</strong> devices</span>
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
              disabled={devices.length < 20 || loading}
              onClick={() => setPage((p) => p + 1)}
              className="p-1.5 rounded-lg border border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-800 text-slate-700 dark:text-slate-300 disabled:opacity-40 hover:bg-slate-50 dark:hover:bg-slate-700 shadow-xs"
            >
              <ChevronRight className="h-4 w-4" />
            </button>
          </div>
        </div>
      </div>

      {/* Device Detail Modal */}
      <Modal
        isOpen={!!selectedDevice}
        onClose={() => setSelectedDevice(null)}
        title={`Device Hardware Dossier: ${selectedDevice?.device?.external_id}`}
        subtitle={`${selectedDevice?.device?.platform} • ${selectedDevice?.device?.device_type}`}
        maxWidth="2xl"
      >
        {selectedDevice && (
          <div className="space-y-5 text-xs">
            {/* Linked Accounts on this device */}
            <div>
              <h4 className="font-bold text-slate-700 dark:text-slate-300 uppercase tracking-wider text-[11px] mb-2">
                Accounts Observed on this Device ({selectedDevice.associated_accounts?.length || 0})
              </h4>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                {(selectedDevice.associated_accounts || []).map((acc: any) => (
                  <div key={acc.id} className="p-3 rounded-lg bg-slate-50 dark:bg-slate-900 border border-slate-200 dark:border-slate-800 space-y-1">
                    <span className="font-mono font-bold text-slate-900 dark:text-white">{acc.external_id}</span>
                    <p className="text-slate-600 dark:text-slate-400 font-medium">{acc.customer_name}</p>
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
