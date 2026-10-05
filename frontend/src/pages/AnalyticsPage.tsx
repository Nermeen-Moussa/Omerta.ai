import React, { useEffect, useState } from 'react';
import { api } from '../api/client';
import { StatCard } from '../components/common/StatCard';
import {
  TrendingUp,
  Activity,
  ShieldAlert,
  Globe2,
  Cpu,
  BarChart2,
  RefreshCw,
  PieChart as PieIcon,
  Zap,
} from 'lucide-react';
import {
  AreaChart,
  Area,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  PieChart,
  Pie,
  Cell,
  RadarChart,
  PolarGrid,
  PolarAngleAxis,
  PolarRadiusAxis,
  Radar,
} from 'recharts';

const COLORS = ['#00d2ff', '#10b981', '#f59e0b', '#ef4444', '#8b5cf6', '#ec4899'];

const TYPOLOGY_DATA = [
  { typology: 'Multiple Accounts on Single Device', risk_weight: 85, occurrences: 42 },
  { typology: 'Suspected Commercial VPN / Proxy', risk_weight: 65, occurrences: 68 },
  { typology: 'Virtualized Environment / Emulator', risk_weight: 90, occurrences: 29 },
  { typology: 'Account Takeover / New Device Pattern', risk_weight: 78, occurrences: 35 },
  { typology: 'Rapid Mule Pass-Through Transfer', risk_weight: 95, occurrences: 18 },
  { typology: 'Unusual Volume Deviation (> 5x Avg)', risk_weight: 60, occurrences: 84 },
];

const CURRENCY_DATA = [
  { name: 'EGP (Egyptian Pound)', value: 68, amount: '$42.1M Eq.' },
  { name: 'USD (US Dollar)', value: 18, amount: '$11.2M' },
  { name: 'EUR (Euro)', value: 9, amount: '$5.6M' },
  { name: 'GBP (British Pound)', value: 5, amount: '$3.1M' },
];

