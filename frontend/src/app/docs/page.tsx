import { Button } from "@/components/ui/button";

export default function DocsPage() {
  return (
    <div className="h-full overflow-y-auto p-8 max-w-4xl mx-auto">
      <h1 className="text-3xl font-bold mb-8">Developer Documentation</h1>
      <div className="space-y-8">
        <section>
          <h2 className="text-xl font-semibold mb-2">API Reference</h2>
          <p className="text-muted-foreground mb-3">
            Interactive API documentation powered by OpenAPI.
          </p>
          <div className="flex gap-3">
            <Button asChild variant="outline" size="sm">
              <a href="/docs/api">Swagger UI</a>
            </Button>
            <Button asChild variant="outline" size="sm">
              <a href="/docs/redoc">ReDoc</a>
            </Button>
          </div>
        </section>

        <section>
          <h2 className="text-xl font-semibold mb-2">MCP Server</h2>
          <p className="text-muted-foreground mb-3">
            Model Context Protocol integration for AI agents.
          </p>
          <Button asChild variant="outline" size="sm">
            <a href="/docs/mcp">MCP Reference</a>
          </Button>
        </section>
      </div>
    </div>
  );
}
