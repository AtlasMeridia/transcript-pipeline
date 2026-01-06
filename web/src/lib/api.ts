import type {
  ProcessRequest,
  ProcessResponse,
  Job,
  TranscriptResponse,
  SummaryResponse,
  ConfigResponse,
} from './types';

// Use environment variable or default to localhost for development
// In production/Docker, this will be set via NEXT_PUBLIC_API_URL
const getApiBaseUrl = () => {
  if (typeof window !== 'undefined') {
    // Client-side: use environment variable or fallback to same origin
    return process.env.NEXT_PUBLIC_API_URL || window.location.origin;
  }
  // Server-side: use environment variable or default
  return process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';
};

class ApiError extends Error {
  constructor(
    message: string,
    public status?: number,
    public response?: Response
  ) {
    super(message);
    this.name = 'ApiError';
  }
}

const MAX_RETRIES = 3;
const INITIAL_RETRY_DELAY = 1000;
const RETRYABLE_STATUS_CODES = [408, 429, 500, 502, 503, 504];

async function sleep(ms: number): Promise<void> {
  return new Promise(resolve => setTimeout(resolve, ms));
}

async function fetchApi<T>(
  endpoint: string,
  options?: RequestInit
): Promise<T> {
  const url = `${getApiBaseUrl()}${endpoint}`;

  for (let attempt = 0; attempt <= MAX_RETRIES; attempt++) {
    try {
      const response = await fetch(url, {
        ...options,
        headers: {
          'Content-Type': 'application/json',
          ...options?.headers,
        },
      });

      if (!response.ok) {
        // Only retry on specific status codes
        if (RETRYABLE_STATUS_CODES.includes(response.status) && attempt < MAX_RETRIES) {
          const delay = INITIAL_RETRY_DELAY * Math.pow(2, attempt);
          await sleep(delay);
          continue;
        }

        throw new ApiError(
          `API request failed: ${response.statusText}`,
          response.status,
          response
        );
      }

      return response.json();
    } catch (error) {
      // Retry on network errors (TypeError from fetch)
      if (error instanceof TypeError && attempt < MAX_RETRIES) {
        const delay = INITIAL_RETRY_DELAY * Math.pow(2, attempt);
        await sleep(delay);
        continue;
      }
      // Re-throw ApiError or other errors
      throw error;
    }
  }

  throw new ApiError('Max retries exceeded', undefined, undefined);
}

export const api = {
  /**
   * Start processing a YouTube video
   */
  async startProcessing(
    url: string,
    options?: { llm_type?: 'claude' | 'gpt'; extract?: boolean }
  ): Promise<ProcessResponse> {
    const request: ProcessRequest = {
      url,
      llm_type: options?.llm_type,
      extract: options?.extract !== false,
    };
    return fetchApi<ProcessResponse>('/api/process', {
      method: 'POST',
      body: JSON.stringify(request),
    });
  },

  /**
   * Get job status
   */
  async getJobStatus(jobId: string): Promise<Job> {
    return fetchApi<Job>(`/api/jobs/${jobId}`);
  },

  /**
   * Get transcript content
   */
  async getTranscript(jobId: string): Promise<TranscriptResponse> {
    return fetchApi<TranscriptResponse>(`/api/jobs/${jobId}/transcript`);
  },

  /**
   * Get summary content
   */
  async getSummary(jobId: string): Promise<SummaryResponse | null> {
    try {
      return await fetchApi<SummaryResponse>(`/api/jobs/${jobId}/summary`);
    } catch (error) {
      if (error instanceof ApiError && error.status === 404) {
        return null;
      }
      throw error;
    }
  },

  /**
   * Get download URL for transcript or summary
   */
  getDownloadUrl(jobId: string, fileType: 'transcript' | 'summary'): string {
    return `${getApiBaseUrl()}/api/jobs/${jobId}/download/${fileType}`;
  },

  /**
   * Get configuration
   */
  async getConfig(): Promise<ConfigResponse> {
    return fetchApi<ConfigResponse>('/api/config');
  },
};