export const AnalyticsPage: React.FC = () => {
  const [charts, setCharts] = useState<any>(null);
  const [loading, setLoading] = useState<boolean>(true);

  useEffect(() => {
    loadAnalytics();
  }, []);

  const loadAnalytics = async () => {
    setLoading(true);
    try {
      const data = await api.getDashboardCharts();
      setCharts(data);
    } catch (err: any) {
      console.error('Failed to load analytics charts', err);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="space-y-6 animate-in fade-in duration-200">
      {/* Top Banner */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 omerta-card p-6 border-slate-200 dark:border-slate-800 shadow-md">
        <div className="flex items-center gap-4">
          <div className="w-12 h-12 rounded-xl bg-indigo-50 dark:bg-indigo-500/10 border border-indigo-200 dark:border-indigo-500/30 flex items-center justify-center text-indigo-600 dark:text-indigo-400 shadow-xs">
            <TrendingUp className="w-6 h-6" />
          </div>
          <div>
            <h1 className="text-2xl font-bold text-slate-900 dark:text-white tracking-tight flex items-center gap-2">
              Advanced Risk & Fraud Analytics
              <span className="text-xs px-2.5 py-0.5 rounded-full bg-indigo-50 dark:bg-indigo-500/10 text-indigo-700 dark:text-indigo-300 border border-indigo-200 dark:border-indigo-500/20 font-bold">
                Real-Time ML Insights
              </span>
            </h1>
            <p className="text-xs text-slate-500 dark:text-slate-400 mt-1">
              Cross-entity statistical distributions, typology concentrations, and currency volatility monitoring.
            </p>
          </div>
        </div>
        <button
          onClick={loadAnalytics}
          disabled={loading}
          className="px-3.5 py-2 rounded-xl bg-white dark:bg-slate-800 hover:bg-slate-50 dark:hover:bg-slate-700 text-slate-700 dark:text-slate-200 border border-slate-300 dark:border-slate-700 text-xs font-semibold flex items-center gap-2 transition-colors disabled:opacity-50 shadow-xs"
        >
          <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin text-sky-500 dark:text-cyan-400' : ''}`} />
          Refresh Charts
        </button>
      </div>

      {/* KPI Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <StatCard
          title="Active Fraud Typologies"
          value="6 Active"
          icon={<ShieldAlert className="w-5 h-5" />}
          description="Monitored in synthetic baseline"
          variant="alert"
        />
        <StatCard
          title="Top Anomaly Scenario"
          value="Mule Pass-Through"
          icon={<Zap className="w-5 h-5" />}
          description="95% Risk severity rating"
          variant="alert"
        />
        <StatCard
          title="Dominant Jurisdiction"
          value="Egypt (EGP)"
          icon={<Globe2 className="w-5 h-5" />}
          description="68% of monitored traffic"
          variant="cyan"
        />
        <StatCard
          title="Avg Neural Detection Lag"
          value="< 18ms"
          icon={<Cpu className="w-5 h-5" />}
          description="Parallel analyzer pipeline"
          variant="emerald"
        />
      </div>

      {/* Main Charts Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Transaction Volume Timeline */}
        <div className="omerta-card p-6 shadow-md">
          <div className="flex items-center justify-between mb-4 pb-2 border-b border-slate-200 dark:border-slate-800">
            <h2 className="text-sm font-bold text-slate-900 dark:text-white flex items-center gap-2">
              <Activity className="w-4 h-4 text-sky-600 dark:text-cyan-400" />
              Hourly Transaction Volume (EGP Eq.)
            </h2>
            <span className="text-xs text-slate-500 dark:text-slate-400 font-mono">Past 24 Hours</span>
          </div>
          <div className="h-72">
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={charts?.volume_over_time || []}>
                <defs>
                  <linearGradient id="volColor" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="#00d2ff" stopOpacity={0.4} />
                    <stop offset="95%" stopColor="#00d2ff" stopOpacity={0.0} />
                  </linearGradient>
                </defs>
                <CartesianGrid strokeDasharray="3 3" stroke="#cbd5e1" opacity={0.3} />
                <XAxis dataKey="timestamp" stroke="#64748b" tick={{ fontSize: 11 }} />
                <YAxis stroke="#64748b" tick={{ fontSize: 11 }} tickFormatter={(v) => `$${(v / 1000).toFixed(0)}k`} />
                <Tooltip
                  contentStyle={{ backgroundColor: '#0f172a', borderColor: '#334155', borderRadius: '8px', color: '#ffffff' }}
                  formatter={(v: any) => [`$${Number(v).toLocaleString()}`, 'Volume']}
                />
                <Area type="monotone" dataKey="volume" stroke="#0284c7" strokeWidth={2} fillOpacity={1} fill="url(#volColor)" />
              </AreaChart>
            </ResponsiveContainer>
          </div>
        </div>

        {/* Typology Radar Analysis */}
        <div className="omerta-card p-6 shadow-md">
          <div className="flex items-center justify-between mb-4 pb-2 border-b border-slate-200 dark:border-slate-800">
            <h2 className="text-sm font-bold text-slate-900 dark:text-white flex items-center gap-2">
              <ShieldAlert className="w-4 h-4 text-amber-600 dark:text-amber-400" />
              Financial Crime Typology Risk Weights
            </h2>
            <span className="text-xs font-bold text-amber-700 dark:text-amber-400">Scenario Matrix</span>
          </div>
          <div className="h-72">
            <ResponsiveContainer width="100%" height="100%">
              <RadarChart data={TYPOLOGY_DATA}>
                <PolarGrid stroke="#94a3b8" opacity={0.3} />
                <PolarAngleAxis dataKey="typology" stroke="#64748b" tick={{ fontSize: 9 }} />
                <PolarRadiusAxis stroke="#64748b" angle={30} domain={[0, 100]} />
                <Radar name="Risk Weight" dataKey="risk_weight" stroke="#ea580c" fill="#f59e0b" fillOpacity={0.4} />
                <Tooltip contentStyle={{ backgroundColor: '#0f172a', borderColor: '#334155', borderRadius: '8px', color: '#ffffff' }} />
              </RadarChart>
            </ResponsiveContainer>
          </div>
        </div>

        {/* Currency Distribution Breakdown */}
        <div className="omerta-card p-6 shadow-md">
          <div className="flex items-center justify-between mb-4 pb-2 border-b border-slate-200 dark:border-slate-800">
            <h2 className="text-sm font-bold text-slate-900 dark:text-white flex items-center gap-2">
              <PieIcon className="w-4 h-4 text-emerald-600 dark:text-emerald-400" />
              Monitored Currency Portfolios
            </h2>
            <span className="text-xs text-slate-500 dark:text-slate-400 font-mono">FX Exposure</span>
          </div>
          <div className="h-72">
            <ResponsiveContainer width="100%" height="100%">
              <PieChart>
                <Pie
                  data={CURRENCY_DATA}
                  dataKey="value"
                  nameKey="name"
                  cx="50%"
                  cy="50%"
                  outerRadius={85}
                  innerRadius={50}
                  paddingAngle={4}
                  label={(entry: any) => `${(entry?.name || '').split(' ')[0]} ${((entry?.percent || 0) * 100).toFixed(0)}%`}
                >
                  {CURRENCY_DATA.map((_, index) => (
                    <Cell key={`cell-${index}`} fill={COLORS[index % COLORS.length]} />
                  ))}
                </Pie>
                <Tooltip
                  contentStyle={{ backgroundColor: '#0f172a', borderColor: '#334155', borderRadius: '8px', color: '#ffffff' }}
                  formatter={(v: any, name: any, item: any) => [`${v}% (${item.payload.amount})`, name]}
                />
              </PieChart>
            </ResponsiveContainer>
          </div>
        </div>

        {/* Risk Level Distribution Bars */}
        <div className="omerta-card p-6 shadow-md">
          <div className="flex items-center justify-between mb-4 pb-2 border-b border-slate-200 dark:border-slate-800">
            <h2 className="text-sm font-bold text-slate-900 dark:text-white flex items-center gap-2">
              <BarChart2 className="w-4 h-4 text-sky-600 dark:text-indigo-400" />
              Transactions by Severity Classification
            </h2>
            <span className="text-xs font-bold text-sky-700 dark:text-cyan-400">Review Rule: &gt;40%</span>
          </div>
          <div className="h-72">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={charts?.risk_distribution || []}>
                <CartesianGrid strokeDasharray="3 3" stroke="#cbd5e1" opacity={0.3} />
                <XAxis dataKey="risk_level" stroke="#64748b" tick={{ fontSize: 10 }} />
                <YAxis stroke="#64748b" tick={{ fontSize: 11 }} />
                <Tooltip contentStyle={{ backgroundColor: '#0f172a', borderColor: '#334155', borderRadius: '8px', color: '#ffffff' }} />
                <Bar dataKey="count" radius={[4, 4, 0, 0]}>
                  {(charts?.risk_distribution || []).map((entry: any, index: number) => {
                    const color =
                      entry.risk_level === 'CRITICAL'
                        ? '#dc2626'
                        : entry.risk_level === 'HIGH'
                        ? '#ea580c'
                        : entry.risk_level === 'REQUIRES_REVIEW'
                        ? '#d97706'
                        : entry.risk_level === 'MODERATE'
                        ? '#0284c7'
                        : '#059669';
                    return <Cell key={`bar-${index}`} fill={color} />;
                  })}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>
      </div>
    </div>
  );
};
