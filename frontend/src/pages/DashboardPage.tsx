import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  ArrowLeftRight,
  DollarSign,
  ShieldAlert,
  AlertTriangle,
  FolderSearch,
  Users,
  Wallet,
  Gauge,
  ArrowUpRight,
  TrendingUp,
  RefreshCw,
} from 'lucide-react';
import {
  ResponsiveContainer,
  AreaChart,
  Area,
  XAxis,
  YAxis,
  Tooltip,
  PieChart,
  Pie,
  Cell,
} from 'recharts';
import { api } from '../api/client';
import { StatCard } from '../components/common/StatCard';
import { RiskBadge } from '../components/common/RiskBadge';

export const DashboardPage: React.FC = () => {
  const [summary, setSummary] = useState<any>(null);
  const [charts, setCharts] = useState<any>(null);
  const [recent, setRecent] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const navigate = useNavigate();

  const loadDashboardData = async () => {
    setLoading(true);
    try {
      const [sumRes, chartRes, recRes] = await Promise.all([
        api.getDashboardSummary(),
        api.getDashboardCharts(),
        api.getRecentActivity(6),
      ]);
      setSummary(sumRes);
      setCharts(chartRes);
      setRecent(recRes);
    } catch (err) {
      console.error('Failed to load dashboard data', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadDashboardData();
  }, []);

  const RISK_COLORS: Record<string, string> = {
    LOW: '#10b981',
    MODERATE: '#f59e0b',
    REQUIRES_REVIEW: '#f97316',
    HIGH: '#ef4444',
    CRITICAL: '#dc2626',
  };

  return (
    <div className="space-y-6 animate-in fade-in duration-200">
      {/* Page Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-slate-900 dark:text-white flex items-center gap-2.5">
            Financial Crime Intelligence Dashboard
          </h1>
          <p className="text-xs text-slate-500 dark:text-slate-400 mt-1">
            Real-time transaction monitoring, multi-signal risk assessments, and human review queues.
          </p>
        </div>
        <div className="flex items-center gap-3">
          <button
            onClick={loadDashboardData}
            className="flex items-center gap-2 px-3 py-1.5 rounded-lg bg-white dark:bg-slate-900 border border-slate-300 dark:border-slate-700 text-xs font-semibold text-slate-700 dark:text-slate-200 hover:bg-slate-50 dark:hover:bg-slate-800 transition-colors shadow-sm"
          >
            <RefreshCw className={`h-3.5 w-3.5 ${loading ? 'animate-spin text-sky-500 dark:text-cyan-400' : ''}`} />
            <span>Refresh</span>
          </button>
          <button
            onClick={() => navigate('/risk-monitoring')}
            className="flex items-center gap-2 px-3.5 py-1.5 rounded-lg bg-gradient-to-r from-sky-500 to-cyan-500 text-slate-950 text-xs font-bold hover:brightness-110 transition-all shadow-md shadow-cyan-500/15"
          >
            <ShieldAlert className="h-4 w-4" />
            <span>Review Queue ({summary?.transactions_requiring_review ?? '…'})</span>
          </button>
        </div>
      </div>

      {/* 8 Primary KPI Summary Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <StatCard
          title="Total Transactions"
          value={summary ? summary.total_transactions.toLocaleString() : '10,000'}
          subtitle="Monitored in system of record"
          change="+14.2% vs last period"
          isPositive={true}
          icon={ArrowLeftRight}
          variant="cyan"
        />
        <StatCard
          title="Total Volume"
          value={
            summary
              ? `${(summary.total_volume / 1000000).toFixed(1)}M EGP`
              : '156.5M EGP'
          }
          subtitle="Cumulative gross volume"
          change="+8.6% throughput"
          isPositive={true}
          icon={DollarSign}
          variant="emerald"
        />
        <StatCard
          title="Requires Human Review"
          value={summary ? summary.transactions_requiring_review : '315'}
          subtitle="Strict rule: risk_score > 40%"
          change="Pending analyst review"
          isPositive={false}
          icon={ShieldAlert}
          variant="alert"
        />
        <StatCard
          title="High-Risk Transactions"
          value={summary ? summary.high_risk_transactions : '10'}
          subtitle="Score >= 70% or critical flags"
          change="Priority escalated"
          isPositive={false}
          icon={AlertTriangle}
          variant="alert"
        />
        <StatCard
          title="Open Investigations"
          value={summary ? summary.open_investigations : '67'}
          subtitle="Active analyst cases"
          change="Active compliance pipeline"
          isPositive={true}
          icon={FolderSearch}
          variant="default"
        />
        <StatCard
          title="Customers Monitored"
          value={summary ? summary.customers_monitored.toLocaleString() : '1,000'}
          subtitle="Individuals, SMEs & Corporates"
          change="Full KYC coverage"
          isPositive={true}
          icon={Users}
          variant="default"
        />
        <StatCard
          title="Accounts Monitored"
          value={summary ? summary.accounts_monitored.toLocaleString() : '1,515'}
          subtitle="Active multi-currency accounts"
          change="EGP, USD, EUR, GBP"
          isPositive={true}
          icon={Wallet}
          variant="default"
        />
        <StatCard
          title="Average Risk Score"
          value={summary ? `${summary.average_risk_score.toFixed(1)}%` : '13.2%'}
          subtitle="Baseline platform risk profile"
          change="Low baseline variance"
          isPositive={true}
          icon={Gauge}
          variant="cyan"
        />
      </div>

      {/* Primary Visualizations Row */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Transaction Volume Timeseries (2 cols) */}
        <div className="lg:col-span-2 omerta-card p-6 flex flex-col justify-between">
          <div className="flex items-center justify-between pb-4 border-b border-slate-200 dark:border-slate-800">
            <div>
              <h2 className="text-base font-bold text-slate-900 dark:text-white tracking-tight flex items-center gap-2">
                <TrendingUp className="h-4 w-4 text-sky-600 dark:text-cyan-400" />
                Transaction Volume & Review Activity Over Time
              </h2>
              <p className="text-xs text-slate-500 dark:text-slate-400">
                Daily transaction gross volume with corresponding flagged human reviews
              </p>
            </div>
            <span className="px-2.5 py-1 rounded-md bg-slate-100 dark:bg-slate-800 text-[11px] font-mono font-semibold text-sky-700 dark:text-cyan-300 border border-slate-300 dark:border-slate-700">
              15-Day Window
            </span>
          </div>

          <div className="h-72 w-full mt-4">
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={charts?.volume_trend || []}>
                <defs>
                  <linearGradient id="volGradient" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="#00d2ff" stopOpacity={0.4} />
                    <stop offset="95%" stopColor="#00d2ff" stopOpacity={0.0} />
                  </linearGradient>
                  <linearGradient id="reviewGradient" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="#f59e0b" stopOpacity={0.4} />
                    <stop offset="95%" stopColor="#f59e0b" stopOpacity={0.0} />
                  </linearGradient>
                </defs>
                <XAxis dataKey="date" stroke="#64748b" fontSize={11} tickLine={false} />
                <YAxis stroke="#64748b" fontSize={11} tickLine={false} />
                <Tooltip
                  contentStyle={{
                    backgroundColor: '#0f172a',
                    borderColor: '#334155',
                    borderRadius: '8px',
                    fontSize: '12px',
                    color: '#ffffff',
                  }}
                />
                <Area
                  type="monotone"
                  dataKey="volume"
                  name="Volume (EGP)"
                  stroke="#0284c7"
                  strokeWidth={2}
                  fillOpacity={1}
                  fill="url(#volGradient)"
                />
                <Area
                  type="monotone"
                  dataKey="reviews"
                  name="Flagged Reviews"
                  stroke="#ea580c"
                  strokeWidth={2}
                  fillOpacity={1}
                  fill="url(#reviewGradient)"
                />
              </AreaChart>
            </ResponsiveContainer>
          </div>
        </div>

        {/* Risk Level Distribution Donut (1 col) */}
        <div className="omerta-card p-6 flex flex-col justify-between">
          <div className="pb-4 border-b border-slate-200 dark:border-slate-800">
            <h2 className="text-base font-bold text-slate-900 dark:text-white tracking-tight">
              Risk Level Breakdown
            </h2>
            <p className="text-xs text-slate-500 dark:text-slate-400">Total population across severity tiers</p>
          </div>

          <div className="h-56 w-full mt-2">
            <ResponsiveContainer width="100%" height="100%">
              <PieChart>
                <Pie
                  data={charts?.risk_distribution || []}
                  dataKey="count"
                  nameKey="level"
                  cx="50%"
                  cy="50%"
                  innerRadius={55}
                  outerRadius={80}
                  paddingAngle={3}
                >
                  {(charts?.risk_distribution || []).map((entry: any) => (
                    <Cell
                      key={entry.level}
                      fill={RISK_COLORS[entry.level] || '#38bdf8'}
                      stroke="#ffffff"
                      strokeWidth={1.5}
                    />
                  ))}
                </Pie>
                <Tooltip
                  contentStyle={{
                    backgroundColor: '#0f172a',
                    borderColor: '#334155',
                    borderRadius: '8px',
                    fontSize: '12px',
                    color: '#ffffff',
                  }}
                />
              </PieChart>
            </ResponsiveContainer>
          </div>

          {/* Legend */}
          <div className="grid grid-cols-2 gap-2 text-xs pt-2 border-t border-slate-200 dark:border-slate-800/80">
            {(charts?.risk_distribution || []).map((item: any) => (
              <div key={item.level} className="flex items-center gap-2">
                <span
                  className="h-2 w-2 rounded-full"
                  style={{ backgroundColor: RISK_COLORS[item.level] || '#38bdf8' }}
                />
                <span className="truncate text-slate-600 dark:text-slate-400 font-medium">{item.level}:</span>
                <span className="font-bold text-slate-900 dark:text-white font-mono">{item.count}</span>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* Secondary Analytics Row: Top Risk Signals & Recent Flagged Activity */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Top Detected Risk Signals */}
        <div className="omerta-card p-6">
          <div className="flex items-center justify-between pb-4 border-b border-slate-200 dark:border-slate-800">
            <div>
              <h2 className="text-base font-bold text-slate-900 dark:text-white tracking-tight">
                Top Detected Risk Signals
              </h2>
              <p className="text-xs text-slate-500 dark:text-slate-400">Most frequent behavioral & structural triggers</p>
            </div>
            <button
              onClick={() => navigate('/analytics')}
              className="text-xs text-sky-600 dark:text-cyan-400 hover:text-sky-700 dark:hover:text-cyan-300 flex items-center gap-1 font-bold"
            >
              <span>View details</span>
              <ArrowUpRight className="h-3.5 w-3.5" />
            </button>
          </div>

          <div className="mt-4 space-y-3">
            {(charts?.top_risk_signals || []).map((sig: any, idx: number) => (
              <div
                key={idx}
                className="flex items-center justify-between p-3 rounded-lg bg-slate-50 dark:bg-slate-900/60 border border-slate-200 dark:border-slate-800/80 hover:border-slate-300 dark:hover:border-slate-700 transition-colors"
              >
                <div className="flex items-center gap-3">
                  <div className="text-xs font-mono font-bold text-slate-500 dark:text-slate-400 w-4">
                    #{idx + 1}
                  </div>
                  <div>
                    <p className="text-xs font-bold text-slate-900 dark:text-white">{sig.signal}</p>
                    <p className="text-[11px] text-slate-500 dark:text-slate-400 font-medium">Severity: {sig.severity}</p>
                  </div>
                </div>
                <div className="text-right">
                  <span className="px-2.5 py-0.5 rounded-full text-xs font-mono font-bold bg-sky-100 dark:bg-sky-500/10 text-sky-800 dark:text-cyan-300 border border-sky-300 dark:border-sky-500/20">
                    {sig.count} detections
                  </span>
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Priority Review Alerts Stream */}
        <div className="omerta-card p-6">
          <div className="flex items-center justify-between pb-4 border-b border-slate-200 dark:border-slate-800">
            <div>
              <h2 className="text-base font-bold text-slate-900 dark:text-white tracking-tight">
                Priority Review Stream
              </h2>
              <p className="text-xs text-slate-500 dark:text-slate-400">High-severity alerts awaiting compliance review</p>
            </div>
            <button
              onClick={() => navigate('/risk-monitoring')}
              className="text-xs text-amber-600 dark:text-amber-400 hover:text-amber-700 dark:hover:text-amber-300 flex items-center gap-1 font-bold"
            >
              <span>Go to review queue</span>
              <ArrowUpRight className="h-3.5 w-3.5" />
            </button>
          </div>

          <div className="mt-4 space-y-3">
            {(recent?.priority_alerts || []).map((al: any) => (
              <div
                key={al.id}
                onClick={() => navigate(`/transactions/${al.transaction_id}`)}
                className="flex items-center justify-between p-3 rounded-lg bg-slate-50 dark:bg-slate-900/60 border border-slate-200 dark:border-slate-800/80 hover:border-amber-400 dark:hover:border-amber-500/40 hover:bg-amber-50/40 dark:hover:bg-slate-800 cursor-pointer transition-all"
              >
                <div className="space-y-1">
                  <div className="flex items-center gap-2">
                    <span className="text-xs font-bold text-slate-900 dark:text-white font-mono">
                      {al.external_id}
                    </span>
                    <RiskBadge level={al.risk_level} score={al.risk_score} size="sm" />
                  </div>
                  <p className="text-[11px] text-slate-500 dark:text-slate-400 font-medium">
                    Type: {al.alert_type.replace(/_/g, ' ')}
                  </p>
                </div>
                <div className="text-right">
                  <span className="text-xs font-bold text-sky-600 dark:text-cyan-400 flex items-center gap-1">
                    Investigate <ArrowUpRight className="h-3.5 w-3.5" />
                  </span>
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
};
