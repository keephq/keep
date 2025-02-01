// ChatMessages.tsx
import { User } from "next-auth";
import {
  Message,
  TextMessage,
  MessageRole,
} from "@copilotkit/runtime-client-gql";
import { MessageBotHeader, MessageUserHeader } from "./MessageHeaders";
import { MessageRenderer } from "./MessageRenderer";
import { useRef, useEffect } from "react";
import { Button } from "@tremor/react";
import { TrashIcon } from "@radix-ui/react-icons";

interface ChatMessagesProps {
  messages: Message[];
  user?: User | null;
  isLoading: boolean;
  clearChat: () => void;
}

export function ChatMessages({
  messages,
  user,
  isLoading,
  clearChat,
}: ChatMessagesProps) {
  const messagesEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  return (
    <div className="relative flex-1 min-h-0 overflow-hidden">
      <Button
        color="orange"
        variant="secondary"
        tooltip="Clear chat"
        onClick={clearChat}
        icon={TrashIcon}
        className="absolute top-2 right-2 z-10"
      />

      <div className="absolute inset-0 overflow-y-auto px-4 pb-4">
        <div className="flex flex-col gap-6 py-4">
          {messages.map((message, index) => (
            <div
              key={message.id || index}
              className="max-w-[85%]"
              data-message-role={
                message instanceof TextMessage
                  ? message.role.toLowerCase()
                  : "system"
              }
              data-message-id={message.id}
              style={{ position: "relative" }}
            >
              {message instanceof TextMessage &&
                message.role === MessageRole.Assistant && <MessageBotHeader />}
              {message instanceof TextMessage &&
                message.role === MessageRole.User && (
                  <MessageUserHeader user={user} />
                )}
              <MessageRenderer
                message={message}
                isLastMessage={index === messages.length - 1}
                isLoading={isLoading}
              />
            </div>
          ))}
          <div ref={messagesEndRef} />
        </div>
      </div>
    </div>
  );
}
