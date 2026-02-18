"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { Play, Plus, RotateCcw, Trash2 } from "lucide-react";
import type { APIResponse } from "@/types/api";
import { Button } from "@/components/ui/button";
import { AnalysisProgress } from "@/components/analysis-progress";
import { ConfirmDeleteDialog } from "@/components/confirm-delete-dialog";
import { NewProjectSheet } from "@/components/new-project-sheet";

interface ProjectSummary {
  id: string;
  name: string;
  status: string;
  local_path: string | null;
  created_at: string;
}

const statusBadge = (status: string) => {
  switch (status) {
    case "analyzed":
      return "bg-green-100 text-green-800 dark:bg-green-900/30 dark:text-green-400";
    case "analyzing":
      return "bg-amber-100 text-amber-800 dark:bg-amber-900/30 dark:text-amber-400 animate-pulse";
    case "error":
      return "bg-red-100 text-red-800 dark:bg-red-900/30 dark:text-red-400";
    case "paused":
      return "bg-blue-100 text-blue-800 dark:bg-blue-900/30 dark:text-blue-400";
    default:
      return "bg-muted text-muted-foreground";
  }
};

export default function HomePage() {
  const router = useRouter();
  const [projects, setProjects] = useState<ProjectSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [sheetOpen, setSheetOpen] = useState(false);
  const [deleteTarget, setDeleteTarget] = useState<ProjectSummary | null>(null);

  const refreshProjects = useCallback(
    () =>
      fetch("/api/projects")
        .then((res) => res.json())
        .then((data: APIResponse<ProjectSummary[]>) => {
          if (data.success && data.data) {
            setProjects(data.data);
          }
        })
        .catch(() => {}),
    [],
  );

  // Periodically refresh when any project is analyzing
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  useEffect(() => {
    const hasAnalyzing = projects.some((p) => p.status === "analyzing");
    if (hasAnalyzing && !pollRef.current) {
      pollRef.current = setInterval(refreshProjects, 5000);
    } else if (!hasAnalyzing && pollRef.current) {
      clearInterval(pollRef.current);
      pollRef.current = null;
    }
    return () => {
      if (pollRef.current !== null) {
        clearInterval(pollRef.current);
        pollRef.current = null;
      }
    };
  }, [projects, refreshProjects]);

  useEffect(() => {
    refreshProjects().finally(() => setLoading(false));
  }, [refreshProjects]);

  const handleCreated = (projectId: string, autoAnalyze: boolean) => {
    setSheetOpen(false);
    if (autoAnalyze) {
      router.push(`/projects/${projectId}?analyze=true`);
    } else {
      router.push(`/projects/${projectId}`);
    }
  };

  const handleAnalyze = (e: React.MouseEvent, projectId: string) => {
    e.preventDefault();
    e.stopPropagation();
    // Optimistic status update
    setProjects((prev) =>
      prev.map((p) =>
        p.id === projectId ? { ...p, status: "analyzing" } : p,
      ),
    );
  };

  const handleDelete = async () => {
    if (!deleteTarget) return;
    const id = deleteTarget.id;
    setDeleteTarget(null);
    await fetch(`/api/projects/${id}`, { method: "DELETE" });
    setProjects((prev) => prev.filter((p) => p.id !== id));
  };

  const hasProjects = !loading && projects.length > 0;

  return (
    <>
      <div className="h-full overflow-y-auto p-8 max-w-4xl mx-auto">
        <div className="flex items-center justify-between mb-8">
          <div>
            <div className="flex items-center gap-3 mb-2">
              <img src="/icon.svg" alt="Artifactor" className="w-9 h-9" />
              <h1 className="text-3xl font-bold">Artifactor</h1>
            </div>
            <p className="text-muted-foreground">
              Code intelligence platform — turns any codebase into queryable
              intelligence
            </p>
          </div>
        </div>

        {loading ? (
          <div className="animate-pulse space-y-3">
            {[1, 2, 3].map((i) => (
              <div key={i} className="h-16 bg-muted rounded-lg" />
            ))}
          </div>
        ) : !hasProjects ? (
          <div className="text-center py-16">
            <p className="text-muted-foreground mb-4">
              No projects yet. Understand your first codebase to get started.
            </p>
            <Button onClick={() => setSheetOpen(true)}>
              <Plus className="h-4 w-4" />
              Understand a Codebase
            </Button>
          </div>
        ) : (
          <>
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-lg font-semibold">Projects</h2>
              <Button
                size="icon"
                variant="outline"
                onClick={() => setSheetOpen(true)}
                aria-label="Add project"
              >
                <Plus className="h-4 w-4" />
              </Button>
            </div>
            <div className="space-y-3">
              {projects.map((project) => (
                <div
                  key={project.id}
                  className="border border-border rounded-lg bg-card overflow-hidden"
                >
                  <a
                    href={`/projects/${project.id}`}
                    className="block p-4 hover:bg-accent/50 transition-colors"
                  >
                    <div className="flex justify-between items-center">
                      <div className="min-w-0">
                        <h3 className="font-medium">{project.name}</h3>
                        {project.local_path && (
                          <p className="text-sm text-muted-foreground truncate">
                            {project.local_path}
                          </p>
                        )}
                      </div>
                      <span
                        className={`text-xs px-2 py-1 rounded-md font-medium shrink-0 ml-4 ${statusBadge(project.status)}`}
                      >
                        {project.status}
                      </span>
                    </div>
                  </a>

                  {/* Footer: action buttons + compact progress */}
                  <div className="border-t border-border px-4 py-2 flex items-center justify-between">
                    {project.status === "analyzing" ? (
                      <AnalysisProgress
                        projectId={project.id}
                        onComplete={refreshProjects}
                        onError={refreshProjects}
                        onPaused={refreshProjects}
                        compact
                      />
                    ) : project.status === "pending" ? (
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={(e) => handleAnalyze(e, project.id)}
                      >
                        <Play className="h-3.5 w-3.5 mr-1" />
                        Analyze
                      </Button>
                    ) : project.status === "error" ? (
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={(e) => handleAnalyze(e, project.id)}
                      >
                        <RotateCcw className="h-3.5 w-3.5 mr-1" />
                        Retry
                      </Button>
                    ) : project.status === "paused" ? (
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={(e) => handleAnalyze(e, project.id)}
                      >
                        <Play className="h-3.5 w-3.5 mr-1" />
                        Resume
                      </Button>
                    ) : (
                      <span />
                    )}
                    <button
                      type="button"
                      onClick={(e) => {
                        e.preventDefault();
                        e.stopPropagation();
                        setDeleteTarget(project);
                      }}
                      className="inline-flex items-center justify-center rounded-md text-muted-foreground hover:text-destructive hover:bg-destructive/10 transition-colors h-7 w-7 shrink-0"
                      aria-label={`Delete ${project.name}`}
                    >
                      <Trash2 className="h-3.5 w-3.5" />
                    </button>
                  </div>
                </div>
              ))}
            </div>
          </>
        )}
      </div>

      <NewProjectSheet
        open={sheetOpen}
        onClose={() => setSheetOpen(false)}
        onCreated={handleCreated}
      />

      {deleteTarget && (
        <ConfirmDeleteDialog
          open={!!deleteTarget}
          projectName={deleteTarget.name}
          onClose={() => setDeleteTarget(null)}
          onConfirm={handleDelete}
        />
      )}
    </>
  );
}
