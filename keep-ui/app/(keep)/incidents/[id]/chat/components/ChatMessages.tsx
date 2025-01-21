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
  loadingStates: { [key: string]: boolean };
  handleFeedback: (
    type: "thumbsUp" | "thumbsDown",
    message: Element
  ) => Promise<void>;
  clearChat: () => void;
}

export function ChatMessages({
  messages,
  user,
  isLoading,
  loadingStates,
  handleFeedback,
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
              {message instanceof TextMessage &&
                message.role === MessageRole.Assistant &&
                message.id && (
                  <div className="message-feedback absolute bottom-2 right-2 flex gap-2">
                    <button
                      className={`p-1 hover:bg-tremor-background-muted rounded-full transition-colors group relative ${
                        loadingStates && message.id && loadingStates[message.id]
                          ? "opacity-50 cursor-not-allowed"
                          : ""
                      }`}
                      onClick={async () => {
                        const messageElement = document.querySelector(
                          `[data-message-id="${message.id}"]`
                        );
                        if (messageElement) {
                          await handleFeedback("thumbsUp", messageElement);
                        }
                      }}
                    >
                      <span className="invisible group-hover:visible absolute bottom-full right-0 whitespace-nowrap rounded bg-tremor-background-emphasis px-2 py-1 text-xs text-tremor-background">
                        Add to RCA
                      </span>
                      <svg
                        width="15"
                        height="15"
                        viewBox="0 0 15 15"
                        fill="none"
                      >
                        <path
                          d="M7.5.8c-3.7 0-6.7 3-6.7 6.7s3 6.7 6.7 6.7 6.7-3 6.7-6.7-3-6.7-6.7-6.7zm0 12.4c-3.1 0-5.7-2.5-5.7-5.7s2.5-5.7 5.7-5.7 5.7 2.5 5.7 5.7-2.6 5.7-5.7 5.7z"
                          fill="currentColor"
                        />
                        <path
                          d="M4.8 7c.4 0 .8-.4.8-.8s-.4-.8-.8-.8-.8.4-.8.8.4.8.8.8zm5.4 0c.4 0 .8-.4.8-.8s-.4-.8-.8-.8-.8.4-.8.8.4.8.8.8zm-5.1 1.9h5.8c.2.8-.5 2.3-2.9 2.3s-3.1-1.5-2.9-2.3z"
                          fill="currentColor"
                        />
                      </svg>
                    </button>
                  </div>
                )}
            </div>
          ))}
          <div ref={messagesEndRef} />
        </div>
      </div>
    </div>
  );
}
