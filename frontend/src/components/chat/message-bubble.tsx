import type { Citation } from "@/types/api";
import { cn } from "@/lib/utils";

interface MessageBubbleProps {
  role: "user" | "assistant";
  content: string;
  citations?: Citation[];
  isError?: boolean;
}

export function MessageBubble({
  role,
  content,
  citations,
  isError,
}: MessageBubbleProps) {
  const isUser = role === "user";

  return (
    <div
      className={cn(
        "flex w-full gap-3",
        isUser ? "flex-row-reverse" : "flex-row",
      )}
    >
      <div
        className={cn(
          "max-w-[80%] rounded-2xl px-4 py-3 text-base leading-normal sm:max-w-[70%]",
          isError
            ? "border border-destructive bg-destructive/10 text-destructive"
            : isUser
              ? "bg-primary text-primary-foreground"
              : "border border-border bg-card text-card-foreground",
        )}
        role={isError ? "alert" : undefined}
      >
        <p className="whitespace-pre-wrap break-words">{content}</p>

        {citations && citations.length > 0 && (
          <div className="mt-2 flex flex-wrap gap-1.5">
            {citations.map((c, j) => (
              <span
                key={j}
                className="inline-flex items-center rounded-md bg-muted px-2 py-0.5 text-xs font-mono text-muted-foreground"
              >
                {c.file_path}:{c.line_start}-{c.line_end}
              </span>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
