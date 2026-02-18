"use client";

import { CopyButton } from "@/components/ui/copy-button";
import { PageHeader } from "@/components/layout/page-header";

const MCP_CONFIG = `{
  "mcpServers": {
    "artifactor": {
      "command": "uv",
      "args": ["run", "artifactor", "mcp", "--project", "<project-id>"]
    }
  }
}`;

const MCP_CONFIG_SSE = `{
  "mcpServers": {
    "artifactor": {
      "url": "http://localhost:8001/sse"
    }
  }
}`;

interface ToolParam {
  name: string;
  type: string;
  default: string;
  description: string;
}

interface Tool {
  name: string;
  description: string;
  params: ToolParam[];
}

const TOOLS: Tool[] = [
  {
    name: "query_codebase",
    description:
      "Search the Intelligence Model for answers. Returns an answer with source citations.",
    params: [
      {
        name: "question",
        type: "string",
        default: "(required)",
        description: "Natural-language question about the codebase",
      },
      {
        name: "project_id",
        type: "string",
        default: '""',
        description: "Project ID (uses default if empty)",
      },
    ],
  },
  {
    name: "get_specification",
    description: "Retrieve a documentation section by name.",
    params: [
      {
        name: "section",
        type: "string",
        default: "(required)",
        description:
          "Section name (executive_overview, features, personas, user_stories, security_requirements, system_overview, data_models, interfaces, ui_specs, api_specs, integrations, tech_stories, security_considerations)",
      },
      {
        name: "project_id",
        type: "string",
        default: '""',
        description: "Project ID (uses default if empty)",
      },
    ],
  },
  {
    name: "list_features",
    description: "List all discovered features with code mappings.",
    params: [
      {
        name: "project_id",
        type: "string",
        default: '""',
        description: "Project ID (uses default if empty)",
      },
    ],
  },
  {
    name: "get_data_model",
    description: "Get entity attributes, types, and relationships.",
    params: [
      {
        name: "entity",
        type: "string",
        default: '""',
        description: "Entity name to search for (empty returns full section)",
      },
      {
        name: "project_id",
        type: "string",
        default: '""',
        description: "Project ID (uses default if empty)",
      },
    ],
  },
  {
    name: "explain_symbol",
    description: "Explain purpose, callers, and callees for a symbol.",
    params: [
      {
        name: "file_path",
        type: "string",
        default: "(required)",
        description: "Path to the source file",
      },
      {
        name: "symbol_name",
        type: "string",
        default: '""',
        description: "Symbol name within the file",
      },
      {
        name: "project_id",
        type: "string",
        default: '""',
        description: "Project ID (uses default if empty)",
      },
    ],
  },
  {
    name: "get_call_graph",
    description: "Get call graph for a function or method.",
    params: [
      {
        name: "file_path",
        type: "string",
        default: "(required)",
        description: "Path to the source file",
      },
      {
        name: "symbol_name",
        type: "string",
        default: "(required)",
        description: "Function or method name",
      },
      {
        name: "direction",
        type: "string",
        default: '"both"',
        description: "Traversal direction: callers, callees, or both",
      },
      {
        name: "depth",
        type: "int",
        default: "2",
        description: "Traversal depth (1\u20135)",
      },
      {
        name: "project_id",
        type: "string",
        default: '""',
        description: "Project ID (uses default if empty)",
      },
    ],
  },
  {
    name: "get_user_stories",
    description: "Get user stories with acceptance criteria.",
    params: [
      {
        name: "epic",
        type: "string",
        default: '""',
        description: "Filter by epic name",
      },
      {
        name: "persona",
        type: "string",
        default: '""',
        description: "Filter by persona",
      },
      {
        name: "project_id",
        type: "string",
        default: '""',
        description: "Project ID (uses default if empty)",
      },
    ],
  },
  {
    name: "get_api_endpoints",
    description: "Get discovered API endpoints.",
    params: [
      {
        name: "path_filter",
        type: "string",
        default: '""',
        description: "Filter endpoints by path",
      },
      {
        name: "method",
        type: "string",
        default: '""',
        description: "Filter by HTTP method (GET, POST, etc.)",
      },
      {
        name: "project_id",
        type: "string",
        default: '""',
        description: "Project ID (uses default if empty)",
      },
    ],
  },
  {
    name: "search_code_entities",
    description: "Search code entities by name or keyword.",
    params: [
      {
        name: "query",
        type: "string",
        default: "(required)",
        description: "Search query",
      },
      {
        name: "entity_type",
        type: "string",
        default: '""',
        description: "Filter by entity type (function, class, table, etc.)",
      },
      {
        name: "project_id",
        type: "string",
        default: '""',
        description: "Project ID (uses default if empty)",
      },
    ],
  },
  {
    name: "get_security_findings",
    description: "Get security findings with affected files.",
    params: [
      {
        name: "severity",
        type: "string",
        default: '""',
        description: "Filter by severity level",
      },
      {
        name: "category",
        type: "string",
        default: '""',
        description: "Filter by finding category",
      },
      {
        name: "project_id",
        type: "string",
        default: '""',
        description: "Project ID (uses default if empty)",
      },
    ],
  },
];

