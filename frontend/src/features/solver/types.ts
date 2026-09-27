export type ExecutionReason =
  | "CONTEST_NOT_STARTED"
  | "CONTEST_PAUSED"
  | "CONTEST_FINISHED"
  | "JUDGE_UNAVAILABLE";
export interface ContestDetail {
  id: number;
  title: string;
  status: string;
  start_time: string;
  end_time: string;
  server_time: string;
  paused_at: string | null;
  can_manage: boolean;
  practice_enabled: boolean;
  practice_execution: { allowed: boolean; reason: ExecutionReason | null };
  execution: { allowed: boolean; reason: ExecutionReason | null };
  problems: { id: number; title: string; letter: string }[];
}

export interface Sample {
  input_data: string;
  expected: string;
  is_sample: boolean;
}
export interface ProblemDetail {
  id: number;
  title: string;
  description: string;
  input_fmt: string;
  output_fmt: string;
  difficulty: string;
  time_limit: number;
  mem_limit: number;
  samples: Sample[];
  editorial?: string;
}

export type SubmissionKind = "RUN" | "SUBMIT";
export interface SubmissionResult {
  id: number;
  status: string;
  error?: string;
  tests?: {
    ordinal: number;
    verdict: string;
    stdout: string;
    stderr: string;
    time_ms: number;
  }[];
}
