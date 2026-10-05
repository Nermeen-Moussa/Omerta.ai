import React, { useEffect, useState } from 'react';
import { api } from '../api/client';
import { useAuth } from '../context/AuthContext';
import { useTheme, type ThemeMode } from '../context/ThemeContext';
import {
  Sliders,
  Server,
  Database,
  CheckCircle2,
  AlertTriangle,
  RefreshCw,
  Save,
  ShieldCheck,
  Bot,
  Network,
  FileCode,
  Sun,
  Moon,
  Monitor,
  Palette,
} from 'lucide-react';

export const SettingsPage: React.FC = () => {
  const { user } = useAuth();
  const { theme, setTheme } = useTheme();
  const [settingsData, setSettingsData] = useState<any>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [saving, setSaving] = useState<boolean>(false);
  const [saveSuccess, setSaveSuccess] = useState<string | null>(null);
  const [saveError, setSaveError] = useState<string | null>(null);

  // Form State
  const [humanReviewThreshold, setHumanReviewThreshold] = useState<number>(40.0);
  const [highRiskThreshold, setHighRiskThreshold] = useState<number>(70.0);
  const [criticalRiskThreshold, setCriticalRiskThreshold] = useState<number>(90.0);

  useEffect(() => {
    loadSettings();
  }, []);

  const loadSettings = async () => {
    setLoading(true);
    try {
      const data = await api.getSettings();
      setSettingsData(data);
      if (data.thresholds) {
        setHumanReviewThreshold(data.thresholds.human_review_threshold || 40.0);
        setHighRiskThreshold(data.thresholds.high_risk_threshold || 70.0);
        setCriticalRiskThreshold(data.thresholds.critical_risk_threshold || 90.0);
      }
    } catch (err: any) {
      console.error('Failed to load system settings', err);
    } finally {
      setLoading(false);
    }
  };

  const handleSaveThresholds = async (e: React.FormEvent) => {
    e.preventDefault();
    setSaving(true);
    setSaveSuccess(null);
    setSaveError(null);
    try {
      await api.updateThresholds({
        human_review_threshold: Number(humanReviewThreshold),
        high_risk_threshold: Number(highRiskThreshold),
        critical_risk_threshold: Number(criticalRiskThreshold),
      });
      setSaveSuccess('Risk scoring thresholds updated successfully across all monitoring nodes.');
      loadSettings();
    } catch (err: any) {
      setSaveError(err.message || 'Failed to update thresholds. Requires Administrator role.');
    } finally {
      setSaving(false);
    }
  };

  const isAdministrator = user?.role === 'ADMINISTRATOR';

  const themeOptions: Array<{ mode: ThemeMode; title: string; desc: string; icon: any }> = [
    {
      mode: 'dark',
      title: 'Midnight Dark (Default)',
      desc: 'High-contrast navy surfaces with electric cyan accents, designed for night operations.',
      icon: Moon,
    },
    {
      mode: 'light',
      title: 'Fintech Light',
      desc: 'Clean, crisp white and slate layout with refined contrast for daylight compliance work.',
      icon: Sun,
    },
    {
      mode: 'system',
      title: 'System Automatic',
      desc: 'Synchronizes dynamically with your operating system light / dark preferences.',
      icon: Monitor,
    },
  ];

  return (
    <div className="space-y-6 animate-in fade-in duration-200">
      {/* Top Banner */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 omerta-card p-6 border-slate-200 dark:border-slate-800 shadow-md">
        <div className="flex items-center gap-4">
          <div className="w-12 h-12 rounded-xl bg-sky-50 dark:bg-cyan-500/10 border border-sky-200 dark:border-cyan-500/30 flex items-center justify-center text-sky-600 dark:text-cyan-400 shadow-xs">
            <Sliders className="w-6 h-6" />
          </div>
          <div>
            <h1 className="text-2xl font-bold text-slate-900 dark:text-white tracking-tight flex items-center gap-2">
              System Settings & Platform Preferences
              <span className="text-xs px-2.5 py-0.5 rounded-full bg-sky-50 dark:bg-cyan-500/10 text-sky-700 dark:text-cyan-300 border border-sky-300 dark:border-cyan-500/30 font-bold">
                Production Core
              </span>
            </h1>
            <p className="text-xs text-slate-500 dark:text-slate-400 mt-1">
              Configure visual appearance, risk scoring thresholds, and inspect subsystem integration readiness.
            </p>
          </div>
        </div>
        <button
          onClick={loadSettings}
          disabled={loading}
          className="px-3.5 py-2 rounded-xl bg-white dark:bg-slate-800 hover:bg-slate-50 dark:hover:bg-slate-700 text-slate-700 dark:text-slate-200 border border-slate-300 dark:border-slate-700 text-xs font-semibold flex items-center gap-2 transition-colors disabled:opacity-50 shadow-xs"
        >
          <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin text-sky-500 dark:text-cyan-400' : ''}`} />
          Refresh Diagnostics
        </button>
      </div>

      {/* Visual Theme Appearance Preference Card */}
      <div className="omerta-card p-6 shadow-md">
        <h2 className="text-base font-bold text-slate-900 dark:text-white mb-2 flex items-center gap-2">
          <Palette className="w-5 h-5 text-sky-600 dark:text-cyan-400" />
          Analyst Workspace Theme & Appearance
        </h2>
        <p className="text-xs text-slate-500 dark:text-slate-400 mb-5">
          Select your preferred workspace theme. Switch seamlessly between dark mode and light mode.
        </p>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          {themeOptions.map((opt) => {
            const Icon = opt.icon;
            const isSelected = theme === opt.mode;
            return (
              <button
                key={opt.mode}
                type="button"
                onClick={() => setTheme(opt.mode)}
                className={`text-left p-4 rounded-xl border transition-all duration-200 flex flex-col justify-between ${
                  isSelected
                    ? 'border-sky-500 dark:border-cyan-400 bg-sky-50 dark:bg-sky-500/15 shadow-md shadow-sky-500/10 ring-2 ring-sky-500 dark:ring-cyan-400'
                    : 'border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900/60 hover:border-slate-300 dark:hover:border-slate-700 hover:bg-slate-50 dark:hover:bg-slate-800/40'
                }`}
              >
                <div>
                  <div className="flex items-center justify-between mb-2">
                    <div
                      className={`p-2 rounded-lg border ${
                        isSelected
                          ? 'bg-sky-600 dark:bg-cyan-500 text-white dark:text-slate-950 border-sky-600 dark:border-cyan-400'
                          : 'bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-slate-400 border-slate-200 dark:border-slate-700'
                      }`}
                    >
                      <Icon className="w-4 h-4" />
                    </div>
                    {isSelected && (
                      <span className="text-[10px] font-bold uppercase tracking-wider px-2 py-0.5 rounded-full bg-sky-600 dark:bg-cyan-400 text-white dark:text-slate-950">
                        Active
                      </span>
                    )}
                  </div>
                  <div className="text-sm font-bold text-slate-900 dark:text-white mb-1">{opt.title}</div>
                  <div className="text-xs text-slate-600 dark:text-slate-400 leading-relaxed font-normal">{opt.desc}</div>
                </div>
              </button>
            );
          })}
        </div>
      </div>

      {/* Subsystem Readiness Matrix */}
      <div className="omerta-card p-6 shadow-md">
        <h2 className="text-base font-bold text-slate-900 dark:text-white mb-4 flex items-center gap-2">
          <Server className="w-5 h-5 text-sky-600 dark:text-cyan-400" />
          Subsystem Health & Interface Readiness
        </h2>

        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
          {/* PostgreSQL */}
          <div className="p-4 rounded-xl bg-slate-50 dark:bg-slate-950/70 border border-slate-200 dark:border-slate-800 flex items-start gap-3">
            <div className="p-2.5 rounded-lg bg-emerald-50 dark:bg-emerald-500/10 text-emerald-700 dark:text-emerald-400 border border-emerald-200 dark:border-emerald-500/20">
              <Database className="w-5 h-5" />
            </div>
            <div>
              <div className="text-[10px] font-bold text-slate-500 dark:text-slate-400 uppercase tracking-wider">Primary Database</div>
              <div className="text-sm font-bold text-slate-900 dark:text-white mt-0.5">PostgreSQL 17</div>
              <div className="flex items-center gap-1.5 mt-2">
                <span className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse" />
                <span className="text-xs font-mono font-bold text-emerald-700 dark:text-emerald-400">
                  {settingsData?.system_status?.postgres === 'ok' ? 'HEALTHY (Port 15432)' : 'DISCONNECTED'}
                </span>
              </div>
            </div>
          </div>

          {/* Neo4j */}
          <div className="p-4 rounded-xl bg-slate-50 dark:bg-slate-950/70 border border-slate-200 dark:border-slate-800 flex items-start gap-3">
            <div className="p-2.5 rounded-lg bg-sky-50 dark:bg-cyan-500/10 text-sky-700 dark:text-cyan-400 border border-sky-200 dark:border-cyan-500/20">
              <Network className="w-5 h-5" />
            </div>
            <div>
              <div className="text-[10px] font-bold text-slate-500 dark:text-slate-400 uppercase tracking-wider">Graph Knowledge Engine</div>
              <div className="text-sm font-bold text-slate-900 dark:text-white mt-0.5">Neo4j 5 Enterprise</div>
              <div className="flex items-center gap-1.5 mt-2">
                <span className="w-2 h-2 rounded-full bg-sky-500 dark:bg-cyan-400" />
                <span className="text-xs font-mono font-bold text-sky-700 dark:text-cyan-400">
                  {settingsData?.system_status?.neo4j === 'ok' ? 'CONNECTED (Bolt 17687)' : 'MOCK READY'}
                </span>
              </div>
            </div>
          </div>

          {/* LLM Engine */}
          <div className="p-4 rounded-xl bg-slate-50 dark:bg-slate-950/70 border border-slate-200 dark:border-slate-800 flex items-start gap-3">
            <div className="p-2.5 rounded-lg bg-indigo-50 dark:bg-indigo-500/10 text-indigo-700 dark:text-indigo-400 border border-indigo-200 dark:border-indigo-500/20">
              <Bot className="w-5 h-5" />
            </div>
            <div>
              <div className="text-[10px] font-bold text-slate-500 dark:text-slate-400 uppercase tracking-wider">LLM Provider</div>
              <div className="text-sm font-bold text-slate-900 dark:text-white mt-0.5">Groq Cloud AI</div>
              <div className="flex items-center gap-1.5 mt-2">
                <span className="w-2 h-2 rounded-full bg-indigo-500 dark:bg-indigo-400" />
                <span className="text-xs font-mono font-bold text-indigo-700 dark:text-indigo-400">
                  {settingsData?.system_status?.llm_model || 'llama-3.3-70b'}
                </span>
              </div>
            </div>
          </div>

          {/* MCP Tool Registry */}
          <div className="p-4 rounded-xl bg-slate-50 dark:bg-slate-950/70 border border-slate-200 dark:border-slate-800 flex items-start gap-3">
            <div className="p-2.5 rounded-lg bg-amber-50 dark:bg-amber-500/10 text-amber-700 dark:text-amber-400 border border-amber-200 dark:border-amber-500/20">
              <FileCode className="w-5 h-5" />
            </div>
            <div>
              <div className="text-[10px] font-bold text-slate-500 dark:text-slate-400 uppercase tracking-wider">MCP Tool Protocols</div>
              <div className="text-sm font-bold text-slate-900 dark:text-white mt-0.5">4 Tools Registered</div>
              <div className="flex items-center gap-1.5 mt-2">
                <span className="w-2 h-2 rounded-full bg-amber-500 dark:bg-amber-400" />
                <span className="text-xs font-mono font-bold text-amber-800 dark:text-amber-400">Txn, Graph, Risk, AML</span>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Threshold Configuration Form */}
      <div className="omerta-card p-6 shadow-md">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 mb-6 pb-4 border-b border-slate-200 dark:border-slate-800">
          <div>
            <h2 className="text-base font-bold text-slate-900 dark:text-white flex items-center gap-2">
              <ShieldCheck className="w-5 h-5 text-sky-600 dark:text-cyan-400" />
              Multi-Signal Risk Scoring Thresholds
            </h2>
            <p className="text-xs text-slate-500 dark:text-slate-400 mt-1">
              Deterministic threshold configuration governing automated queuing and human review routing.
            </p>
          </div>
          <div className="px-3 py-1 rounded-lg bg-amber-50 dark:bg-amber-500/10 border border-amber-300 dark:border-amber-500/30 text-xs font-bold text-amber-800 dark:text-amber-400 self-start sm:self-auto">
            Rule: {settingsData?.review_rule || 'risk_score > 40.00%'}
          </div>
        </div>

        {saveSuccess && (
          <div className="mb-6 p-4 rounded-xl bg-emerald-50 dark:bg-emerald-500/10 border border-emerald-300 dark:border-emerald-500/30 flex items-center gap-3 text-emerald-800 dark:text-emerald-300 text-sm font-bold">
            <CheckCircle2 className="w-5 h-5 flex-shrink-0" />
            <span>{saveSuccess}</span>
          </div>
        )}

        {saveError && (
          <div className="mb-6 p-4 rounded-xl bg-rose-50 dark:bg-rose-500/10 border border-rose-300 dark:border-rose-500/30 flex items-center gap-3 text-rose-800 dark:text-rose-400 text-sm font-bold">
            <AlertTriangle className="w-5 h-5 flex-shrink-0" />
            <span>{saveError}</span>
          </div>
        )}

        <form onSubmit={handleSaveThresholds} className="space-y-6">
          <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
            {/* Human Review Threshold */}
            <div className="bg-slate-50 dark:bg-slate-950 p-5 rounded-xl border border-slate-200 dark:border-slate-800 space-y-3">
              <div className="flex items-center justify-between">
                <label className="text-xs font-bold text-amber-800 dark:text-amber-400 uppercase tracking-wider">
                  Human Review Trigger
                </label>
                <span className="text-sm font-bold font-mono text-amber-900 dark:text-amber-400">{humanReviewThreshold}%</span>
              </div>
              <input
                type="range"
                min="10"
                max="80"
                step="1"
                value={humanReviewThreshold}
                onChange={(e) => setHumanReviewThreshold(Number(e.target.value))}
                disabled={!isAdministrator}
                className="w-full accent-amber-500 cursor-pointer"
              />
              <p className="text-[11px] text-slate-600 dark:text-slate-400">
                Score &gt; {humanReviewThreshold}% triggers queue flagging. Score &le; {humanReviewThreshold}% remains routine.
              </p>
            </div>

            {/* High Risk Threshold */}
            <div className="bg-slate-50 dark:bg-slate-950 p-5 rounded-xl border border-slate-200 dark:border-slate-800 space-y-3">
              <div className="flex items-center justify-between">
                <label className="text-xs font-bold text-orange-800 dark:text-orange-400 uppercase tracking-wider">
                  High-Risk Threshold
                </label>
                <span className="text-sm font-bold font-mono text-orange-900 dark:text-orange-400">{highRiskThreshold}%</span>
              </div>
              <input
                type="range"
                min="50"
                max="90"
                step="1"
                value={highRiskThreshold}
                onChange={(e) => setHighRiskThreshold(Number(e.target.value))}
                disabled={!isAdministrator}
                className="w-full accent-orange-500 cursor-pointer"
              />
              <p className="text-[11px] text-slate-600 dark:text-slate-400">
                Tier escalates priority badge to HIGH and raises investigation urgency.
              </p>
            </div>

            {/* Critical Risk Threshold */}
            <div className="bg-slate-50 dark:bg-slate-950 p-5 rounded-xl border border-slate-200 dark:border-slate-800 space-y-3">
              <div className="flex items-center justify-between">
                <label className="text-xs font-bold text-rose-800 dark:text-red-400 uppercase tracking-wider">
                  Critical Threshold
                </label>
                <span className="text-sm font-bold font-mono text-rose-900 dark:text-red-400">{criticalRiskThreshold}%</span>
              </div>
              <input
                type="range"
                min="75"
                max="99"
                step="1"
                value={criticalRiskThreshold}
                onChange={(e) => setCriticalRiskThreshold(Number(e.target.value))}
                disabled={!isAdministrator}
                className="w-full accent-rose-600 cursor-pointer"
              />
              <p className="text-[11px] text-slate-600 dark:text-slate-400">
                Immediate senior investigator notification and automatic case genesis.
              </p>
            </div>
          </div>

          <div className="flex items-center justify-between pt-4 border-t border-slate-200 dark:border-slate-800">
            <div className="text-xs">
              {isAdministrator ? (
                <span className="text-emerald-700 dark:text-emerald-400 font-bold">Logged in as Administrator (Write Access Granted)</span>
              ) : (
                <span className="text-amber-800 dark:text-amber-400 font-bold">Read-Only Mode: Switch to Administrator role to tune thresholds</span>
              )}
            </div>
            <button
              type="submit"
              disabled={!isAdministrator || saving}
              className="px-5 py-2.5 bg-gradient-to-r from-sky-500 to-cyan-500 hover:brightness-110 text-slate-950 text-xs font-bold rounded-xl flex items-center gap-2 shadow-md shadow-cyan-500/15 disabled:opacity-40 disabled:cursor-not-allowed transition-all"
            >
              <Save className="w-4 h-4" />
              {saving ? 'Persisting Thresholds...' : 'Save Configuration'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};
