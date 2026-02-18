"use client";

import { useCallback, useEffect, useState } from "react";
import {
  ChevronRight,
  Folder,
  FolderUp,
  Loader2,
} from "lucide-react";
import * as Dialog from "@radix-ui/react-dialog";
import { Button } from "@/components/ui/button";

interface FolderPickerProps {
  open: boolean;
  onClose: () => void;
  onSelect: (path: string) => void;
}

interface BrowseEntry {
  name: string;
  type: string;
}

interface BrowseData {
  current: string;
  parent: string | null;
  entries: BrowseEntry[];
}

export function FolderPicker({ open, onClose, onSelect }: FolderPickerProps) {
  const [currentPath, setCurrentPath] = useState<string | null>(null);
  const [parent, setParent] = useState<string | null>(null);
  const [entries, setEntries] = useState<BrowseEntry[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const browse = useCallback(async (path?: string) => {
    setLoading(true);
    setError(null);
    try {
      const url = path
        ? `/api/filesystem/browse?path=${encodeURIComponent(path)}`
        : "/api/filesystem/browse";
      const res = await fetch(url);
      const json = await res.json();
      if (!json.success) {
        setError(json.error || "Failed to browse directory.");
        return;
      }
      const data = json.data as BrowseData;
      setCurrentPath(data.current);
      setParent(data.parent);
      setEntries(data.entries);
    } catch {
      setError("Could not connect to the server.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (open) {
      browse();
    }
  }, [open, browse]);

  const breadcrumbs = currentPath ? currentPath.split("/").filter(Boolean) : [];

  return (
    <Dialog.Root open={open} onOpenChange={(isOpen) => !isOpen && onClose()}>
      <Dialog.Portal>
        <Dialog.Overlay className="fixed inset-0 bg-black/50 z-50" />
        <Dialog.Content className="fixed left-1/2 top-1/2 -translate-x-1/2 -translate-y-1/2 z-50 w-full max-w-lg bg-background border border-border rounded-lg shadow-lg flex flex-col max-h-[80vh]">
          <div className="px-5 pt-5 pb-3 border-b border-border">
            <Dialog.Title className="text-base font-semibold">
              Choose Folder
            </Dialog.Title>
            <Dialog.Description className="text-sm text-muted-foreground mt-1">
              Navigate to the project directory you want to analyze.
            </Dialog.Description>
          </div>

          {/* Breadcrumb */}
          <div className="px-5 py-2 border-b border-border text-xs text-muted-foreground flex items-center gap-1 overflow-x-auto">
            <button
              type="button"
              onClick={() => browse("/")}
              className="hover:text-foreground transition-colors shrink-0"
            >
              /
            </button>
            {breadcrumbs.map((segment, i) => {
              const path = "/" + breadcrumbs.slice(0, i + 1).join("/");
              const isLast = i === breadcrumbs.length - 1;
              return (
                <span key={path} className="flex items-center gap-1">
                  <ChevronRight className="h-3 w-3 shrink-0" />
                  {isLast ? (
                    <span className="text-foreground font-medium">{segment}</span>
                  ) : (
                    <button
                      type="button"
                      onClick={() => browse(path)}
                      className="hover:text-foreground transition-colors"
                    >
                      {segment}
                    </button>
                  )}
                </span>
              );
            })}
          </div>

          {/* Directory listing */}
          <div className="flex-1 overflow-y-auto min-h-[200px]">
            {loading ? (
              <div className="flex items-center justify-center py-12">
                <Loader2 className="h-5 w-5 animate-spin text-muted-foreground" />
              </div>
            ) : error ? (
              <div className="px-5 py-8 text-center text-sm text-destructive">
                {error}
              </div>
            ) : (
              <div className="py-1">
                {/* Parent directory */}
                {parent && (
                  <button
                    type="button"
                    onClick={() => browse(parent)}
                    className="w-full flex items-center gap-3 px-5 py-2.5 text-sm hover:bg-accent/50 transition-colors text-left"
                  >
                    <FolderUp className="h-4 w-4 text-muted-foreground shrink-0" />
                    <span className="text-muted-foreground">..</span>
                  </button>
                )}

                {entries.length === 0 && !parent ? (
                  <p className="px-5 py-8 text-center text-sm text-muted-foreground">
                    No subdirectories found.
                  </p>
                ) : (
                  entries.map((entry) => (
                    <button
                      key={entry.name}
                      type="button"
                      onClick={() =>
                        browse(
                          currentPath === "/"
                            ? `/${entry.name}`
                            : `${currentPath}/${entry.name}`
                        )
                      }
                      className="w-full flex items-center gap-3 px-5 py-2.5 text-sm hover:bg-accent/50 transition-colors text-left"
                    >
                      <Folder className="h-4 w-4 text-muted-foreground shrink-0" />
                      <span className="truncate">{entry.name}</span>
                    </button>
                  ))
                )}
              </div>
            )}
          </div>

          {/* Footer */}
          <div className="px-5 py-3 border-t border-border flex items-center justify-between gap-3">
            <p className="text-xs text-muted-foreground truncate flex-1">
              {currentPath || ""}
            </p>
            <div className="flex gap-2 shrink-0">
              <Button variant="ghost" size="sm" onClick={onClose}>
                Cancel
              </Button>
              <Button
                size="sm"
                disabled={!currentPath}
                onClick={() => {
                  if (currentPath) {
                    onSelect(currentPath);
                    onClose();
                  }
                }}
              >
                Select
              </Button>
            </div>
          </div>
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}
