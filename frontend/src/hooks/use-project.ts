"use client";

import { useEffect, useState } from "react";
import type { APIResponse } from "@/types/api";

interface Project {
  id: string;
  name: string;
  status: string;
  local_path: string | null;
  branch: string | null;
  created_at: string;
}

interface Section {
  section_name: string;
  content: string;
  confidence: number;
}

export function useProject(projectId: string) {
  const [project, setProject] = useState<Project | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setLoading(true);
    fetch(`/api/projects/${projectId}`)
      .then((res) => res.json())
      .then((data: APIResponse<Project>) => {
        if (data.success && data.data) {
          setProject(data.data);
        } else {
          setError(data.error || "Failed to load project");
        }
      })
      .catch((err) => setError(String(err)))
      .finally(() => setLoading(false));
  }, [projectId]);

  return { project, loading, error };
}

export function useSection(projectId: string, sectionName: string) {
  const [section, setSection] = useState<Section | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    setLoading(true);
    fetch(`/api/projects/${projectId}/sections/${sectionName}`)
      .then((res) => res.json())
      .then((data: APIResponse<Section>) => {
        if (data.success && data.data) {
          setSection(data.data);
        }
      })
      .catch(() => {})
      .finally(() => setLoading(false));
  }, [projectId, sectionName]);

  return { section, loading };
}
