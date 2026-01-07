'use client';

import { useState } from 'react';
import { useUIStore } from '@/src/stores/uiStore';
import { useQuery } from '@tanstack/react-query';
import { api } from '@/src/lib/api';

interface VideoUrlInputProps {
  onProcess: (url: string) => void;
  isProcessing: boolean;
}

export function VideoUrlInput({ onProcess, isProcessing }: VideoUrlInputProps) {
  const { url, setUrl, inputFocused, setInputFocused } = useUIStore();
  const [buttonHovered, setButtonHovered] = useState(false);

  const { data: config } = useQuery({
    queryKey: ['config'],
    queryFn: () => api.getConfig(),
  });

  const handleSubmit = () => {
    if (url.trim() && !isProcessing) {
      onProcess(url.trim());
    }
  };

  return (
    <section className="mb-10 max-w-2xl mx-auto">
      <label className="font-mono text-[0.6875rem] uppercase tracking-wider text-[var(--text-muted)] mb-2 block">
        YouTube URL
      </label>
      <div className="flex gap-4 items-stretch flex-col md:flex-row">
        <input
          type="text"
          value={url}
          onChange={(e) => setUrl(e.target.value)}
          onKeyDown={(e) => e.key === 'Enter' && !isProcessing && handleSubmit()}
          onFocus={() => setInputFocused(true)}
          onBlur={() => setInputFocused(false)}
          placeholder="Paste a YouTube link..."
          disabled={isProcessing}
          autoComplete="off"
          autoCapitalize="off"
          className={`flex-1 bg-[var(--bg-secondary)] border border-[var(--border-color)] rounded-sm px-4 py-4 font-ui text-base text-[var(--text-primary)] outline-none transition-all min-h-[48px] ${
            inputFocused
              ? 'border-[var(--accent)] shadow-[0_0_0_3px_rgba(201,146,74,0.15)]'
              : ''
          }`}
        />
        <button
          onClick={handleSubmit}
          disabled={isProcessing || !url.trim()}
          onMouseEnter={() => setButtonHovered(true)}
          onMouseLeave={() => setButtonHovered(false)}
          className={`bg-gradient-to-br from-[var(--accent)] to-[var(--accent-dark)] border-none rounded-sm px-10 py-4 font-ui text-sm font-medium uppercase tracking-wider text-[var(--cream-50)] cursor-pointer transition-all whitespace-nowrap shadow-[0_4px_20px_rgba(201,146,74,0.25)] min-h-[48px] md:w-auto w-full ${
            isProcessing || !url.trim()
              ? 'bg-[var(--bg-elevated)] text-[var(--text-muted)] cursor-not-allowed shadow-none'
              : buttonHovered
              ? 'transform -translate-y-0.5 shadow-[0_6px_30px_rgba(201,146,74,0.35)]'
              : ''
          }`}
        >
          {isProcessing ? 'Processing...' : 'Process'}
        </button>
      </div>
      {config?.mlx_whisper_model && config?.transcription_engine !== 'captions' && (
        <div className="mt-2 font-mono text-xs text-[var(--text-muted)] flex items-center gap-4 flex-wrap">
          <span>MLX Whisper</span>
          <span className="bg-[var(--accent-gold-subtle)] px-2 py-0.5 rounded-sm text-[var(--accent)]">
            {config.mlx_whisper_model}
          </span>
        </div>
      )}
    </section>
  );
}

