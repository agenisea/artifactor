"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import ReactMarkdown from "react-markdown";
import { PageHeader } from "@/components/layout/page-header";
import remarkGfm from "remark-gfm";
import type { APIResponse } from "@/types/api";

interface SectionData {
  section_name: string;
  title: string;
  content: string;
  confidence: number;
}

function confidenceBadge(confidence: number) {
  const pct = Math.round(confidence * 100);
  if (pct >= 80)
    return "bg-green-100 text-green-800 dark:bg-green-900/30 dark:text-green-400";
  if (pct >= 60)
    return "bg-amber-100 text-amber-800 dark:bg-amber-900/30 dark:text-amber-400";
  return "bg-red-100 text-red-800 dark:bg-red-900/30 dark:text-red-400";
}

export default function SectionPage() {
  const params = useParams();
  const projectId = params.id as string;
  const sectionName = params.section as string;
  const [section, setSection] = useState<SectionData | null>(null);

  useEffect(() => {
    fetch(`/api/projects/${projectId}/sections/${sectionName}`)
      .then((res) => res.json())
      .then((data: APIResponse<SectionData>) => {
        if (data.success && data.data) setSection(data.data);
      })
      .catch(() => {});
  }, [projectId, sectionName]);

  if (!section) {
    return (
      <div className="p-8">
        <div className="animate-pulse space-y-3">
          <div className="h-8 w-64 bg-muted rounded" />
          <div className="h-4 w-full bg-muted rounded" />
          <div className="h-4 w-full bg-muted rounded" />
        </div>
      </div>
    );
  }

  const pct = Math.round(section.confidence * 100);

  return (
    <div className="flex h-full flex-col">
      {/* Pinned header */}
      <PageHeader backHref={`/projects/${projectId}`} backLabel="Back to project" title={section.title}>
        <span
          className={`text-xs px-2 py-1 rounded-md font-medium ${confidenceBadge(section.confidence)}`}
        >
          {pct}% confidence
        </span>
      </PageHeader>

      {/* Scrollable content */}
      <div className="flex-1 overflow-y-auto">
        <div className="mx-auto max-w-4xl p-6 pb-16">
          <div className="prose prose-sm dark:prose-invert max-w-none">
            <ReactMarkdown remarkPlugins={[remarkGfm]}>
              {section.content}
            </ReactMarkdown>
          </div>
        </div>
      </div>
    </div>
  );
}
