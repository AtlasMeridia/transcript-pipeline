import { useEffect, useState, useRef } from 'react';
import type { Job } from '@/src/lib/types';

// Use environment variable or default to same origin
const getApiBaseUrl = () => {
  if (typeof window !== 'undefined') {
    return process.env.NEXT_PUBLIC_API_URL || window.location.origin;
  }
  return process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';
};

export function useJobStream(jobId: string | null) {
  const [status, setStatus] = useState<Job | null>(null);
  const [error, setError] = useState<Error | null>(null);
  const eventSourceRef = useRef<EventSource | null>(null);

  useEffect(() => {
    if (!jobId) {
      setStatus(null);
      setError(null);
      return;
    }

    const url = `${getApiBaseUrl()}/api/jobs/${jobId}/stream`;
    const eventSource = new EventSource(url);
    eventSourceRef.current = eventSource;

    eventSource.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data) as Job;
        setStatus(data);
        setError(null);

        // Close connection if job is complete or errored
        if (data.status === 'complete' || data.status === 'error') {
          eventSource.close();
        }
      } catch (err) {
        setError(err instanceof Error ? err : new Error('Failed to parse SSE data'));
      }
    };

    eventSource.onerror = (err) => {
      setError(new Error('SSE connection error'));
      eventSource.close();
    };

    return () => {
      eventSource.close();
      eventSourceRef.current = null;
    };
  }, [jobId]);

  return { status, error };
}

