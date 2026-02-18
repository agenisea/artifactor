"use client";

import { useEffect, useRef } from "react";
import type { ChatMessage } from "@/hooks/use-chat";
import { MessageBubble } from "./message-bubble";
import { TypingIndicator } from "./typing-indicator";

interface MessageListProps {
  messages: ChatMessage[];
  isStreaming: boolean;
}

export function MessageList({ messages, isStreaming }: MessageListProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const lastContent = messages[messages.length - 1]?.content;

  // Auto-scroll on new messages
  useEffect(() => {
    const el = containerRef.current;
    if (!el) return;
    el.scrollTo({ top: el.scrollHeight, behavior: "smooth" });
  }, [messages.length, lastContent, isStreaming]);

  const lastMsg = messages[messages.length - 1];
  const showTyping =
    isStreaming && lastMsg?.role === "assistant" && !lastMsg.content;

  return (
    <div
      ref={containerRef}
      role="log"
      aria-label="Conversation history"
      aria-live="polite"
      aria-relevant="additions"
      className="flex-1 overflow-y-auto"
    >
      <div className="mx-auto max-w-3xl space-y-4 p-4">
        {messages.length === 0 && (
          <p className="mt-8 text-center text-muted-foreground">
            Ask a question about this codebase.
          </p>
        )}

        {messages.map((msg, i) => {
          // Don't render the placeholder assistant message when typing indicator is shown
          if (showTyping && i === messages.length - 1) return null;
          return (
            <MessageBubble
              key={i}
              role={msg.role}
              content={msg.content}
              citations={msg.citations}
              isError={msg.isError}
            />
          );
        })}

        {showTyping && <TypingIndicator status={lastMsg?.status} />}
      </div>
    </div>
  );
}
