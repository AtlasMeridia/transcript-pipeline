import { useEffect, useState, useRef, useCallback } from 'react';
import type { Job } from '@/src/lib/types';

const getApiBaseUrl = () => {
  if (typeof window !== 'undefined') {
    return process.env.NEXT_PUBLIC_API_URL || window.location.origin;
  }
  return process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';
};

const MAX_RECONNECT_ATTEMPTS = 3;
const INITIAL_RECONNECT_DELAY = 1000;

export function useJobStream(jobId: string | null) {
  const [status, setStatus] = useState<Job | null>(null);
  const [error, setError] = useState<Error | null>(null);
  const [isConnecting, setIsConnecting] = useState(false);
  const eventSourceRef = useRef<EventSource | null>(null);
  const reconnectAttemptsRef = useRef(0);
  const reconnectTimeoutRef = useRef<NodeJS.Timeout | null>(null);
  const lastStatusRef = useRef<Job | null>(null);

  const connect = useCallback(() => {
    if (!jobId) return;

    // Don't reconnect if job is already complete
    if (lastStatusRef.current?.status === 'complete' || lastStatusRef.current?.status === 'error') {
      return;
    }

    setIsConnecting(true);
    const url = `${getApiBaseUrl()}/api/jobs/${jobId}/stream`;
    const eventSource = new EventSource(url);
    eventSourceRef.current = eventSource;

    eventSource.onopen = () => {
      setIsConnecting(false);
      reconnectAttemptsRef.current = 0;
    };

    eventSource.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data) as Job;
        setStatus(data);
        lastStatusRef.current = data;
        setError(null);

        if (data.status === 'complete' || data.status === 'error') {
          eventSource.close();
        }
      } catch (err) {
        setError(err instanceof Error ? err : new Error('Failed to parse SSE data'));
      }
    };

    eventSource.onerror = () => {
      eventSource.close();
      setIsConnecting(false);

      // Don't reconnect if job is already complete
      if (lastStatusRef.current?.status === 'complete' || lastStatusRef.current?.status === 'error') {
        return;
      }

      // Attempt reconnection with exponential backoff
      if (reconnectAttemptsRef.current < MAX_RECONNECT_ATTEMPTS) {
        const delay = INITIAL_RECONNECT_DELAY * Math.pow(2, reconnectAttemptsRef.current);
        reconnectAttemptsRef.current++;

        reconnectTimeoutRef.current = setTimeout(() => {
          connect();
        }, delay);
      } else {
        setError(new Error('Connection lost. Please refresh the page.'));
      }
    };
  }, [jobId]);

  useEffect(() => {
    if (!jobId) {
      setStatus(null);
      setError(null);
      lastStatusRef.current = null;
      return;
    }

    connect();

    return () => {
      if (eventSourceRef.current) {
        eventSourceRef.current.close();
        eventSourceRef.current = null;
      }
      if (reconnectTimeoutRef.current) {
        clearTimeout(reconnectTimeoutRef.current);
        reconnectTimeoutRef.current = null;
      }
      reconnectAttemptsRef.current = 0;
    };
  }, [jobId, connect]);

  return { status, error, isConnecting };
}
