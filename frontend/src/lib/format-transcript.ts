import type { ChatMessage } from "@/hooks/use-chat";

export function formatChatTranscript(messages: ChatMessage[]): string {
  return messages
    .filter((m) => m.content)
    .map((m) => {
      const role = m.role === "user" ? "User" : "Assistant";
      const parts: string[] = [`${role}: ${m.content}`];
      if (m.citations?.length) {
        const cites = m.citations.map(
          (c) => `  - ${c.file_path}:${c.line_start}`,
        );
        parts.push("Citations:\n" + cites.join("\n"));
      }
      return parts.join("\n\n");
    })
    .join("\n\n---\n\n");
}
