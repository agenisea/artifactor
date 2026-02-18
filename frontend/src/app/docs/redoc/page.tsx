import { PageHeader } from "@/components/layout/page-header";

export default function RedocPage() {
  return (
    <div className="flex h-full flex-col">
      <PageHeader backHref="/docs" backLabel="Back to docs" title="ReDoc" />

      <iframe
        src="/api/redoc"
        title="ReDoc — Artifactor API Reference"
        className="flex-1 border-none bg-white"
      />
    </div>
  );
}
