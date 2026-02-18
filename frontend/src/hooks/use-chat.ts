"use client";

import { useCallback, useRef, useState } from "react";
import { useSSEStream } from "@agenisea/sse-kit/client";
import type {
  ChatEventData,
  ChatEventType,
  ChatResult,
  Citation,
  ConfidenceScore,
} from "@/types/api";

export interface ChatMessage {
  role: "user" | "assistant";
  content: string;
  citations?: Citation[];
  confidence?: ConfidenceScore | null;
  status?: string;
  isError?: boolean;
}

export function useChat(projectId: string) {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [conversationId, setConversationId] = useState<string | null>(null);

  // Ref tracks the assistant message index across closures
  const assistantIdxRef = useRef<number>(-1);
  const conversationIdRef = useRef<string | null>(null);
  conversationIdRef.current = conversationId;

  const { state, start, cancel, reset } = useSSEStream<
    { message: string; conversation_id: string | null },
    ChatResult,
    ChatEventData,
    ChatEventType
  >({
    endpoint: `${process.env.NEXT_PUBLIC_BACKEND_URL || "http://localhost:8000"}/api/projects/${projectId}/chat`,
    method: "POST",
    initialEvent: "idle",
    completeEvent: "complete",
    errorEvent: "error",
    extractResult: (data) => {
      if (data.message !== undefined && data.citations !== undefined) {
        return {
          message: data.message,
          citations: data.citations ?? [],
          confidence: data.confidence ?? null,
          tools_used: data.tools_used ?? [],
          conversation_id: data.conversation_id ?? "",
        };
      }
      return undefined;
    },
    onUpdate: (event, data) => {
      const idx = assistantIdxRef.current;
      if (idx < 0) return;

      if (event === "thinking" && data.status) {
        setMessages((prev) => {
          const updated = [...prev];
          updated[idx] = { ...updated[idx], status: data.status };
          return updated;
        });
      }
      if (event === "tool_call" && data.message) {
        setMessages((prev) => {
          const updated = [...prev];
          updated[idx] = { ...updated[idx], status: data.message };
          return updated;
        });
      }
    },
    onComplete: (result) => {
      const idx = assistantIdxRef.current;
      if (idx < 0) return;

      setMessages((prev) => {
        const updated = [...prev];
        updated[idx] = {
          role: "assistant",
          content: result.message,
          citations: result.citations,
          confidence: result.confidence,
          status: undefined,
        };
        return updated;
      });
      if (result.conversation_id) {
        setConversationId(result.conversation_id);
      }
    },
    onError: (error) => {
      const idx = assistantIdxRef.current;
      if (idx < 0) return;

      setMessages((prev) => {
        const updated = [...prev];
        updated[idx] = {
          role: "assistant",
          content: `Error: ${error}`,
          status: undefined,
          isError: true,
        };
        return updated;
      });
    },
  });

  const sendMessage = useCallback(
    (content: string) => {
      if (state.isStreaming) return;

      // Add user + placeholder assistant messages
      setMessages((prev) => {
        const next = [
          ...prev,
          { role: "user" as const, content },
          { role: "assistant" as const, content: "", status: "Thinking..." },
        ];
        assistantIdxRef.current = next.length - 1;
        return next;
      });

      reset();
      start({
        message: content,
        conversation_id: conversationIdRef.current,
      });
    },
    [state.isStreaming, start, reset],
  );

  return {
    messages,
    sendMessage,
    isStreaming: state.isStreaming,
    cancel,
    conversationId,
  };
}
