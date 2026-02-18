"use client";

import { useCallback, useEffect, useState } from "react";
import { useParams, useRouter, useSearchParams } from "next/navigation";
import { FolderOpen, Trash2 } from "lucide-react";
import type { APIResponse } from "@/types/api";
import { Button } from "@/components/ui/button";
import { CopyButton } from "@/components/ui/copy-button";
import { PageHeader } from "@/components/layout/page-header";
import { AnalysisProgress } from "@/components/analysis-progress";
import { ConfirmDeleteDialog } from "@/components/confirm-delete-dialog";

interface ProjectDetail {
  id: string;
  name: string;
  status: string;
  local_path: string | null;
  branch: string | null;
  created_at: string;
}

interface SectionSummary {
  section_name: string;
  title: string;
  confidence: number;
}

export default function ProjectPage() {
  const params = useParams();
  const searchParams = useSearchParams();
  const router = useRouter();
  const projectId = params.id as string;
  const autoAnalyze = searchParams.get("analyze") === "true";

  const [project, setProject] = useState<ProjectDetail | null>(null);
  const [sections, setSections] = useState<SectionSummary[]>([]);
  const [showProgress, setShowProgress] = useState(false);
  const [deleteOpen, setDeleteOpen] = useState(false);
  const [notFound, setNotFound] = useState(false);

  const refreshProject = useCallback(() => {
    fetch(`/api/projects/${projectId}`)
      .then((res) => res.json())
      .then((data: APIResponse<ProjectDetail>) => {
        if (data.success && data.data) {
          setProject(data.data);
        } else {
          setNotFound(true);
        }
      })
      .catch(() => {
        setNotFound(true);
      });
  }, [projectId]);

  useEffect(() => {
    refreshProject();

    fetch(`/api/projects/${projectId}/sections`)
      .then((res) => res.json())
      .then((data: APIResponse<SectionSummary[]>) => {
        if (data.success && data.data) setSections(data.data);
      })
      .catch(() => {});
  }, [projectId, refreshProject]);

  // One-shot auto-analyze: strip the query param after triggering
  useEffect(() => {
    if (!autoAnalyze || !project) return;
    if (project.status === "analyzing" || project.status === "analyzed") return;
    setProject({ ...project, status: "analyzing" });
    setShowProgress(true);
    router.replace(`/projects/${projectId}`, { scroll: false });
  }, [autoAnalyze, project, projectId, router]);

  // Always mount AnalysisProgress when project is analyzing
  useEffect(() => {
    if (project?.status === "analyzing") {
      setShowProgress(true);
    }
  }, [project?.status]);

  const handleAnalyzeClick = () => {
    if (project) {
      setProject({ ...project, status: "analyzing" });
    }
    setShowProgress(true);
  };

  const handleComplete = () => {
    setShowProgress(false);
    refreshProject();
    fetch(`/api/projects/${projectId}/sections`)
      .then((res) => res.json())
      .then((data: APIResponse<SectionSummary[]>) => {
        if (data.success && data.data) setSections(data.data);
      })
      .catch(() => {});
  };

  const handlePaused = () => {
    setShowProgress(false);
    refreshProject();
  };

  const handleDelete = async () => {
    setDeleteOpen(false);
    await fetch(`/api/projects/${projectId}`, { method: "DELETE" });
    router.push("/");
  };

  if (notFound) {
    return (
      <div className="h-full overflow-y-auto p-8 max-w-4xl mx-auto">
        <PageHeader backHref="/" backLabel="Back to projects" title="Projects" variant="inline" />
        <div className="text-center py-12">
          <p className="text-muted-foreground">Project not found</p>
        </div>
      </div>
    );
  }

  if (!project) {
    return (
      <div className="p-8">
        <div className="animate-pulse h-8 w-64 bg-muted rounded mb-4" />
        <div className="animate-pulse h-4 w-96 bg-muted rounded" />
      </div>
    );
  }

  const statusBadge =
    {
      analyzed:
        "bg-green-100 text-green-800 dark:bg-green-900/30 dark:text-green-400",
      analyzing:
        "bg-amber-100 text-amber-800 dark:bg-amber-900/30 dark:text-amber-400 animate-pulse",
      error:
        "bg-red-100 text-red-800 dark:bg-red-900/30 dark:text-red-400",
      paused:
        "bg-blue-100 text-blue-800 dark:bg-blue-900/30 dark:text-blue-400",
      pending: "bg-muted text-muted-foreground",
    }[project.status] || "bg-muted text-muted-foreground";

  return (
    <>
      <div className="h-full overflow-y-auto p-8 max-w-4xl mx-auto">
        <PageHeader backHref="/" backLabel="Back to projects" title={project.name} variant="inline">
          <CopyButton
            getText={() => projectId}
            label="Copy Project ID"
            showLabel
          />
          <button
            type="button"
            onClick={() => setDeleteOpen(true)}
            className="inline-flex items-center justify-center rounded-md text-muted-foreground hover:text-destructive hover:bg-destructive/10 transition-colors h-8 w-8 shrink-0 ml-auto"
            aria-label="Delete project"
          >
            <Trash2 className="h-4 w-4" />
          </button>
        </PageHeader>

        <div className="flex items-center gap-4 text-sm mb-6">
          <span
            className={`text-xs px-2 py-1 rounded-md font-medium ${statusBadge}`}
          >
            {project.status}
          </span>
          {project.local_path && (
            <span className="flex items-center gap-1.5 text-muted-foreground">
              <FolderOpen className="h-4 w-4" />
              <span className="truncate max-w-md">{project.local_path}</span>
            </span>
          )}
        </div>

        {/* Status-driven views */}
        {showProgress ? (
          <div className="max-w-lg">
            <h2 className="text-xl font-semibold mb-4">Analysis Progress</h2>
            <AnalysisProgress
              projectId={projectId}
              onComplete={handleComplete}
              onError={() => {}}
              onPaused={handlePaused}
            />
          </div>
        ) : project.status === "paused" ? (
          <div className="text-center py-12">
            <p className="text-muted-foreground mb-4">
              Analysis is paused.
            </p>
            <Button onClick={handleAnalyzeClick}>Resume</Button>
          </div>
        ) : project.status === "pending" ? (
          <div className="text-center py-12">
            <p className="text-muted-foreground mb-4">
              This project hasn&apos;t been analyzed yet.
            </p>
            <Button onClick={handleAnalyzeClick}>Analyze</Button>
          </div>
        ) : project.status === "error" ? (
          <div className="text-center py-12">
            <p className="text-destructive mb-4">
              Analysis failed. You can retry.
            </p>
            <Button onClick={handleAnalyzeClick}>Retry</Button>
          </div>
        ) : (
          <>
            <div className="flex gap-3 mb-8">
              <Button asChild>
                <a href={`/projects/${projectId}/chat`}>Chat</a>
              </Button>
            </div>

            <h2 className="text-xl font-semibold mb-4">
              Documentation Sections
            </h2>
            {sections.length === 0 ? (
              <p className="text-muted-foreground">
                No sections generated yet.
              </p>
            ) : (
              <div className="grid grid-cols-2 gap-3">
                {sections.map((section) => (
                  <a
                    key={section.section_name}
                    href={`/projects/${projectId}/docs/${section.section_name}`}
                    className="p-3 border border-border rounded-lg hover:bg-accent/50 transition-colors bg-card"
                  >
                    <div className="font-medium">
                      {section.title}
                    </div>
                  </a>
                ))}
              </div>
            )}
          </>
        )}
      </div>

      <ConfirmDeleteDialog
        open={deleteOpen}
        projectName={project.name}
        onClose={() => setDeleteOpen(false)}
        onConfirm={handleDelete}
      />
    </>
  );
}
