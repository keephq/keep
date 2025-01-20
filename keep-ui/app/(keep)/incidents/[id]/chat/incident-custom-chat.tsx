import { useState, useEffect, useRef } from "react";
import { Card } from "@tremor/react";
import { Button } from "@tremor/react";
import { StopIcon, TrashIcon } from "@radix-ui/react-icons";
import {
  Message,
  TextMessage,
  MessageRole,
  ActionExecutionMessage,
  ResultMessage,
  AgentStateMessage,
} from "@copilotkit/runtime-client-gql";
import {
  CopilotTask,
  useCopilotChat,
  useCopilotContext,
} from "@copilotkit/react-core";
import { EmptyStateCard } from "@/components/ui/EmptyStateCard";
import { useRouter } from "next/navigation";
import type { IncidentDto } from "@/entities/incidents/model";
import Image from "next/image";
import { User } from "next-auth";
import { ChatMarkdown } from "./chatmarkdown";

function UserAvatar({
  user,
  className = "",
}: {
  user?: User | null;
  className?: string;
}) {
  if (!user?.image) {
    return (
      <div
        className={`${className} bg-gray-200 rounded-full flex items-center justify-center`}
      >
        <span className="text-gray-500 text-sm">{user?.name?.[0] || "A"}</span>
      </div>
    );
  }

  return (
    <div className={`${className} relative rounded-full overflow-hidden`}>
      <Image
        src={user.image}
        alt={user.name || "User"}
        className="object-cover"
        fill
        sizes="(max-width: 32px) 32px"
      />
    </div>
  );
}

function MessageBotHeader() {
  return (
    <div className="flex items-center gap-2 mb-2">
      <Image src="/keep.svg" alt="Keep AI Logo" width={32} height={32} />
      <span className="font-semibold">Keep Incidents Resolver</span>
    </div>
  );
}

function MessageUserHeader({ user }: { user?: User | null }) {
  return (
    <div className="flex items-center gap-2 mb-2">
      <UserAvatar user={user} className="h-6 w-6" />
      <span className="font-semibold">{user?.name || "Anonymous"}</span>
    </div>
  );
}

function LoadingSpinner() {
  return (
    <div className="flex items-center justify-center p-2">
      <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-orange-500"></div>
    </div>
  );
}

function RenderMessage({
  message,
  isLastMessage,
  isLoading,
}: {
  message: Message;
  isLastMessage?: boolean;
  isLoading?: boolean;
}) {
  if (message instanceof TextMessage) {
    return (
      <div>
        <div className="prose prose-sm max-w-none break-words">
          <div className="max-w-[95%] whitespace-pre-wrap">
            <ChatMarkdown>{message.content}</ChatMarkdown>
          </div>
        </div>
        {isLastMessage && isLoading && <LoadingSpinner />}
      </div>
    );
  }

  if (message instanceof ActionExecutionMessage) {
    return (
      <div className="text-sm text-gray-500 break-words">
        Executing action: {message.name}
        {message.arguments && (
          <pre className="mt-1 text-xs bg-gray-100 p-2 rounded overflow-x-auto">
            {JSON.stringify(message.arguments, null, 2)}
          </pre>
        )}
        {isLastMessage && isLoading && <LoadingSpinner />}
      </div>
    );
  }

  if (message instanceof ResultMessage) {
    return (
      <div className="text-sm break-words">
        <div className="text-gray-500">Action result:</div>
        <pre className="mt-1 text-xs bg-gray-100 p-2 rounded overflow-x-auto">
          {typeof message.result === "string"
            ? message.result
            : JSON.stringify(message.result, null, 2)}
        </pre>
        {isLastMessage && isLoading && <LoadingSpinner />}
      </div>
    );
  }

  if (message instanceof AgentStateMessage) {
    return (
      <div className="text-sm text-gray-500">
        Agent state update: {message.agentName}
        {isLastMessage && isLoading && <LoadingSpinner />}
      </div>
    );
  }

  return null;
}

function CustomChatFooter({
  user,
  inputValue,
  setInputValue,
  onSubmit,
  isLoading,
  onStopGeneration,
}: {
  user?: User | null;
  inputValue: string;
  setInputValue: (value: string) => void;
  onSubmit: (e: React.FormEvent) => void;
  isLoading: boolean;
  onStopGeneration: () => void;
}) {
  return (
    <div className="border-t bg-white p-4">
      <form onSubmit={onSubmit} className="flex items-start gap-4">
        <UserAvatar user={user} className="h-8 w-8 mt-2" />
        <div className="flex-1 relative">
          <textarea
            value={inputValue}
            onChange={(e) => setInputValue(e.target.value)}
            placeholder="For example: Find the root cause of this incident"
            className="w-full p-3 pr-24 border rounded-lg resize-none focus:ring-2 focus:ring-orange-300 min-h-[80px]"
            disabled={isLoading}
          />
          <div className="absolute bottom-2 right-2">
            {!isLoading ? (
              <Button
                type="submit"
                color="orange"
                disabled={!inputValue.trim()}
              >
                Submit
              </Button>
            ) : (
              <Button color="orange" onClick={onStopGeneration} icon={StopIcon}>
                Stop
              </Button>
            )}
          </div>
        </div>
      </form>
    </div>
  );
}

