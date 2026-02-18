import { ArrowLeft } from "lucide-react";

interface PageHeaderProps {
  backHref: string;
  backLabel: string;
  title: string;
  variant?: "bar" | "inline";
  children?: React.ReactNode;
}

export function PageHeader({
  backHref,
  backLabel,
  title,
  variant = "bar",
  children,
}: PageHeaderProps) {
  const isBar = variant === "bar";

  return (
    <div
      className={
        isBar
          ? "flex items-center gap-2 border-b border-border px-4 py-3 shrink-0"
          : "flex items-center gap-3 mb-2"
      }
    >
      <a
        href={backHref}
        aria-label={backLabel}
        className="inline-flex shrink-0 items-center justify-center rounded-md text-muted-foreground transition-colors touch-target hover:bg-accent hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
      >
        <ArrowLeft className="h-5 w-5" aria-hidden="true" />
      </a>
      <h1
        className={
          isBar ? "text-xl font-bold" : "text-3xl font-bold"
        }
      >
        {title}
      </h1>
      {children}
    </div>
  );
}
