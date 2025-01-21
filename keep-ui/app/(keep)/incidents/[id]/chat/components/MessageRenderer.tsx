import {
  Message,
  TextMessage,
  MessageRole,
  ActionExecutionMessage,
  ResultMessage,
  AgentStateMessage,
} from "@copilotkit/runtime-client-gql";
import { ChatMarkdown } from "./ChatMarkdown";
import { LoadingSpinner } from "./LoadingSpinner";

interface MessageRendererProps {
  message: Message;
  isLastMessage?: boolean;
  isLoading?: boolean;
}

export function MessageRenderer({
  message,
  isLastMessage,
  isLoading,
}: MessageRendererProps) {
  const messageWrapper = "relative px-4";
  const messageContent = "pl-8"; // Increased left padding from 6 to 8
  const verticalLine = "absolute top-0 left-[10px] w-[2px] h-full bg-gray-200"; // Added left offset

  if (message instanceof TextMessage) {
    return (
      <div className={messageWrapper}>
        <div className={verticalLine} />
        <div className={messageContent}>
          <div className="message-text break-words">
            <div className="max-w-[95%] prose prose-sm [&>*]:!m-0 [&_p]:!m-0 [&_ol]:!m-0 [&_ul]:!m-0 [&_li]:!m-0">
              <ChatMarkdown>{message.content}</ChatMarkdown>
            </div>
          </div>
          {isLastMessage && isLoading && <LoadingSpinner />}
        </div>
      </div>
    );
  }

  if (message instanceof ActionExecutionMessage) {
    return (
      <div className={messageWrapper}>
        <div className={verticalLine} />
        <div className={messageContent}>
          <div className="text-sm text-gray-500 break-words">
            Executing action: {message.name}
            {message.arguments && (
              <pre className="mt-1 text-xs bg-gray-100 p-2 rounded overflow-x-auto">
                {JSON.stringify(message.arguments, null, 2)}
              </pre>
            )}
            {isLastMessage && isLoading && <LoadingSpinner />}
          </div>
        </div>
      </div>
    );
  }

  if (message instanceof ResultMessage) {
    return (
      <div className={messageWrapper}>
        <div className={verticalLine} />
        <div className={messageContent}>
          <div className="text-sm break-words">
            <div className="text-gray-500">Action result:</div>
            <pre className="mt-1 text-xs bg-gray-100 p-2 rounded overflow-x-auto">
              {typeof message.result === "string"
                ? message.result
                : JSON.stringify(message.result, null, 2)}
            </pre>
            {isLastMessage && isLoading && <LoadingSpinner />}
          </div>
        </div>
      </div>
    );
  }

  if (message instanceof AgentStateMessage) {
    return (
      <div className={messageWrapper}>
        <div className={verticalLine} />
        <div className={messageContent}>
          <div className="text-sm text-gray-500">
            Agent state update: {message.agentName}
            {isLastMessage && isLoading && <LoadingSpinner />}
          </div>
        </div>
      </div>
    );
  }

  return null;
}
