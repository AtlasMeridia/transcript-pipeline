// TypeScript types matching FastAPI models

export type JobStatus = 
  | 'pending'
  | 'downloading'
  | 'transcribing'
  | 'extracting'
  | 'complete'
  | 'error';

export type Phase =
  | 'download'
  | 'transcribe'
  | 'extract'
  | 'complete';

export type LLMType = 'claude' | 'gpt';

export interface ProcessRequest {
  url: string;
  llm_type?: LLMType;
  extract?: boolean;
}

export interface VideoMetadata {
  title: string;
  author?: string;
  date?: string;
  duration?: string;
  url: string;
}

export interface Job {
  job_id: string;
  status: JobStatus;
  phase: Phase | null;
  progress: number | null;
  message: string | null;
  metadata: VideoMetadata | null;
  transcript_path: string | null;
  summary_path: string | null;
  error: string | null;
  created_at: string;
  completed_at: string | null;
}

export interface ProcessResponse {
  job_id: string;
  status: JobStatus;
  phase: Phase | null;
  progress: number | null;
  message: string | null;
  metadata: VideoMetadata | null;
  transcript_path: string | null;
  summary_path: string | null;
  error: string | null;
  created_at: string;
  completed_at: string | null;
}

export interface TranscriptResponse {
  content: string;
  path: string;
}

export interface SummaryResponse {
  content: string;
  path: string;
}

export interface ConfigResponse {
  default_llm: LLMType;
  output_dir: string;
  has_anthropic_key: boolean;
  has_openai_key: boolean;
  transcription_engine: string;
  mlx_whisper_model?: string;
}

export interface Results {
  title: string;
  transcript: string;
  summary: string | null;
  metadata: VideoMetadata;
}

export interface LogEntry {
  timestamp: string;
  message: string;
  type: 'default' | 'success' | 'error' | 'info';
}

