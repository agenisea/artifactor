"use client";

import { useEffect, useRef, useState } from "react";
import { FolderOpen, Loader2 } from "lucide-react";
import { FolderPicker } from "@/components/folder-picker";
import type { APIResponse, ProjectCreate } from "@/types/api";
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetFooter,
  SheetHeader,
  SheetTitle,
} from "@/components/ui/sheet";
import { Button } from "@/components/ui/button";

interface NewProjectSheetProps {
  open: boolean;
  onClose: () => void;
  onCreated: (projectId: string, autoAnalyze: boolean) => void;
}

export function NewProjectSheet({
  open,
  onClose,
  onCreated,
}: NewProjectSheetProps) {
  const [localPath, setLocalPath] = useState("");
  const [name, setName] = useState("");
  const [nameManuallyEdited, setNameManuallyEdited] = useState(false);
  const [autoAnalyze, setAutoAnalyze] = useState(true);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [pickerOpen, setPickerOpen] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);

  // Auto-derive name from last path segment
  useEffect(() => {
    if (nameManuallyEdited) return;
    if (!localPath.trim()) {
      setName("");
      return;
    }
    const segments = localPath.replace(/\/+$/, "").split("/");
    const last = segments[segments.length - 1] || "";
    setName(last);
  }, [localPath, nameManuallyEdited]);

  // Focus input when sheet opens
  useEffect(() => {
    if (open) {
      setTimeout(() => inputRef.current?.focus(), 300);
      setError(null);
    }
  }, [open]);

  // Reset form when closing
  useEffect(() => {
    if (!open) {
      setLocalPath("");
      setName("");
      setNameManuallyEdited(false);
      setAutoAnalyze(true);
      setError(null);
      setLoading(false);
    }
  }, [open]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);

    const trimmedPath = localPath.trim();
    if (!trimmedPath) {
      setError("Local path is required.");
      return;
    }
    if (!trimmedPath.startsWith("/")) {
      setError("Path must be absolute (start with /).");
      return;
    }

    const trimmedName = name.trim();
    if (!trimmedName) {
      setError("Project name is required.");
      return;
    }

    setLoading(true);
    try {
      const body: ProjectCreate = {
        name: trimmedName,
        local_path: trimmedPath,
        branch: null,
      };

      const res = await fetch("/api/projects", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });

      const data: APIResponse<{ id: string }> = await res.json();

      if (!data.success || !data.data) {
        setError(data.error || "Failed to create project.");
        return;
      }

      onCreated(data.data.id, autoAnalyze);
    } catch {
      setError("Could not connect to the server.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <Sheet open={open} onOpenChange={(isOpen) => !isOpen && onClose()}>
      <SheetContent side="right">
        <SheetHeader>
          <SheetTitle>Understand a Codebase</SheetTitle>
          <SheetDescription>
            Point Artifactor at a local codebase and it will generate cited
            documentation.
          </SheetDescription>
        </SheetHeader>

        <form
          onSubmit={handleSubmit}
          className="flex-1 flex flex-col px-6 gap-5 overflow-y-auto"
        >
          {/* Local path */}
          <div>
            <label
              htmlFor="local-path"
              className="block text-sm font-medium mb-1.5"
            >
              Local path <span className="text-muted-foreground">(required)</span>
            </label>
            <div className="flex gap-2">
              <input
                ref={inputRef}
                id="local-path"
                type="text"
                value={localPath}
                onChange={(e) => setLocalPath(e.target.value)}
                placeholder="/Users/you/projects/your-repo"
                className="flex-1 px-3 py-2 border border-input rounded-md text-sm bg-background focus:outline-none focus:ring-2 focus:ring-ring focus:border-transparent"
                autoComplete="off"
              />
              <Button
                type="button"
                variant="outline"
                size="sm"
                onClick={() => setPickerOpen(true)}
                aria-label="Browse for folder"
              >
                <FolderOpen className="h-4 w-4" />
                Browse
              </Button>
            </div>
            <p className="text-xs text-muted-foreground mt-1">
              Absolute path to a source code directory on this machine.
            </p>
          </div>

          {/* Project name */}
          <div>
            <label
              htmlFor="project-name"
              className="block text-sm font-medium mb-1.5"
            >
              Name
            </label>
            <input
              id="project-name"
              type="text"
              value={name}
              onChange={(e) => {
                setName(e.target.value);
                setNameManuallyEdited(true);
              }}
              placeholder="my-project"
              className="w-full px-3 py-2 border border-input rounded-md text-sm bg-background focus:outline-none focus:ring-2 focus:ring-ring focus:border-transparent"
            />
            <p className="text-xs text-muted-foreground mt-1">
              Auto-derived from folder name. You can change it.
            </p>
          </div>

          {/* Auto-analyze toggle */}
          <div className="flex items-center justify-between py-2">
            <div>
              <span className="text-sm font-medium">Auto-analyze</span>
              <p className="text-xs text-muted-foreground">
                Start analysis immediately after creating the project.
              </p>
            </div>
            <button
              type="button"
              role="switch"
              aria-checked={autoAnalyze}
              onClick={() => setAutoAnalyze(!autoAnalyze)}
              className={`relative w-11 h-6 rounded-full transition-colors ${
                autoAnalyze ? "bg-primary" : "bg-muted"
              }`}
            >
              <span
                className={`absolute top-0.5 left-0.5 w-5 h-5 bg-primary-foreground rounded-full transition-transform ${
                  autoAnalyze ? "translate-x-5" : "translate-x-0"
                }`}
              />
            </button>
          </div>

          {/* Error */}
          {error && (
            <div
              role="alert"
              className="text-sm text-destructive bg-destructive/10 px-3 py-2 rounded-md"
            >
              {error}
            </div>
          )}

          {/* Spacer */}
          <div className="flex-1" />
        </form>

        <SheetFooter>
          <Button type="submit" disabled={loading} className="w-full" onClick={handleSubmit}>
            {loading ? (
              <span className="flex items-center justify-center gap-2">
                <Loader2 className="h-4 w-4 animate-spin" />
                Creating...
              </span>
            ) : autoAnalyze ? (
              "Analyze"
            ) : (
              "Add"
            )}
          </Button>
        </SheetFooter>
      </SheetContent>

      <FolderPicker
        open={pickerOpen}
        onClose={() => setPickerOpen(false)}
        onSelect={(path) => setLocalPath(path)}
      />
    </Sheet>
  );
}
