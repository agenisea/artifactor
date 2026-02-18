import Link from "next/link";

interface SidebarProps {
  projectId: string;
  sections: string[];
  activeSection?: string;
}

export function Sidebar({ projectId, sections, activeSection }: SidebarProps) {
  return (
    <aside className="w-64 border-r border-border p-4">
      <h3 className="text-sm font-semibold text-muted-foreground uppercase mb-3">
        Sections
      </h3>
      <nav className="space-y-1">
        {sections.map((section) => (
          <Link
            key={section}
            href={`/projects/${projectId}/docs/${section}`}
            className={`block px-3 py-2 rounded text-sm transition-colors ${
              activeSection === section
                ? "bg-accent text-accent-foreground font-medium"
                : "text-muted-foreground hover:bg-accent/50 hover:text-foreground"
            }`}
          >
            {section.replace(/_/g, " ")}
          </Link>
        ))}
      </nav>
    </aside>
  );
}
