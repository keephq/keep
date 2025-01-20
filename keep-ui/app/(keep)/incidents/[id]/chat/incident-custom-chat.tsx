import { useState, useEffect, useRef } from "react";
import { Card } from "@tremor/react";
import { Button } from "@tremor/react";
import { TrashIcon } from "@radix-ui/react-icons";
import {
  Message,
  TextMessage,
  MessageRole,
} from "@copilotkit/runtime-client-gql";
import { CopilotTask } from "@copilotkit/react-core";
import type { IncidentDto } from "@/entities/incidents/model";
import { User } from "next-auth";
import {
  MessageBotHeader,
  MessageUserHeader,
} from "./components/MessageHeaders";
import { MessageRenderer } from "./components/MessageRenderer";
import { ChatFooter } from "./components/ChatFooter";
import { useCopilotChat } from "@copilotkit/react-core";
import "./incident-chat.css";

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
  initialMessage?: string; // Add this prop for the initial message
}

export function CustomIncidentChat({
  incident,
  alerts,
  user,
  handleFeedback,
  loadingStates,
  initialMessage = "How can I help you with this incident? 🕵️", // Default initial message
}: CustomIncidentChatProps) {
  const [inputValue, setInputValue] = useState("");
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const initialMessageShownRef = useRef(false);

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

  // Load messages from localStorage or show initial message
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
    } else if (!initialMessageShownRef.current) {
      // Show initial message only if there are no saved messages
      const initialSystemMessage = new TextMessage({
        content: initialMessage,
        role: MessageRole.Assistant,
        id: "initial-message",
        createdAt: new Date().toISOString(),
      });
      setMessages([initialSystemMessage]);
      initialMessageShownRef.current = true;
    }
  }, [incident.id, initialMessage]);

  // Save messages to localStorage
  useEffect(() => {
    if (visibleMessages.length > 0) {
      localStorage.setItem(
        `copilotkit-messages-${incident.id}`,
        JSON.stringify(visibleMessages)
      );
    }
  }, [visibleMessages, incident.id]);

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

  return (
    <Card className="flex flex-col h-[calc(100vh-10rem)]">
      <div className="relative flex-1 flex flex-col overflow-hidden">
        <Button
          color="orange"
          variant="secondary"
          tooltip="Clear chat"
          onClick={() => {
            localStorage.removeItem(`copilotkit-messages-${incident.id}`);
            setMessages([]);
            // Show initial message again after clearing
            const initialSystemMessage = new TextMessage({
              content: initialMessage,
              role: MessageRole.Assistant,
              id: "initial-message",
              createdAt: new Date().toISOString(),
            });
            setMessages([initialSystemMessage]);
          }}
          icon={TrashIcon}
          className="absolute top-2 right-2 z-10"
        />

        {/* Rest of the component remains the same */}
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
                <MessageRenderer
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

        <ChatFooter
          user={user}
          inputValue={inputValue}
          setInputValue={setInputValue}
          onSubmit={handleSubmit}
          isLoading={isLoading}
          onStopGeneration={stopGeneration}
        />
      </div>
    </Card>
  );
}
