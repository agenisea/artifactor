"use client";

import { useState, type ChangeEvent, type FormEvent } from "react";
import { useParams } from "next/navigation";
import { useChat } from "@/hooks/use-chat";
import { PageHeader } from "@/components/layout/page-header";
import { MessageList } from "@/components/chat/message-list";
import { InputArea } from "@/components/chat/input-area";
import { CopyButton } from "@/components/ui/copy-button";
import { formatChatTranscript } from "@/lib/format-transcript";

export default function ChatPage() {
  const params = useParams();
  const projectId = params.id as string;
  const [input, setInput] = useState("");
  const { messages, sendMessage, isStreaming } = useChat(projectId);

  const handleChange = (e: ChangeEvent<HTMLTextAreaElement>) =>
    setInput(e.target.value);

  const handleSubmit = (e: FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    if (!input.trim() || isStreaming) return;
    sendMessage(input.trim());
    setInput("");
  };

  return (
    <div className="flex h-full flex-col">
      <a
        href="#chat-input"
        className="sr-only focus:not-sr-only focus:absolute focus:z-50 focus:rounded-md focus:bg-primary focus:px-4 focus:py-2 focus:text-primary-foreground"
      >
        Skip to chat input
      </a>

      <PageHeader backHref={`/projects/${projectId}`} backLabel="Back to project" title="Chat">
        <div className="ml-auto">
          <CopyButton
            getText={() => formatChatTranscript(messages)}
            label="Copy chat"
          />
        </div>
      </PageHeader>

      <MessageList messages={messages} isStreaming={isStreaming} />

      <div id="chat-input">
        <InputArea
          value={input}
          onChange={handleChange}
          onSubmit={handleSubmit}
          disabled={isStreaming}
        />
      </div>
    </div>
  );
}
