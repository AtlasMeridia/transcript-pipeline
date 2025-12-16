'use client';

import type { LogEntry } from '@/src/lib/types';
import { useUIStore } from '@/src/stores/uiStore';

interface ActivityLogProps {
  logs: LogEntry[];
  isProcessing: boolean;
}

export function ActivityLog({ logs, isProcessing }: ActivityLogProps) {
  const { showDetails } = useUIStore();

  if (logs.length === 0) return null;

  const shouldShow = isProcessing ? showDetails : true;

  return (
    <section
      className={`mb-10 overflow-hidden transition-all duration-600 ${
        isProcessing && !shouldShow ? 'max-h-0' : ''
      }`}
    >
      <label className="font-mono text-[0.6875rem] uppercase tracking-wider text-[var(--text-muted)] mb-2 block">
        Activity Log
      </label>
      <div className="bg-[var(--bg-secondary)] rounded-sm border border-[var(--border-subtle)] p-4 max-h-40 overflow-y-auto">
        {logs.map((log, i) => (
          <div key={i} className="font-mono text-[0.6875rem] leading-[1.8] flex gap-2">
            <span className="text-[var(--text-muted)] flex-shrink-0 opacity-60">
              {log.timestamp}
            </span>
            <span
              className={`${
                log.type === 'success'
                  ? 'text-[var(--success)]'
                  : log.type === 'error'
                  ? 'text-[var(--error)]'
                  : 'text-[var(--text-secondary)]'
              }`}
            >
              {log.message}
            </span>
          </div>
        ))}
      </div>
    </section>
  );
}

