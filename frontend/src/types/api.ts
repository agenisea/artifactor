// TypeScript types mirroring backend Pydantic models.
// Contract safety: changes to backend schemas must be reflected here.

// Mirrors: src/artifactor/api/schemas.py -> APIResponse
export interface APIResponse<T = unknown> {
  success: boolean;
  data: T | null;
  error: string | null;
  metadata: Record<string, unknown>;
}

// Mirrors: src/artifactor/intelligence/value_objects.py -> Citation
export interface Citation {
  file_path: string;
  function_name: string | null;
  line_start: number;
  line_end: number;
  confidence: number;
}

// Mirrors: src/artifactor/intelligence/value_objects.py -> ConfidenceScore
export interface ConfidenceScore {
  value: number;
  source: "ast" | "llm" | "cross_validated";
  explanation: string;
}

// Mirrors: src/artifactor/intelligence/value_objects.py -> CodeLocation
export interface CodeLocation {
  file: string;
  line: number;
  column: number;
  language: string;
}

// Mirrors: src/artifactor/intelligence/value_objects.py -> EntityType
export interface EntityType {
  kind: "class" | "function" | "module" | "endpoint" | "table" | "interface";
  language: string | null;
}

// Mirrors: src/artifactor/agent/schemas.py -> AgentResponse
export interface AgentResponse {
  message: string;
  citations: Citation[];
  confidence: ConfidenceScore | null;
  tools_used: string[];
}

// Mirrors: src/artifactor/api/schemas.py -> ProjectCreate
export interface ProjectCreate {
  name: string;
  local_path: string | null;
  branch: string | null;
}

// Mirrors: src/artifactor/api/schemas.py -> ChatRequest
export interface ChatRequest {
  message: string;
  conversation_id: string | null;
}

// ── Chat SSE types ──────────────────────────────────────────────

// Wire-format discriminated union (mirrors chat.py event stream)
export type ChatSSEEvent =
  | { event: "thinking"; data: { status: string; request_id: string } }
  | { event: "tool_call"; data: { tool: string; message: string; request_id: string } }
  | {
      event: "complete";
      data: {
        message: string;
        citations: Citation[];
        confidence: ConfidenceScore | null;
        tools_used: string[];
        conversation_id: string;
        request_id: string;
        model: string;
      };
    }
  | { event: "error"; data: { error: string; request_id: string } };

// String literal union for useSSEStream TEvent parameter
export type ChatEventType = "idle" | "thinking" | "tool_call" | "complete" | "error";

// Loose interface for useSSEStream TUpdate (different events have different shapes)
export interface ChatEventData {
  status?: string;
  tool?: string;
  message?: string;
  citations?: Citation[];
  confidence?: ConfidenceScore | null;
  tools_used?: string[];
  conversation_id?: string;
  model?: string;
  error?: string;
  request_id?: string;
}

// Result extracted from the complete event
export interface ChatResult {
  message: string;
  citations: Citation[];
  confidence: ConfidenceScore | null;
  tools_used: string[];
  conversation_id: string;
}

// ── Analysis SSE types ──────────────────────────────────────────

// Wire-format discriminated union (mirrors projects.py event stream)
export type AnalysisSSEEvent =
  | {
      event: "stage";
      data: {
        name: string;
        status: "running" | "done" | "error";
        message: string;
        duration_ms: number;
      };
    }
  | {
      event: "complete";
      data: {
        project_id: string;
        sections: number;
        stages_ok: number;
        stages_failed: number;
        duration_ms: number;
      };
    }
  | { event: "paused"; data: { message: string } }
  | { event: "error"; data: { error: string } };

// Mirrors: src/artifactor/api/schemas.py -> PlaybookStepResponse
export interface PlaybookStep {
  description: string;
  tool: string;
}

// Mirrors: src/artifactor/api/schemas.py -> PlaybookMetaResponse
export interface PlaybookMeta {
  name: string;
  title: string;
  description: string;
  agent: string;
  difficulty: string;
  estimatedTime: string;
  mcpPrompt: string;
  tags: string[];
  stepCount: number;
  toolsUsed: string[];
}

// Mirrors: src/artifactor/api/schemas.py -> PlaybookDetailResponse
export interface Playbook extends PlaybookMeta {
  steps: PlaybookStep[];
  examplePrompt: string;
}
