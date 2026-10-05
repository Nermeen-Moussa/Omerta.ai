import React from 'react';
import type { RiskLevel } from '../../types';

interface RiskBadgeProps {
  level: RiskLevel | string;
  score?: number;
  size?: 'sm' | 'md' | 'lg';
}

export const RiskBadge: React.FC<RiskBadgeProps> = ({ level, score, size = 'md' }) => {
  const normalizedLevel = (level || 'LOW').toUpperCase();

  const config: Record<string, { bg: string; text: string; border: string; label: string }> = {
    LOW: {
      bg: 'bg-emerald-50 dark:bg-emerald-500/20',
      text: 'text-emerald-800 dark:text-emerald-300 font-semibold',
      border: 'border-emerald-300 dark:border-emerald-500/40',
      label: 'Low Risk',
    },
    MODERATE: {
      bg: 'bg-amber-50 dark:bg-amber-500/20',
      text: 'text-amber-900 dark:text-amber-300 font-semibold',
      border: 'border-amber-300 dark:border-amber-500/40',
      label: 'Moderate',
    },
    REQUIRES_REVIEW: {
      bg: 'bg-orange-50 dark:bg-orange-500/20',
      text: 'text-orange-900 dark:text-orange-300 font-semibold',
      border: 'border-orange-300 dark:border-orange-500/40',
      label: 'Requires Review',
    },
    HIGH: {
      bg: 'bg-rose-50 dark:bg-rose-500/20',
      text: 'text-rose-900 dark:text-rose-300 font-semibold',
      border: 'border-rose-300 dark:border-rose-500/40',
      label: 'High Risk',
    },
    CRITICAL: {
      bg: 'bg-red-50 dark:bg-red-600/30',
      text: 'text-red-950 dark:text-red-200 font-bold',
      border: 'border-red-400 dark:border-red-500/60',
      label: 'Critical Risk',
    },
  };

  const style = config[normalizedLevel] || config.LOW;

  const sizeClasses = {
    sm: 'px-2 py-0.5 text-xs',
    md: 'px-2.5 py-1 text-xs',
    lg: 'px-3 py-1.5 text-sm',
  };

  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded-full border shadow-sm ${style.bg} ${style.text} ${style.border} ${sizeClasses[size]}`}
    >
      <span className="h-2 w-2 rounded-full bg-current opacity-90" />
      <span>{style.label}</span>
      {score !== undefined && (
        <span className="opacity-90 font-mono text-[0.9em] ml-0.5 font-bold">({score.toFixed(1)}%)</span>
      )}
    </span>
  );
};
