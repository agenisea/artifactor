interface TypingIndicatorProps {
  status?: string;
}

export function TypingIndicator({ status }: TypingIndicatorProps) {
  return (
    <div className="flex justify-start" aria-label="Processing">
      <div
        className="rounded-2xl border border-border bg-card px-4 py-3"
        role="status"
        aria-live="polite"
      >
        <div className="flex items-center gap-1">
          <span className="typing-dot h-2 w-2 rounded-full bg-muted-foreground" />
          <span className="typing-dot h-2 w-2 rounded-full bg-muted-foreground" />
          <span className="typing-dot h-2 w-2 rounded-full bg-muted-foreground" />
        </div>
        {status && (
          <p className="mt-1.5 text-xs text-muted-foreground">{status}</p>
        )}
        <span className="sr-only">
          {status || "Analyzing codebase..."}
        </span>
      </div>
    </div>
  );
}
