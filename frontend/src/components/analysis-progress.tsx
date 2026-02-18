"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { Check, Circle, Loader2, Pause, X } from "lucide-react";
import { useSSEStream } from "@agenisea/sse-kit/client";
import { Button } from "@/components/ui/button";

interface Stage {
  name: string;
  label: string;
  status: "pending" | "running" | "done" | "error";
  message: string;
  duration_ms: number;
}

interface CompleteSummary {
  project_id: string;
  sections: number;
  stages_ok: number;
  stages_failed: number;
  duration_ms: number;
}

type AnalysisEventType = "idle" | "stage" | "complete" | "paused" | "error";

interface ProgressInfo {
  completed: number;
  total: number;
  percent: number;
}

interface AnalysisEventData {
  message?: string;
  name?: string;
  status?: string;
  duration_ms?: number;
  completed?: number;
  total?: number;
  percent?: number;
  project_id?: string;
  sections?: number;
  stages_ok?: number;
  stages_failed?: number;
  label?: string;
  error?: string;
}

interface AnalysisProgressProps {
  projectId: string;
  onComplete: () => void;
  onError: () => void;
  compact?: boolean;
  onPaused?: () => void;
}

export function AnalysisProgress({
  projectId,
  onComplete,
  onError,
  compact = false,
  onPaused,
}: AnalysisProgressProps) {
  const [stages, setStages] = useState<Stage[]>([]);
  const [summary, setSummary] = useState<CompleteSummary | null>(null);
  const [progress, setProgress] = useState<ProgressInfo | null>(null);
  const [elapsedMs, setElapsedMs] = useState(0);
  const [isPausing, setIsPausing] = useState(false);
  const startTimeRef = useRef<number>(Date.now());
  const timerRef = useRef<ReturnType<typeof setInterval> | undefined>(undefined);

  const { state, start, reset } = useSSEStream<
    void,
    CompleteSummary,
    AnalysisEventData,
    AnalysisEventType
  >({
    endpoint: `${process.env.NEXT_PUBLIC_BACKEND_URL || "http://localhost:8000"}/api/projects/${projectId}/analyze`,
    method: "POST",
    initialEvent: "idle",
    completeEvent: "complete",
    errorEvent: "error",
    extractResult: (data) => {
      if (data.project_id && data.sections !== undefined) {
        return {
          project_id: data.project_id,
          sections: data.sections,
          stages_ok: data.stages_ok ?? 0,
          stages_failed: data.stages_failed ?? 0,
          duration_ms: data.duration_ms ?? 0,
        };
      }
      return undefined;
    },
    onUpdate: (event, data) => {
      if (event === "paused") {
        if (timerRef.current) clearInterval(timerRef.current);
        onPaused?.();
        return;
      }
      if (data.name) {
        const stage: Stage = {
          name: data.name,
          label: data.label ?? data.name,
          status: (data.status as Stage["status"]) || "running",
          message: data.message || "",
          duration_ms: data.duration_ms || 0,
        };
        setStages((prev) => {
          const idx = prev.findIndex((s) => s.name === stage.name);
          if (idx >= 0) {
            const updated = [...prev];
            updated[idx] = stage;
            return updated;
          }
          return [...prev, stage];
        });
        if (
          data.completed !== undefined &&
          data.total !== undefined &&
          data.percent !== undefined
        ) {
          setProgress({
            completed: data.completed,
            total: data.total,
            percent: data.percent,
          });
        }
      }
    },
    onComplete: (result) => {
      setSummary(result);
      if (timerRef.current) clearInterval(timerRef.current);
      onComplete();
    },
    onError: () => {
      if (timerRef.current) clearInterval(timerRef.current);
      onError();
    },
  });

  const startRef = useRef(start);
  const resetRef = useRef(reset);
  startRef.current = start;
  resetRef.current = reset;

  const startAnalysis = useCallback(() => {
    setStages([]);
    setSummary(null);
    setProgress(null);
    setElapsedMs(0);
    startTimeRef.current = Date.now();
    timerRef.current = setInterval(() => {
      setElapsedMs(Date.now() - startTimeRef.current);
    }, 500);
    resetRef.current();
    startRef.current(undefined as unknown as void);
  }, []);

  const startedRef = useRef(false);

  useEffect(() => {
    if (startedRef.current) return;
    startedRef.current = true;
    startAnalysis();
    return () => {
      if (timerRef.current) clearInterval(timerRef.current);
    };
  }, [startAnalysis]);

  const handlePause = async (e: React.MouseEvent) => {
    e.preventDefault();
    e.stopPropagation();
    if (isPausing) return;
    setIsPausing(true);
    try {
      const res = await fetch(
        `${process.env.NEXT_PUBLIC_BACKEND_URL || "http://localhost:8000"}/api/projects/${projectId}/pause`,
        { method: "POST" },
      );
      const data = await res.json();
      if (data.success) {
        if (timerRef.current) clearInterval(timerRef.current);
        onPaused?.();
        return;
      }
    } catch {
      // Network error — fall through to re-enable
    }
    setIsPausing(false);
  };

  const formatDuration = (ms: number) => {
    const rounded = Math.round(ms);
    if (rounded < 1000) return `${rounded}ms`;
    const secs = Math.floor(rounded / 1000);
    if (secs < 60) return `${secs}s`;
    const mins = Math.floor(secs / 60);
    const remainSecs = secs % 60;
    return `${mins}m ${remainSecs}s`;
  };

  // Current stage for compact display
  const currentStage = stages.findLast((s) => s.status === "running") ?? stages.at(-1);
  const overallPercent =
    progress?.percent ??
    (stages.length > 0
      ? Math.round(
          (stages.filter((s) => s.status === "done").length / stages.length) *
            100,
        )
      : 0);

  // ── Compact rendering ──────────────────────────────────────
  if (compact) {
    return (
      <div className="flex items-center gap-2 px-1 py-1">
        <Loader2 className="h-4 w-4 text-primary animate-spin shrink-0" />
        <span className="text-xs text-muted-foreground truncate min-w-0 flex-1">
          {currentStage ? currentStage.label : "Starting..."}
        </span>
        <span className="text-xs text-muted-foreground shrink-0">
          {overallPercent}%
        </span>
        <div className="w-16 bg-muted rounded-full h-1.5 shrink-0">
          <div
            className="bg-primary h-1.5 rounded-full transition-all duration-300"
            style={{ width: `${overallPercent}%` }}
          />
        </div>
        <button
          type="button"
          onClick={handlePause}
          disabled={isPausing}
          className="inline-flex items-center justify-center rounded-md text-muted-foreground hover:text-foreground hover:bg-accent transition-colors h-6 w-6 shrink-0 disabled:opacity-50 disabled:pointer-events-none"
          aria-label="Pause analysis"
        >
          {isPausing
            ? <Loader2 className="h-3.5 w-3.5 animate-spin" />
            : <Pause className="h-3.5 w-3.5" />}
        </button>
      </div>
    );
  }

  // ── Full rendering ─────────────────────────────────────────

  const completedStages = stages.filter((s) => s.status === "done");
  const avgMs =
    completedStages.length >= 2
      ? completedStages.reduce((sum, s) => sum + s.duration_ms, 0) /
        completedStages.length
      : 0;
  const pendingCount = stages.filter(
    (s) => s.status === "running" || s.status === "pending",
  ).length;
  const estimatedRemainingMs =
    avgMs > 0 && pendingCount > 0 ? Math.round(avgMs * pendingCount) : 0;

  const stageIcon = (status: Stage["status"]) => {
    switch (status) {
      case "running":
        return <Loader2 className="h-5 w-5 text-primary animate-spin" />;
      case "done":
        return <Check className="h-5 w-5 text-green-600 dark:text-green-400" />;
      case "error":
        return <X className="h-5 w-5 text-destructive" />;
      default:
        return <Circle className="h-5 w-5 text-muted-foreground" />;
    }
  };

  return (
    <div className="space-y-6">
      {/* Timer + pause */}
      <div className="flex items-center justify-between text-sm text-muted-foreground">
        <span>Elapsed: {formatDuration(elapsedMs)}</span>
        <div className="flex items-center gap-3">
          {estimatedRemainingMs > 0 && !summary && !state.error && (
            <span>~{formatDuration(estimatedRemainingMs)} remaining</span>
          )}
          {!summary && !state.error && stages.length > 0 && (
            <Button variant="outline" size="sm" onClick={handlePause} disabled={isPausing}>
              {isPausing ? (
                <>
                  <Loader2 className="h-3.5 w-3.5 mr-1 animate-spin" />
                  Pausing...
                </>
              ) : (
                <>
                  <Pause className="h-3.5 w-3.5 mr-1" />
                  Pause
                </>
              )}
            </Button>
          )}
        </div>
      </div>

      {/* Stage list */}
      <div className="space-y-3">
        {stages.map((stage) => (
          <div key={stage.name} className="flex items-start gap-3">
            <div className="mt-0.5 shrink-0">{stageIcon(stage.status)}</div>
            <div className="flex-1 min-w-0">
              <div className="flex items-center justify-between">
                <span className="text-sm font-medium">
                  {stage.label}
                </span>
                {stage.status === "done" && stage.duration_ms > 0 && (
                  <span className="text-xs text-muted-foreground">
                    {formatDuration(stage.duration_ms)}
                  </span>
                )}
              </div>
              {stage.status === "running" && stage.message && (
                <p className="text-xs text-muted-foreground mt-0.5">
                  {stage.message}
                </p>
              )}
            </div>
          </div>
        ))}
      </div>

      {/* Progress bar */}
      {progress && !summary && !state.error && (
        <div className="space-y-1">
          <div className="w-full bg-muted rounded-full h-2">
            <div
              className="bg-primary h-2 rounded-full transition-all duration-300"
              style={{ width: `${progress.percent}%` }}
            />
          </div>
          <span className="text-xs text-muted-foreground">
            {progress.completed}/{progress.total} chunks
          </span>
        </div>
      )}

      {/* Reassurance */}
      {!summary && !state.error && stages.length > 0 && (
        <p className="text-xs text-muted-foreground text-center">
          You can navigate away — your project will be waiting.
        </p>
      )}

      {/* Complete */}
      {summary && (
        <div className="rounded-lg border border-border bg-card p-4 space-y-2">
          <p className="text-sm font-medium">Analysis complete</p>
          <p className="text-sm text-muted-foreground">
            Generated {summary.sections} documentation section
            {summary.sections !== 1 ? "s" : ""} in{" "}
            {formatDuration(summary.duration_ms)}.
          </p>
          <Button variant="default" size="sm" asChild>
            <a href={`/projects/${projectId}`}>View documentation</a>
          </Button>
        </div>
      )}

      {/* Error */}
      {state.error && (
        <div className="rounded-lg border border-destructive/50 bg-destructive/10 p-4 space-y-2">
          <p className="text-sm font-medium text-destructive">{state.error}</p>
          <Button
            variant="outline"
            size="sm"
            onClick={() => startAnalysis()}
          >
            Retry
          </Button>
        </div>
      )}
    </div>
  );
}
