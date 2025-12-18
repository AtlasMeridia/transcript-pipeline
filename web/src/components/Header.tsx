'use client';

import { useQuery } from '@tanstack/react-query';
import { api } from '@/src/lib/api';

export function Header() {
  const { data: config } = useQuery({
    queryKey: ['config'],
    queryFn: () => api.getConfig(),
  });

  return (
    <header className="sticky top-0 z-50 bg-[rgba(14,19,24,0.9)] backdrop-blur-xl border-b border-[var(--border-subtle)]">
      <div className="max-w-7xl mx-auto px-6 h-[60px] flex items-center justify-between">
        <span className="font-heading text-xl font-medium italic text-[var(--text-primary)] tracking-tight">
          Transcript Pipeline
        </span>
        <nav className="flex gap-6 items-center">
          <span className="font-ui text-sm text-[var(--text-secondary)] flex items-center gap-1.5">
            <span
              className="w-1.5 h-1.5 rounded-full inline-block"
              style={{
                background: config?.has_anthropic_key
                  ? 'var(--success)'
                  : 'var(--error)',
              }}
            />
            {config?.has_anthropic_key ? 'Connected' : 'No API Key'}
          </span>
        </nav>
      </div>
    </header>
  );
}

