'use client';

import { useState, useEffect } from 'react';
import { useMutation, useQuery } from '@tanstack/react-query';
import { Header } from '@/src/components/Header';
import { HeroSection } from '@/src/components/HeroSection';
import { VideoUrlInput } from '@/src/components/VideoUrlInput';
import { ProcessingStatus } from '@/src/components/ProcessingStatus';
import { ActivityLog } from '@/src/components/ActivityLog';
import { ResultsViewer } from '@/src/components/ResultsViewer';
import { useJobStream } from '@/src/hooks/useJobStream';
import { useUIStore } from '@/src/stores/uiStore';
import { api } from '@/src/lib/api';
import type { Results } from '@/src/lib/types';

export default function Home() {
  const [currentJobId, setCurrentJobId] = useState<string | null>(null);
  const [results, setResults] = useState<Results | null>(null);
  const [error, setError] = useState<string | null>(null);
  const { status: jobStatus } = useJobStream(currentJobId);
  const {
    url,
    setUrl,
    logs,
    addLog,
    clearLogs,
    setShowDetails,
    setActiveTab,
  } = useUIStore();

  const processMutation = useMutation({
    mutationFn: (url: string) => api.startProcessing(url),
    onSuccess: (data) => {
      setCurrentJobId(data.job_id);
      addLog('Started processing job', 'info');
    },
    onError: (err) => {
      setError(err instanceof Error ? err.message : 'Failed to start processing');
      addLog(`Error: ${err instanceof Error ? err.message : 'Unknown error'}`, 'error');
    },
  });

  // Handle job status updates from SSE
  useEffect(() => {
    if (!jobStatus) return;

    if (jobStatus.message) {
      const logType =
        jobStatus.status === 'error'
          ? 'error'
          : jobStatus.status === 'complete'
          ? 'success'
          : 'default';
      addLog(jobStatus.message, logType);
    }

    if (jobStatus.status === 'complete') {
      addLog('Processing complete, fetching results...', 'info');
      Promise.all([
        api.getTranscript(jobStatus.job_id),
        api.getSummary(jobStatus.job_id).catch(() => null),
      ])
        .then(([transcript, summary]) => {
          setResults({
            title: jobStatus.metadata?.title || 'Untitled',
            transcript: transcript.content,
            summary: summary?.content || null,
            metadata: jobStatus.metadata || {
              title: 'Untitled',
              url: '',
            },
          });
          addLog('Your transcript is ready to view', 'success');
        })
        .catch((err) => {
          setError('Failed to load results: ' + (err instanceof Error ? err.message : 'Unknown error'));
          addLog(`Failed to load results: ${err instanceof Error ? err.message : 'Unknown error'}`, 'error');
        });
    } else if (jobStatus.status === 'error') {
      setError(jobStatus.error || 'An error occurred');
    }
  }, [jobStatus, addLog]);

  const handleProcess = (videoUrl: string) => {
    setError(null);
    setResults(null);
    clearLogs();
    setShowDetails(false);
    setActiveTab('transcript');
    processMutation.mutate(videoUrl);
  };

  const resetPipeline = () => {
    setUrl('');
    clearLogs();
    setResults(null);
    setError(null);
    setCurrentJobId(null);
    setShowDetails(false);
  };

  const isProcessing = processMutation.isPending || (jobStatus?.status !== 'complete' && jobStatus?.status !== 'error' && currentJobId !== null);

  return (
    <div className="min-h-screen flex flex-col">
      <Header />
      <HeroSection />
      <main className="flex-1 px-4 pb-16 max-w-7xl mx-auto w-full">
        <VideoUrlInput onProcess={handleProcess} isProcessing={isProcessing} />

        {isProcessing && jobStatus && (
          <ProcessingStatus job={jobStatus} />
        )}

        {error && (
          <div className="bg-[var(--error-subtle)] border border-[rgba(176,84,84,0.3)] rounded-sm px-4 py-4 mb-10 font-ui text-sm text-[var(--error)]">
            Error: {error}
          </div>
        )}

        <ActivityLog logs={logs} isProcessing={isProcessing} />

        {results && (
          <>
            <ResultsViewer results={results} jobId={currentJobId || ''} />
            <div className="px-6 py-4 border-t border-[var(--border-subtle)] flex justify-center mt-4">
              <button
                onClick={resetPipeline}
                className="bg-transparent border border-[var(--border-color)] rounded-sm px-6 py-3 font-ui text-sm text-[var(--text-secondary)] cursor-pointer transition-all min-h-[44px] hover:border-[var(--accent)] hover:text-[var(--accent)]"
              >
                Process Another Video
              </button>
            </div>
          </>
        )}
      </main>

      <footer className="border-t border-[var(--border-subtle)] px-6 py-6 mt-auto">
        <div className="max-w-7xl mx-auto flex justify-between items-center flex-wrap gap-2">
          <span className="font-mono text-[0.6875rem] text-[var(--text-muted)]">
            Transcript Pipeline v1.0
          </span>
          <div className="flex gap-6">
            <a
              href="https://github.com/AtlasMeridia/transcript-pipeline"
              target="_blank"
              rel="noopener noreferrer"
              className="font-ui text-[0.8125rem] text-[var(--text-secondary)] text-decoration-none transition-colors min-h-[44px] flex items-center hover:text-[var(--text-primary)]"
            >
              GitHub
            </a>
          </div>
        </div>
      </footer>
    </div>
  );
}
