import { PageHeader } from "@/components/layout/page-header";

export default function SwaggerPage() {
  return (
    <div className="flex h-full flex-col">
      <PageHeader backHref="/docs" backLabel="Back to docs" title="API Reference" />

      <iframe
        src="/api/docs"
        title="Swagger UI — Artifactor API Reference"
        className="flex-1 border-none bg-white"
        allow="clipboard-write"
      />
    </div>
  );
}
