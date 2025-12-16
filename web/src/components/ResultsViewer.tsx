'use client';

import { useState, useRef } from 'react';
import { marked } from 'marked';
import type { Results } from '@/src/lib/types';
import { useUIStore } from '@/src/stores/uiStore';
import { api } from '@/src/lib/api';

interface ResultsViewerProps {
  results: Results;
  jobId: string;
}

function formatDuration(seconds: number | undefined): string {
  if (!seconds) return '';
  const h = Math.floor(seconds / 3600);
  const m = Math.floor((seconds % 3600) / 60);
  const s = Math.floor(seconds % 60);
  if (h > 0) return `${h}h ${m}m`;
  if (m > 0) return `${m}m ${s}s`;
  return `${s}s`;
}

export function ResultsViewer({ results, jobId }: ResultsViewerProps) {
  const {
    previewMode,
    setPreviewMode,
    activeTab,
    setActiveTab,
    hoveredControl,
    setHoveredControl,
  } = useUIStore();
  const touchStartX = useRef<number | null>(null);

  const handleTouchStart = (e: React.TouchEvent) => {
    touchStartX.current = e.touches[0].clientX;
  };

  const handleTouchEnd = (e: React.TouchEvent) => {
    if (!touchStartX.current) return;
    const touchEndX = e.changedTouches[0].clientX;
    const diff = touchStartX.current - touchEndX;
    const threshold = 50;

    if (Math.abs(diff) > threshold) {
      if (diff > 0 && results.summary && activeTab === 'transcript') {
        setActiveTab('summary');
      } else if (diff < 0 && activeTab === 'summary') {
        setActiveTab('transcript');
      }
    }
    touchStartX.current = null;
  };

  const durationStr = results.metadata.duration;
  const durationSeconds = durationStr
    ? (() => {
        const parts = durationStr.split(/[hm\s]+/).filter(Boolean);
        if (parts.length === 0) return undefined;
        let total = 0;
        for (const part of parts) {
          if (part.endsWith('h')) {
            total += parseInt(part) * 3600;
          } else if (part.endsWith('m')) {
            total += parseInt(part) * 60;
          } else if (part.endsWith('s')) {
            total += parseInt(part);
          }
        }
        return total;
      })()
    : undefined;

  const content = activeTab === 'transcript' ? results.transcript : results.summary || '';
  const htmlContent = previewMode ? marked.parse(content) : '';

  return (
    <section className="mt-10">
      <div className="bg-[var(--bg-card)] rounded border border-[var(--border-subtle)] overflow-hidden">
        {/* Result Header */}
        <div className="px-4 py-4 border-b border-[var(--border-subtle)]">
          <h2 className="font-display text-[clamp(1.25rem,3vw,1.75rem)] font-normal text-[var(--text-primary)] mb-1 leading-tight">
            {results.title}
          </h2>
          <div className="font-mono text-[0.6875rem] text-[var(--text-muted)] flex flex-wrap gap-2">
            {results.metadata.author && <span>{results.metadata.author}</span>}
            {durationSeconds && <span>{formatDuration(durationSeconds)}</span>}
          </div>
        </div>

        {/* Tabs */}
        <div className="flex border-b border-[var(--border-subtle)] bg-[var(--bg-secondary)] overflow-x-auto scrollbar-hide">
          <button
            onClick={() => setActiveTab('transcript')}
            className={`px-6 py-4 font-ui text-sm text-[var(--text-secondary)] bg-transparent border-none border-b-2 border-transparent cursor-pointer transition-all mb-[-1px] whitespace-nowrap min-h-[48px] flex-1 text-center ${
              activeTab === 'transcript'
                ? 'text-[var(--text-primary)] border-b-[var(--accent)]'
                : ''
            }`}
          >
            Transcript
          </button>
          {results.summary && (
            <button
              onClick={() => setActiveTab('summary')}
              className={`px-6 py-4 font-ui text-sm text-[var(--text-secondary)] bg-transparent border-none border-b-2 border-transparent cursor-pointer transition-all mb-[-1px] whitespace-nowrap min-h-[48px] flex-1 text-center ${
                activeTab === 'summary'
                  ? 'text-[var(--text-primary)] border-b-[var(--accent)]'
                  : ''
              }`}
            >
              Summary
            </button>
          )}
        </div>

        {/* Controls */}
        <div className="flex justify-between items-center px-2 py-2 border-b border-[var(--border-subtle)] bg-[var(--bg-secondary)] flex-wrap gap-2">
          <button
            onClick={() => setPreviewMode(!previewMode)}
            onMouseEnter={() => setHoveredControl('preview')}
            onMouseLeave={() => setHoveredControl(null)}
            className={`font-mono text-[0.6875rem] px-4 py-2 bg-transparent border border-[var(--border-color)] rounded-sm text-[var(--text-secondary)] cursor-pointer transition-all text-decoration-none inline-flex items-center gap-1 min-h-9 ${
              previewMode
                ? 'bg-[var(--accent-gold-subtle)] border-[var(--accent)] text-[var(--accent)]'
                : hoveredControl === 'preview'
                ? 'border-[var(--accent)] text-[var(--accent)]'
                : ''
            }`}
          >
            {previewMode ? '◉ Preview' : '○ Raw'}
          </button>
          <div className="flex gap-2 flex-wrap">
            <a
              href={api.getDownloadUrl(jobId, 'transcript')}
              onMouseEnter={() => setHoveredControl('download-transcript')}
              onMouseLeave={() => setHoveredControl(null)}
              className={`font-mono text-[0.6875rem] px-4 py-2 bg-transparent border border-[var(--border-color)] rounded-sm text-[var(--text-secondary)] cursor-pointer transition-all text-decoration-none inline-flex items-center gap-1 min-h-9 ${
                hoveredControl === 'download-transcript'
                  ? 'border-[var(--accent)] text-[var(--accent)]'
                  : ''
              }`}
            >
              ↓ Transcript
            </a>
            {results.summary && (
              <a
                href={api.getDownloadUrl(jobId, 'summary')}
                onMouseEnter={() => setHoveredControl('download-summary')}
                onMouseLeave={() => setHoveredControl(null)}
                className={`font-mono text-[0.6875rem] px-4 py-2 bg-transparent border border-[var(--border-color)] rounded-sm text-[var(--text-secondary)] cursor-pointer transition-all text-decoration-none inline-flex items-center gap-1 min-h-9 ${
                  hoveredControl === 'download-summary'
                    ? 'border-[var(--accent)] text-[var(--accent)]'
                    : ''
                }`}
              >
                ↓ Summary
              </a>
            )}
          </div>
        </div>

        {/* Content */}
        <div
          className="p-4 max-h-[calc(100vh-300px)] min-h-[200px] overflow-y-auto"
          onTouchStart={handleTouchStart}
          onTouchEnd={handleTouchEnd}
        >
          {previewMode ? (
            <div
              className="markdown-preview"
              dangerouslySetInnerHTML={{ __html: htmlContent }}
            />
          ) : (
            <pre className="font-mono text-xs leading-[1.7] text-[var(--text-secondary)] whitespace-pre-wrap break-words">
              {content}
            </pre>
          )}
        </div>
      </div>
    </section>
  );
}

