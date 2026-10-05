import React from 'react';

interface StatusBadgeProps {
  status: string;
  type?: 'transaction' | 'review' | 'case' | 'general';
}

export const StatusBadge: React.FC<StatusBadgeProps> = ({ status }) => {
  const norm = (status || 'UNKNOWN').toUpperCase();

  const getStyle = (st: string) => {
    switch (st) {
      case 'COMPLETED':
      case 'ACTIVE':
      case 'RESOLVED':
      case 'CLOSED':
        return 'bg-emerald-50 dark:bg-emerald-500/20 text-emerald-800 dark:text-emerald-300 border-emerald-300 dark:border-emerald-500/40 font-semibold';
      case 'REQUIRES_REVIEW':
      case 'OPEN':
      case 'NEW':
      case 'PENDING':
      case 'PENDING_REVIEW':
        return 'bg-amber-50 dark:bg-amber-500/20 text-amber-900 dark:text-amber-300 border-amber-300 dark:border-amber-500/40 font-semibold';
      case 'UNDER_INVESTIGATION':
      case 'IN_REVIEW':
        return 'bg-sky-50 dark:bg-sky-500/20 text-sky-900 dark:text-sky-300 border-sky-300 dark:border-sky-500/40 font-semibold';
      case 'ESCALATED':
        return 'bg-rose-50 dark:bg-rose-500/20 text-rose-900 dark:text-rose-300 border-rose-300 dark:border-rose-500/40 font-bold';
      case 'NOT_REQUIRED':
        return 'bg-slate-100 dark:bg-slate-800 text-slate-700 dark:text-slate-300 border-slate-300 dark:border-slate-700 font-medium';
      default:
        return 'bg-slate-100 dark:bg-slate-800 text-slate-700 dark:text-slate-300 border-slate-300 dark:border-slate-700 font-medium';
    }
  };

  return (
    <span
      className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs border shadow-sm ${getStyle(
        norm
      )}`}
    >
      {norm.replace(/_/g, ' ')}
    </span>
  );
};
