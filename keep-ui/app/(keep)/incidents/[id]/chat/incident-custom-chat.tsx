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
import { ChatFooter } from "./components/ChatFooter";
import { ChatMessages } from "./components/ChatMessages";
import { useCopilotChat } from "@copilotkit/react-core";
import "./incident-chat.css";

interface CustomIncidentChatProps {
  incident: IncidentDto;
  mutateIncident: () => void;
  alerts: any;
  user?: User | null;
  initialMessage?: string; // Add this prop for the initial message
}

export function CustomIncidentChat({
  incident,
  alerts,
  user,
  initialMessage = "How can I help you with this incident? 🕵️",
}: CustomIncidentChatProps) {
  const [inputValue, setInputValue] = useState("");
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

  const handleSubmit = async (message: string) => {
    if (!message.trim() || isLoading) return;

    const userMessage = new TextMessage({
      content: message,
      role: MessageRole.User,
      id: Math.random().toString(),
      createdAt: new Date().toISOString(),
    });

    try {
      await appendMessage(userMessage);
      await runChatCompletion();
    } catch (error) {
      console.error("Error running chat completion:", error);
    }
  };

  const clearChat = () => {
    localStorage.removeItem(`copilotkit-messages-${incident.id}`);
    setMessages([]);
    const initialSystemMessage = new TextMessage({
      content: initialMessage,
      role: MessageRole.Assistant,
      id: "initial-message",
      createdAt: new Date().toISOString(),
    });
    setMessages([initialSystemMessage]);
  };

  return (
    <Card className="h-full flex flex-col">
      <div className="flex-1 h-0 flex flex-col overflow-hidden">
        <ChatMessages
          messages={visibleMessages}
          user={user}
          isLoading={isLoading}
          clearChat={clearChat}
        />

        <div className="flex-shrink-0 border-t bg-white px-4">
          <ChatFooter
            user={user}
            onMessageSubmit={handleSubmit}
            isLoading={isLoading}
            onStopGeneration={stopGeneration}
          />
        </div>
      </div>
    </Card>
  );
}
