import React from 'react';
import type { LucideIcon } from 'lucide-react';

interface StatCardProps {
  title: string;
  value: string | number;
  subtitle?: string;
  description?: string;
  change?: string;
  isPositive?: boolean;
  icon: LucideIcon | React.ReactNode;
  variant?: 'default' | 'alert' | 'cyan' | 'emerald';
}

export const StatCard: React.FC<StatCardProps> = ({
  title,
  value,
  subtitle,
  description,
  change,
  isPositive,
  icon,
  variant = 'default',
}) => {
  const sub = subtitle || description;

  const variantStyles = {
    default: 'border-slate-200 dark:border-slate-800 hover:border-slate-300 dark:hover:border-slate-700',
    alert: 'border-amber-300 dark:border-amber-500/40 bg-amber-50/50 dark:bg-amber-500/5',
    cyan: 'border-sky-300 dark:border-sky-500/40 bg-sky-50/50 dark:bg-sky-500/5',
    emerald: 'border-emerald-300 dark:border-emerald-500/40 bg-emerald-50/50 dark:bg-emerald-500/5',
  };

  const iconColors = {
    default: 'text-sky-600 dark:text-sky-400 bg-sky-100 dark:bg-sky-500/10 border-sky-200 dark:border-sky-500/30',
    alert: 'text-amber-700 dark:text-amber-400 bg-amber-100 dark:bg-amber-500/10 border-amber-200 dark:border-amber-500/30',
    cyan: 'text-cyan-700 dark:text-cyan-400 bg-cyan-100 dark:bg-cyan-500/10 border-cyan-200 dark:border-cyan-500/30',
    emerald: 'text-emerald-700 dark:text-emerald-400 bg-emerald-100 dark:bg-emerald-500/10 border-emerald-200 dark:border-emerald-500/30',
  };

  const renderIcon = () => {
    if (React.isValidElement(icon)) {
      return icon;
    }
    if (typeof icon === 'function' || typeof icon === 'object') {
      const IconComponent = icon as LucideIcon;
      return <IconComponent className="h-5 w-5" />;
    }
    return null;
  };

  return (
    <div
      className={`omerta-card p-5 transition-all duration-200 hover:-translate-y-0.5 ${variantStyles[variant]}`}
    >
      <div className="flex items-start justify-between">
        <div className="space-y-1">
          <p className="text-xs font-semibold uppercase tracking-wider text-slate-600 dark:text-slate-400">
            {title}
          </p>
          <div className="text-2xl font-bold tracking-tight text-slate-900 dark:text-white font-mono">
            {value}
          </div>
        </div>
        <div className={`p-2.5 rounded-lg border shadow-sm ${iconColors[variant]}`}>
          {renderIcon()}
        </div>
      </div>

      {(sub || change) && (
        <div className="mt-3 flex items-center gap-2 text-xs">
          {change && (
            <span
              className={`font-semibold ${
                isPositive ? 'text-emerald-700 dark:text-emerald-400' : 'text-rose-700 dark:text-rose-400'
              }`}
            >
              {change}
            </span>
          )}
          {sub && <span className="text-slate-500 dark:text-slate-400">{sub}</span>}
        </div>
      )}
    </div>
  );
};
