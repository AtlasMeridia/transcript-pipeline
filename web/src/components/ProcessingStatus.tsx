'use client';

import type { Job, Phase } from '@/src/lib/types';
import { useUIStore } from '@/src/stores/uiStore';

interface ProcessingStatusProps {
  job: Job | null;
}

const phases: Phase[] = ['download', 'transcribe', 'extract', 'complete'];

function getPhaseDisplayName(phase: Phase | null): string {
  const names: Record<Phase, string> = {
    download: 'Downloading',
    transcribe: 'Transcribing',
    extract: 'Summarizing',
    complete: 'Complete',
  };
  return phase ? names[phase] : 'Starting';
}

function getStatusMessage(phase: Phase | null, rawMessage: string | null): string {
  if (!phase) return 'Getting ready...';
  
  const friendlyMessages: Record<Phase, { default: string; patterns: Array<{ match: RegExp; message: string }> }> = {
    download: {
      default: 'Fetching video information...',
      patterns: [
        { match: /download/i, message: 'Downloading audio from YouTube...' },
        { match: /extract/i, message: 'Extracting audio track...' },
        { match: /fetch/i, message: 'Fetching video details...' },
      ],
    },
    transcribe: {
      default: 'Converting speech to text...',
      patterns: [
        { match: /mlx/i, message: 'Transcribing with MLX Whisper...' },
        { match: /whisper/i, message: 'Analyzing audio with Whisper AI...' },
        { match: /caption/i, message: 'Extracting YouTube captions...' },
        { match: /send/i, message: 'Processing audio...' },
        { match: /progress|%/i, message: 'Transcribing speech to text...' },
      ],
    },
    extract: {
      default: 'Generating insights with AI...',
      patterns: [
        { match: /claude/i, message: 'Analyzing content with Claude AI...' },
        { match: /gpt|openai/i, message: 'Generating summary with GPT...' },
        { match: /extract/i, message: 'Extracting key insights...' },
        { match: /summar/i, message: 'Creating your summary...' },
      ],
    },
    complete: {
      default: 'All done! Your content is ready.',
      patterns: [],
    },
  };

  const phaseConfig = friendlyMessages[phase];
  if (rawMessage) {
    for (const { match, message } of phaseConfig.patterns) {
      if (match.test(rawMessage)) return message;
    }
  }
  return phaseConfig.default;
}

function getProgressPercent(phase: Phase | null): number {
  if (!phase) return 0;
  if (phase === 'complete') return 100;
  const phaseIndex = phases.indexOf(phase);
  if (phaseIndex === -1) return 0;
  return Math.min(95, (phaseIndex + 1) * 25);
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

export function ProcessingStatus({ job }: ProcessingStatusProps) {
  const { showDetails, setShowDetails } = useUIStore();
  
  if (!job) return null;

  const progress = getProgressPercent(job.phase);
  const displayMessage = getStatusMessage(job.phase, job.message);
  const phaseDisplayName = getPhaseDisplayName(job.phase);
  const phaseIndex = job.phase ? phases.indexOf(job.phase) : -1;

  // Parse duration from metadata if available
  const durationStr = job.metadata?.duration;
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

  return (
    <>
      {/* Fixed progress bar at top */}
      <div className="fixed top-[60px] left-0 right-0 h-[3px] bg-[var(--bg-deep)] z-99 overflow-hidden">
        <div
          className="h-full bg-gradient-to-r from-[var(--accent)] to-[var(--accent-light)] transition-all duration-500 ease-out shadow-[0_0_10px_var(--accent)]"
          style={{ width: `${progress}%` }}
        />
      </div>

      {/* Status card */}
      <section className="mb-10 relative">
        <div className="bg-[var(--bg-card)] rounded border border-[var(--border-subtle)] px-6 py-6 text-center relative overflow-hidden">
          <div className="font-heading text-[clamp(1.25rem,3vw,1.5rem)] font-normal text-[var(--text-primary)] mb-1">
            {phaseDisplayName}
          </div>
          <div className="font-ui text-[0.9375rem] text-[var(--text-secondary)] mb-4">
            {displayMessage}
          </div>
          {durationSeconds && (
            <div className="font-mono text-xs text-[var(--text-muted)] mb-4">
              {formatDuration(durationSeconds)}
            </div>
          )}
          
          {/* Phase steps indicator */}
          <div className="flex justify-center gap-1 mt-4">
            {phases.map((phase, i) => (
              <div
                key={phase}
                className={`w-2 h-2 rounded-full transition-all ${
                  i < phaseIndex
                    ? 'bg-[var(--success)]'
                    : i === phaseIndex
                    ? 'bg-[var(--accent)] shadow-[0_0_8px_var(--accent)]'
                    : 'bg-[var(--color-navy-600)]'
                }`}
                title={getPhaseDisplayName(phase)}
              />
            ))}
          </div>

          {/* Collapsible details toggle */}
          <button
            onClick={() => setShowDetails(!showDetails)}
            className="font-mono text-[0.6875rem] uppercase tracking-wider text-[var(--text-muted)] bg-transparent border-none cursor-pointer p-2 mt-4 transition-colors hover:text-[var(--text-secondary)]"
          >
            {showDetails ? '▲ Hide Details' : '▼ Show Details'}
          </button>
        </div>
      </section>
    </>
  );
}