interface Resource {
  uri: string;
  description: string;
}

const RESOURCES: Resource[] = [
  {
    uri: "artifactor://projects",
    description: "List all analyzed projects with status",
  },
  {
    uri: "artifactor://project/{project_id}/overview",
    description: "Executive summary for a project",
  },
  {
    uri: "artifactor://project/{project_id}/sections",
    description: "Available documentation sections",
  },
  {
    uri: "artifactor://project/{project_id}/section/{section_name}",
    description: "Full section content as markdown",
  },
  {
    uri: "artifactor://project/{project_id}/diagram/{diagram_type}",
    description:
      "Mermaid diagram source (architecture, er, call_graph, component, sequence)",
  },
];

interface Prompt {
  name: string;
  description: string;
  args: { name: string; type: string; default: string }[];
}

const PROMPTS: Prompt[] = [
  {
    name: "explain_repo",
    description:
      "Generate a project briefing: overview + architecture + features.",
    args: [{ name: "project_id", type: "string", default: "(required)" }],
  },
  {
    name: "review_code",
    description: "Code review context with business rules and security.",
    args: [
      { name: "file_path", type: "string", default: "(required)" },
      { name: "project_id", type: "string", default: '""' },
    ],
  },
  {
    name: "write_tests",
    description: "Generate BDD test specifications from user stories.",
    args: [
      { name: "file_path", type: "string", default: "(required)" },
      { name: "symbol_name", type: "string", default: '""' },
      { name: "project_id", type: "string", default: '""' },
    ],
  },
  {
    name: "fix_bug",
    description: "Assemble context for bug fixing.",
    args: [
      { name: "bug_description", type: "string", default: "(required)" },
      { name: "project_id", type: "string", default: '""' },
    ],
  },
  {
    name: "migration_plan",
    description: "Generate a migration plan with risk analysis.",
    args: [
      {
        name: "target_description",
        type: "string",
        default: "(required)",
      },
      { name: "project_id", type: "string", default: '""' },
    ],
  },
];