interface CustomIncidentChatProps {
  incident: IncidentDto;
  mutateIncident: () => void;
  alerts: any;
  user?: User | null;
  handleFeedback: (
    type: "thumbsUp" | "thumbsDown",
    message: Element
  ) => Promise<void>;
  rcaTask: CopilotTask;
  loadingStates: { [key: string]: boolean };
  setLoadingStates: React.Dispatch<
    React.SetStateAction<{ [key: string]: boolean }>
  >;
}

export function CustomIncidentChat({
  incident,
  alerts,
  user,
  handleFeedback,
  loadingStates,
}: CustomIncidentChatProps) {
  const router = useRouter();
  const [inputValue, setInputValue] = useState("");
  const messagesEndRef = useRef<HTMLDivElement>(null);

  const {
    visibleMessages,
    appendMessage,
    setMessages,
    stopGeneration,
    isLoading,
    runChatCompletion,
  } = useCopilotChat({
    id: incident.id,
  });

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  };

  useEffect(() => {
    scrollToBottom();
  }, [visibleMessages]);

  // Filter out empty messages
  const filteredMessages = visibleMessages.filter((message) => {
    if (message instanceof TextMessage) {
      return message.content.trim() !== "";
    }
    if (message instanceof ActionExecutionMessage) {
      return message.name || message.arguments;
    }
    if (message instanceof ResultMessage) {
      return message.result !== undefined && message.result !== null;
    }
    if (message instanceof AgentStateMessage) {
      return message.agentName;
    }
    return false;
  });

  // Load messages from localStorage
  useEffect(() => {
    const savedMessages = localStorage.getItem(
      `copilotkit-messages-${incident.id}`
    );
    if (savedMessages) {
      try {
        const parsed = JSON.parse(savedMessages);
        const validMessages = parsed.filter((msg: any) => {
          return msg.content?.trim() !== "" || msg.result || msg.name;
        });
        setMessages(validMessages);
      } catch (error) {
        console.error("Error parsing saved messages:", error);
        localStorage.removeItem(`copilotkit-messages-${incident.id}`);
      }
    }
  }, [incident.id]);

  // Save messages to localStorage
  useEffect(() => {
    if (filteredMessages.length > 0) {
      localStorage.setItem(
        `copilotkit-messages-${incident.id}`,
        JSON.stringify(filteredMessages)
      );
    }
  }, [filteredMessages, incident.id]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!inputValue.trim() || isLoading) return;

    const userMessage = new TextMessage({
      content: inputValue,
      role: MessageRole.User,
      id: Math.random().toString(),
      createdAt: new Date().toISOString(),
    });

    try {
      await appendMessage(userMessage);
      setInputValue("");
      await runChatCompletion();
    } catch (error) {
      console.error("Error running chat completion:", error);
    }
  };

  if (!alerts?.items || alerts.items.length === 0) {
    return (
      <EmptyStateCard
        title="Chat not available"
        description="No alerts found for this incident. Go to the alerts feed and assign alerts to interact with the incident."
        buttonText="Assign alerts to this incident"
        onClick={() => router.push("/alerts/feed")}
      />
    );
  }

  return (
    <Card className="flex flex-col max-h-[calc(100vh-10rem)]">
      <div className="relative flex-1 flex flex-col h-full">
        <Button
          color="orange"
          variant="secondary"
          tooltip="Clear chat"
          onClick={() => {
            localStorage.removeItem(`copilotkit-messages-${incident.id}`);
            setMessages([]);
          }}
          icon={TrashIcon}
          className="absolute top-2 right-2 z-10"
        />

        <div className="flex-1 overflow-y-auto p-4">
          <div className="flex flex-col gap-6">
            {visibleMessages.map((message, index) => (
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
                  message.role === MessageRole.Assistant && (
                    <MessageBotHeader />
                  )}
                {message instanceof TextMessage &&
                  message.role === MessageRole.User && (
                    <MessageUserHeader user={user} />
                  )}
                <RenderMessage
                  message={message}
                  isLastMessage={index === visibleMessages.length - 1}
                  isLoading={isLoading}
                />
                {message instanceof TextMessage &&
                  message.role === MessageRole.Assistant &&
                  message.id && (
                    <div className="message-feedback absolute bottom-2 right-2 flex gap-2">
                      <button
                        className={`p-1 hover:bg-tremor-background-muted rounded-full transition-colors group relative ${
                          loadingStates &&
                          message.id &&
                          loadingStates[message.id]
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

        <CustomChatFooter
          user={user}
          inputValue={inputValue}
          setInputValue={setInputValue}
          onSubmit={handleSubmit}
          isLoading={isLoading}
          onStopGeneration={stopGeneration}
          onClearChat={() => {
            localStorage.removeItem(`copilotkit-messages-${incident.id}`);
            setMessages([]);
          }}
        />
      </div>
    </Card>
  );
}
export default CustomIncidentChat;
