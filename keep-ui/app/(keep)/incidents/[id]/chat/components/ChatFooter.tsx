import { Button } from "@tremor/react";
import { StopIcon } from "@radix-ui/react-icons";
import { IoIosArrowForward } from "react-icons/io";
import { User } from "next-auth";
import { UserAvatar } from "./UserAvatar";
import { useState } from "react";

export function ChatFooter({
  user,
  isLoading,
  onStopGeneration,
  onMessageSubmit, // New prop instead of onSubmit
}: {
  user?: User | null;
  isLoading: boolean;
  onStopGeneration: () => void;
  onMessageSubmit: (message: string) => void;
}) {
  const [inputValue, setInputValue] = useState(""); // Move state here

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!inputValue.trim() || isLoading) return;

    onMessageSubmit(inputValue);
    setInputValue(""); // Clear input after submission
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      if (inputValue.trim()) {
        handleSubmit(e);
      }
    }
  };

  return (
    <div className="border-t bg-white">
      <form onSubmit={handleSubmit} className="flex items-center gap-2 mt-2">
        <UserAvatar user={user} className="h-8 w-8" />
        <div className="flex-1 relative">
          <textarea
            value={inputValue}
            onChange={(e) => setInputValue(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="For example: Find the root cause of this incident"
            className="w-full p-3 pr-24 border rounded-lg resize-none focus:ring-2 focus:ring-orange-300 focus:outline-none min-h-[80px]"
            disabled={isLoading}
          />
          <div className="absolute top-1/2 right-2 -translate-y-1/2">
            {!isLoading ? (
              <Button
                type="submit"
                color="orange"
                icon={IoIosArrowForward}
                disabled={!inputValue.trim()}
                size="sm"
              />
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