export default function McpReferencePage() {
  return (
    <div className="flex h-full flex-col">
      <PageHeader backHref="/docs" backLabel="Back to docs" title="MCP Server Reference" />

      <div className="flex-1 overflow-y-auto">
        <div className="mx-auto max-w-4xl p-6 pb-16">
        <section className="mb-10">
          <h2 className="text-lg font-semibold mb-3">Connection</h2>

          <h3 className="text-sm font-semibold mt-4 mb-2">Local (stdio)</h3>
          <p className="text-sm text-muted-foreground mb-3">
            Add to{" "}
            <code className="rounded bg-muted px-1 py-0.5 text-xs">
              ~/.claude/mcp.json
            </code>{" "}
            to connect Claude Code:
          </p>
          <div className="relative">
            <pre className="rounded-lg bg-muted p-4 text-sm font-mono overflow-x-auto">
              {MCP_CONFIG}
            </pre>
            <div className="absolute top-2 right-2">
              <CopyButton getText={() => MCP_CONFIG} label="Copy config" />
            </div>
          </div>
          <p className="text-xs text-muted-foreground mt-2">
            Replace{" "}
            <code className="rounded bg-muted px-1 py-0.5">
              &lt;project-id&gt;
            </code>{" "}
            with your project ID from the dashboard or{" "}
            <code className="rounded bg-muted px-1 py-0.5">
              metadata.json
            </code>
            .
          </p>

          <h3 className="text-sm font-semibold mt-6 mb-2">Docker (SSE)</h3>
          <p className="text-sm text-muted-foreground mb-3">
            For containerized or remote access, use SSE transport:
          </p>
          <div className="relative">
            <pre className="rounded-lg bg-muted p-4 text-sm font-mono overflow-x-auto">
              {MCP_CONFIG_SSE}
            </pre>
            <div className="absolute top-2 right-2">
              <CopyButton getText={() => MCP_CONFIG_SSE} label="Copy config" />
            </div>
          </div>
          <p className="text-xs text-muted-foreground mt-2">
            Requires the{" "}
            <code className="rounded bg-muted px-1 py-0.5">mcp</code>{" "}
            service in{" "}
            <code className="rounded bg-muted px-1 py-0.5">
              docker-compose.yml
            </code>{" "}
            to be uncommented.
          </p>
        </section>

        <section className="mb-10">
          <h2 className="text-lg font-semibold mb-4">Tools ({TOOLS.length})</h2>
          <div className="space-y-6">
            {TOOLS.map((tool) => (
              <div key={tool.name} className="rounded-lg border border-border p-4">
                <h3 className="font-mono text-sm font-semibold mb-1">
                  {tool.name}
                </h3>
                <p className="text-sm text-muted-foreground mb-3">
                  {tool.description}
                </p>
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b border-border text-left">
                      <th className="pb-1.5 pr-4 font-medium">Parameter</th>
                      <th className="pb-1.5 pr-4 font-medium">Type</th>
                      <th className="pb-1.5 pr-4 font-medium">Default</th>
                      <th className="pb-1.5 font-medium">Description</th>
                    </tr>
                  </thead>
                  <tbody>
                    {tool.params.map((p) => (
                      <tr key={p.name} className="border-b border-border/50 last:border-0">
                        <td className="py-1.5 pr-4 font-mono text-xs">
                          {p.name}
                        </td>
                        <td className="py-1.5 pr-4 text-muted-foreground">
                          {p.type}
                        </td>
                        <td className="py-1.5 pr-4 font-mono text-xs text-muted-foreground">
                          {p.default}
                        </td>
                        <td className="py-1.5 text-muted-foreground">
                          {p.description}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ))}
          </div>
        </section>

        <section className="mb-10">
          <h2 className="text-lg font-semibold mb-4">
            Resources ({RESOURCES.length})
          </h2>
          <div className="rounded-lg border border-border overflow-hidden">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-border bg-muted/50 text-left">
                  <th className="px-4 py-2 font-medium">URI Pattern</th>
                  <th className="px-4 py-2 font-medium">Description</th>
                </tr>
              </thead>
              <tbody>
                {RESOURCES.map((r) => (
                  <tr key={r.uri} className="border-b border-border/50 last:border-0">
                    <td className="px-4 py-2 font-mono text-xs">{r.uri}</td>
                    <td className="px-4 py-2 text-muted-foreground">
                      {r.description}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>

        <section className="mb-10">
          <h2 className="text-lg font-semibold mb-4">
            Prompts ({PROMPTS.length})
          </h2>
          <div className="space-y-6">
            {PROMPTS.map((prompt) => (
              <div
                key={prompt.name}
                className="rounded-lg border border-border p-4"
              >
                <h3 className="font-mono text-sm font-semibold mb-1">
                  {prompt.name}
                </h3>
                <p className="text-sm text-muted-foreground mb-3">
                  {prompt.description}
                </p>
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b border-border text-left">
                      <th className="pb-1.5 pr-4 font-medium">Argument</th>
                      <th className="pb-1.5 pr-4 font-medium">Type</th>
                      <th className="pb-1.5 font-medium">Default</th>
                    </tr>
                  </thead>
                  <tbody>
                    {prompt.args.map((a) => (
                      <tr
                        key={a.name}
                        className="border-b border-border/50 last:border-0"
                      >
                        <td className="py-1.5 pr-4 font-mono text-xs">
                          {a.name}
                        </td>
                        <td className="py-1.5 pr-4 text-muted-foreground">
                          {a.type}
                        </td>
                        <td className="py-1.5 font-mono text-xs text-muted-foreground">
                          {a.default}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ))}
          </div>
        </section>
        </div>
      </div>
    </div>
  );
}
