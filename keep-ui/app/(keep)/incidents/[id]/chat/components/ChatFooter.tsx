import { Button } from "@tremor/react";
import { StopIcon } from "@radix-ui/react-icons";
import { IoIosArrowForward } from "react-icons/io";
import { User } from "next-auth";
import { UserAvatar } from "./UserAvatar";

interface ChatFooterProps {
  user?: User | null;
  inputValue: string;
  setInputValue: (value: string) => void;
  onSubmit: (e: React.FormEvent) => void;
  isLoading: boolean;
  onStopGeneration: () => void;
}

export function ChatFooter({
  user,
  inputValue,
  setInputValue,
  onSubmit,
  isLoading,
  onStopGeneration,
}: ChatFooterProps) {
  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      if (inputValue.trim()) {
        onSubmit(e as any);
      }
    }
  };

  return (
    <div className="border-t bg-white p-2">
      <form onSubmit={onSubmit} className="flex items-center gap-4">
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
