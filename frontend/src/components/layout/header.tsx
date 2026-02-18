"use client";

import Link from "next/link";
import { Button } from "@/components/ui/button";
import { ThemeToggle } from "@/components/ui/theme-toggle";

export function Header() {
  return (
    <header className="border-b border-border px-6 py-3 flex items-center justify-between">
      <Link href="/" className="text-lg font-bold text-foreground">
        Artifactor
      </Link>
      <nav className="flex items-center gap-1 text-sm text-foreground">
        <Button asChild variant="ghost" size="sm">
          <Link href="/">Home</Link>
        </Button>
        <Button asChild variant="ghost" size="sm">
          <Link href="/docs">Developer Docs</Link>
        </Button>
        <ThemeToggle />
      </nav>
    </header>
  );
}
